#!/usr/bin/env python3
"""1コマずつの「保存→点検→記録」を助ける（工程④）。状態は panels.json に書く。

  save    <案件> <ID> <落ちてきたファイル>   img/<ID>_<名前>.<拡張子> に置く。前の版は _v1, _v2 … に退避。前と同じ中身なら止める
  check   <案件> <ID>                        機械チェック（サイズ・比率・背景透過・前の版と同一でないか）＋
                                             点検用の画像を qa/<ID>/ に作る：
                                               phone.png   … スマホ表示と同じ大きさ（幅390px）。文字が読めるかはこれで見る
                                               zoom.png    … 2倍。セリフを一字一句読むとき用
                                               chara.png   … キャラクター設定シートと並べたもの（人物の取り違え確認用）
  mark    <案件> <ID> ok|ng|stop [--score N] [--note ...]   点検結果を記録（attempts を数える）
  status  <案件>                              全コマの状況を一覧

panels.json の形は references/story_and_prompts.md の「panels.json」。
"""
import argparse, hashlib, json, shutil, sys, time
from pathlib import Path

PHONE_W = 390


def load(proj):
    p = Path(proj).expanduser() / 'panels.json'
    return p, json.loads(p.read_text())


def find(d, pid):
    for x in d['panels']:
        if x['id'] == pid:
            return x
    sys.exit(f'{pid} は panels.json にありません')


def current_file(proj, panel):
    img = Path(proj).expanduser() / 'img'
    for ext in ('.png', '.webp', '.jpg'):
        f = img / f'{panel["file"]}{ext}'
        if f.exists():
            return f
    return None


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def cmd_save(a):
    proj = Path(a.proj).expanduser()
    pth, d = load(proj)
    pn = find(d, a.id)
    src = Path(a.src).expanduser()
    if not src.exists():
        sys.exit(f'ファイルがありません: {src}')
    cur = current_file(proj, pn)
    if cur and sha(cur) == sha(src):
        sys.exit('前の版と同じ画像です（古い画像を保存した可能性）。チャットの一番下までスクロールして、最新の画像を保存し直してください')
    (proj / 'img').mkdir(exist_ok=True)
    if cur:
        n = 1
        while (proj / 'img' / f'{pn["file"]}_v{n}{cur.suffix}').exists():
            n += 1
        cur.rename(proj / 'img' / f'{pn["file"]}_v{n}{cur.suffix}')
        print(f'前の版 → {pn["file"]}_v{n}{cur.suffix}')
    ext = src.suffix.lower() if src.suffix else '.png'
    dst = proj / 'img' / f'{pn["file"]}{ext}'
    shutil.copy(src, dst)
    print(f'保存：{dst}')


def cmd_check(a):
    from PIL import Image
    proj = Path(a.proj).expanduser()
    pth, d = load(proj)
    pn = find(d, a.id)
    f = current_file(proj, pn)
    if not f:
        sys.exit(f'img/{pn["file"]}.* がありません')
    im = Image.open(f)
    w, h = im.size
    res = {'id': a.id, 'file': f.name, 'size': [w, h], 'mode': im.mode, 'problems': [], 'notes': []}
    # サイズ・比率
    ew, eh = [int(x) for x in pn['size'].split('x')]
    if abs(w / h - ew / eh) > 0.03:
        res['problems'].append(f'縦横比が違う：{w}×{h}（指定 {ew}×{eh}）')
    if w < 1000 and h < 1000:
        res['problems'].append(f'解像度が低い：{w}×{h}')
    # 背景透過
    if pn.get('transparent'):
        if im.mode not in ('RGBA', 'LA', 'P'):
            res['problems'].append('背景透過の指定なのに、透明の情報がない（白で塗られている）')
        else:
            from PIL import ImageStat
            al = im.convert('RGBA').getchannel('A')
            s = max(8, min(w, h) // 20)
            box = {'左上': (0, 0, s, s), '右上': (w - s, 0, w, s), '左下': (0, h - s, s, h), '右下': (w - s, h - s, w, h)}
            vals = {k: ImageStat.Stat(al.crop(b)).mean[0] for k, b in box.items()}
            if vals['左上'] > 10 or vals['右上'] > 10:
                res['problems'].append(f'上の角が透明になっていない（不透明度 { {k: round(v) for k, v in vals.items()} }）')
            else:
                res['notes'].append('上の角は透明：OK')
                if vals['左下'] > 10 or vals['右下'] > 10:
                    res['notes'].append('下の角に絵がある（上半身を下で切る絵なら問題なし。白い板なら直す）')
            hist = al.histogram()
            transparent_ratio = sum(hist[:10]) / (w * h)
            if transparent_ratio < 0.15:
                res['problems'].append(f'透明な部分が少ない（{transparent_ratio:.0%}）。背景が残っている可能性')
            # 白い縁（透過の周りに白い板が残る）
            rgb = im.convert('RGBA')
            edge = [rgb.getpixel((x, h // 2)) for x in range(0, w // 6)]
            if any(p[3] > 200 and p[0] > 245 and p[1] > 245 and p[2] > 245 for p in edge[:5]):
                res['notes'].append('左端に白い不透明の部分あり：白い板が残っていないか目で確認')
    elif im.mode in ('RGBA', 'LA'):
        al = im.getchannel('A')
        if al.getextrema()[0] < 250:
            res['problems'].append('背景透過の指定がないのに透明な部分がある')
    # 前の版と同一
    olds = sorted((proj / 'img').glob(f'{pn["file"]}_v*'))
    if olds and sha(olds[-1]) == sha(f):
        res['problems'].append('前の版と同じ画像（直っていない／古い画像を保存した）')
    # 点検用の画像
    q = proj / 'qa' / a.id
    q.mkdir(parents=True, exist_ok=True)
    rgb = im.convert('RGBA')
    bg = Image.new('RGBA', rgb.size, (255, 255, 255, 255) if not pn.get('transparent') else (200, 200, 200, 255))
    flat = Image.alpha_composite(bg, rgb).convert('RGB')
    # スマホでの表示幅（縦長の図解も横いっぱいに出す）
    pw = round(PHONE_W * pn.get('display_ratio', 1.0))
    flat.resize((pw, round(h * pw / w)), Image.LANCZOS).save(q / 'phone.png')
    flat.resize((pw * 2, round(h * pw * 2 / w)), Image.LANCZOS).save(q / 'zoom.png')
    chara = proj / 'img' / (d.get('chara_sheet') or 'P0_chara.png')
    if not chara.exists():
        cands = sorted((proj / 'img').glob('P0_chara.*'))
        chara = cands[0] if cands else None
    if chara and pn.get('characters'):
        c = Image.open(chara).convert('RGB')
        H = 700
        c = c.resize((round(c.width * H / c.height), H))
        p2 = flat.resize((round(w * H / h), H))
        out = Image.new('RGB', (c.width + p2.width + 20, H), 'white')
        out.paste(c, (0, 0)); out.paste(p2, (c.width + 20, 0))
        out.save(q / 'chara.png')
    res['qa'] = [str(q / n) for n in ('phone.png', 'zoom.png', 'chara.png') if (q / n).exists()]
    res['expect'] = {'texts': pn.get('texts', []), 'characters': pn.get('characters', []), 'checks': pn.get('checks', [])}
    (q / 'machine.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps(res, ensure_ascii=False, indent=1))


def cmd_mark(a):
    pth, d = load(a.proj)
    pn = find(d, a.id)
    pn.setdefault('history', []).append({'at': time.strftime('%Y-%m-%d %H:%M'), 'result': a.result, 'score': a.score, 'note': a.note})
    pn['attempts'] = sum(1 for x in pn['history'] if x['result'] == 'ng')
    pn['status'] = {'ok': 'done', 'ng': 'fixing', 'stop': 'ask_human'}[a.result]
    if a.result == 'ng' and pn['attempts'] >= d.get('max_fix', 3):
        pn['status'] = 'ask_human'
        print(f'{a.id}: 直しが{pn["attempts"]}回に達したので、人に相談してください')
    pth.write_text(json.dumps(d, ensure_ascii=False, indent=1))
    print(f'{a.id}: {pn["status"]}（直し {pn["attempts"]} 回）')


def cmd_status(a):
    pth, d = load(a.proj)
    cnt = {}
    for p in d['panels']:
        st = p.get('status', 'todo')
        cnt[st] = cnt.get(st, 0) + 1
        print(f'{p["id"]:<5} {st:<10} 直し{p.get("attempts", 0)}回  {p.get("title", "")}')
    print(cnt)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('save'); p.add_argument('proj'); p.add_argument('id'); p.add_argument('src'); p.set_defaults(f=cmd_save)
    p = sp.add_parser('check'); p.add_argument('proj'); p.add_argument('id'); p.set_defaults(f=cmd_check)
    p = sp.add_parser('mark'); p.add_argument('proj'); p.add_argument('id'); p.add_argument('result', choices=['ok', 'ng', 'stop'])
    p.add_argument('--score', type=int); p.add_argument('--note', default=''); p.set_defaults(f=cmd_mark)
    p = sp.add_parser('status'); p.add_argument('proj'); p.set_defaults(f=cmd_status)
    a = ap.parse_args()
    a.f(a)


if __name__ == '__main__':
    main()
