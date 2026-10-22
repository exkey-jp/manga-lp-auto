#!/usr/bin/env python3
"""ChatGPTの画面操作が止まったときの予備：OpenAI の画像APIで1枚作る／直す。

  gen   --prompt-file p.txt --size 1536x1024 --out img/M01_shock.png [--ref img/P0_chara.png ...] [--transparent]
  edit  --image img/M14_kaishu.png --prompt-file fix.txt --out <dl>/M14.png [--ref img/P0_chara.png] [--transparent]

- 共通ルール（rules.txt）は --rules で毎回先頭につける（APIは会話を覚えないため）
- キャラを固定するため、人物が出るコマは --ref でキャラクター設定シートを必ず渡す（edits エンドポイントに参照画像として送る）
- キー：環境変数 OPENAI_API_KEY（無ければ ~/.config/manga-lp-auto/openai_key の1行）。キーの作成・入力は人がする
- モデル：環境変数 OPENAI_IMAGE_MODEL（既定 gpt-image-1）。1枚あたりの料金は OpenAI の料金表で確認（高画質の横長で数十円程度）
- 書き出しはPNG。保存後は panel_tool.py save で案件の img/ に入れる
"""
import argparse, base64, os, sys
from pathlib import Path

API = 'https://api.openai.com/v1/images'


def key():
    k = os.environ.get('OPENAI_API_KEY')
    if not k:
        p = Path.home() / '.config/manga-lp-auto/openai_key'
        if p.exists():
            k = p.read_text().strip()
    if not k:
        sys.exit('OPENAI_API_KEY がありません。人に設定してもらってください（このスクリプトはキーを作りません）')
    return k


def prompt_text(a):
    t = Path(a.prompt_file).read_text()
    if a.rules:
        t = Path(a.rules).read_text().strip() + '\n\n---\n\n' + t
    return t


def save(resp, out):
    import requests  # noqa
    if resp.status_code != 200:
        sys.exit(f'APIエラー {resp.status_code}: {resp.text[:500]}')
    data = resp.json()['data'][0]
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_bytes(base64.b64decode(data['b64_json']))
    print(f'保存：{out}')


def common(a):
    d = {'model': os.environ.get('OPENAI_IMAGE_MODEL', 'gpt-image-1'), 'size': a.size, 'quality': a.quality, 'n': '1'}
    if a.transparent:
        d['background'] = 'transparent'
        d['output_format'] = 'png'
    return d


def cmd_gen(a):
    import requests
    h = {'Authorization': f'Bearer {key()}'}
    d = common(a)
    d['prompt'] = prompt_text(a)
    if a.ref:  # 参照画像つき → edits（参照画像を見ながら新しく描く）
        files = [('image[]', (Path(r).name, open(r, 'rb'), mime(r))) for r in a.ref]
        r = requests.post(f'{API}/edits', headers=h, data=d, files=files, timeout=600)
    else:
        d['n'] = 1
        r = requests.post(f'{API}/generations', headers={**h, 'Content-Type': 'application/json'}, json=d, timeout=600)
    save(r, a.out)


def cmd_edit(a):
    import requests
    h = {'Authorization': f'Bearer {key()}'}
    d = common(a)
    d['prompt'] = prompt_text(a)
    paths = [a.image] + (a.ref or [])
    files = [('image[]', (Path(p).name, open(p, 'rb'), mime(p))) for p in paths]
    r = requests.post(f'{API}/edits', headers=h, data=d, files=files, timeout=600)
    save(r, a.out)


def mime(p):
    return {'.png': 'image/png', '.webp': 'image/webp', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}[Path(p).suffix.lower()]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    for name, f in (('gen', cmd_gen), ('edit', cmd_edit)):
        p = sp.add_parser(name)
        if name == 'edit':
            p.add_argument('--image', required=True)
        p.add_argument('--prompt-file', required=True)
        p.add_argument('--rules', help='共通ルールのテキスト（毎回先頭につける）')
        p.add_argument('--size', default='1536x1024', choices=['1024x1024', '1536x1024', '1024x1536'])
        p.add_argument('--quality', default='high', choices=['low', 'medium', 'high'])
        p.add_argument('--ref', action='append')
        p.add_argument('--transparent', action='store_true')
        p.add_argument('--out', required=True)
        p.set_defaults(f=f)
    a = ap.parse_args()
    a.f(a)


if __name__ == '__main__':
    main()
