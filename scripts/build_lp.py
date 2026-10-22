#!/usr/bin/env python3
"""漫画LPを lp.json から組み立てる。

  images  <img_dir> <out_images_dir>          確定画像(M00〜, S01〜)を幅800pxのwebpにする（_v1等・P0は除く）
  build   <lp.json> --images <dir> --out <dir> [--mode prod|preview] [--flat]
                                               index.html / thanks.html / privacy-policy.html / style.css を書き出す
                                               preview = 確認用（GTMなし・送信先なし・robots.txt）。--flat は画像を同じ階層に置く（GitHubのWebアップロード用）
  check   <out_dir> [--mode prod|preview]      参照切れ・{{要確認}}の残り・NG語・GTM/送信先の有無を点検
  package <prod_dir> --name <名前> [--dest ~/Desktop]   本番zipと「公開手順.txt」を作る（README.txt を同梱）
  compare <new_site> <benchmark_site>          見本LP（過去の合格LP）と構成を数で比べる（コマ数・図解の割合・章・CTA・注記・設問数）

各自の設定（リポジトリに入れない）：~/.config/manga-lp-auto/config.json（settings.example.json を参照）

lp.json の書き方は references/html_build.md。
"""
import argparse, html, json, os, re, shutil, sys, zipfile
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
TPL = SKILL / 'assets' / 'template'

TOKENS_DEFAULT = {
    'navy': '#14284b', 'navy-2': '#1f3a68', 'ink': '#1c232d', 'sub': '#5b6573', 'line': '#d6dde6',
    'bg': '#eef2f6', 'paper': '#fff', 'soft': '#f3f7fb', 'sky': '#e6f2fc',
    'cta': '#f07a12', 'cta-dark': '#b9580a', 'cta-ink': '#fff',
    'mark': '#ffe55c', 'red': '#e0201b', 'gift': '#c2410c', 'gift-bg': '#fff4ec',
}
TOKEN_ROWS = [['navy', 'navy-2', 'ink', 'sub', 'line'], ['bg', 'paper', 'soft', 'sky'],
              ['cta', 'cta-dark', 'cta-ink'], ['mark', 'red', 'gift', 'gift-bg']]

GTM_HEAD = """<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
})(window,document,'script','dataLayer','%s');</script>
"""
GTM_BODY = '<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=%s" height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>\n'


def img_size(path):
    from PIL import Image
    with Image.open(path) as im:
        return im.size


# ---------------------------------------------------------------- images
def cmd_images(a):
    from PIL import Image
    src, dst = Path(a.src), Path(a.dst)
    dst.mkdir(parents=True, exist_ok=True)
    n = 0
    for p in sorted(src.iterdir()):
        if p.suffix.lower() not in ('.png', '.webp', '.jpg', '.jpeg'):
            continue
        stem = p.stem
        if re.search(r'_v\d+$', stem) or stem.startswith('P0'):
            continue
        out = dst / (stem + '.webp')
        with Image.open(p) as im:
            alpha = im.mode in ('RGBA', 'LA') or 'transparency' in im.info
            im = im.convert('RGBA' if alpha else 'RGB')
            if im.width > a.width:
                im = im.resize((a.width, round(im.height * a.width / im.width)), Image.LANCZOS)
            im.save(out, 'WEBP', quality=a.quality, method=6)
        n += 1
        print(f'{p.name} -> {out.name}')
    print(f'{n} 枚を書き出しました')


# ---------------------------------------------------------------- build
class Builder:
    def __init__(self, cfg, images_dir, mode, flat):
        self.c = cfg
        self.images_dir = Path(images_dir)
        self.mode = mode
        self.prefix = '' if flat else 'images/'
        gift = cfg.get('gift')
        self.gift = gift

    def gtm(self, which):
        g = (self.c.get('tracking') or {}).get('gtm')
        if self.mode != 'prod' or not g:
            return ''
        return (GTM_HEAD if which == 'head' else GTM_BODY) % g

    def gift_html(self, indent):
        g = self.gift
        if not g:
            return ''
        return f'{indent}<div class="gift"><span class="gt">{g["badge"]}</span><b>{g["text"]}</b></div>\n'

    def img_tag(self, file, alt='', lazy=True, extra=''):
        p = self.images_dir / file
        if not p.exists():
            raise SystemExit(f'画像がありません: {p}')
        w, h = img_size(p)
        lz = ' loading="lazy"' if lazy else ''
        return f'<img src="{self.prefix}{file}" width="{w}" height="{h}"{lz} alt="{html.escape(alt, quote=True)}"{extra}>'

    def cta(self, micro, label, sub=False, indent='  '):
        i2 = indent + '  '
        cls = 'btn sub' if sub else 'btn'
        return (f'{indent}<div class="cta">\n' + self.gift_html(i2) +
                (f'{i2}<p class="micro">{micro}</p>\n' if micro else '') +
                f'{i2}<button class="{cls}" type="button" data-go>{label}</button>\n{indent}</div>\n')

    def expand(self, s):
        s = s.replace('{{IMG}}', self.prefix)
        s = s.replace('{{SITE_NAME}}', self.c['site']['name'])

        def gift_rep(m):
            return self.gift_html(m.group(1)).rstrip('\n') if self.gift else ''
        s = re.sub(r'^([ \t]*){{GIFT}}', gift_rep, s, flags=re.M)

        def cta_rep(m):
            ind, body = m.group(1), m.group(2).split('|')
            micro, label = body[0], body[1]
            sub = len(body) > 2 and body[2] == 'sub'
            return self.cta(micro, label, sub, ind).rstrip('\n')
        s = re.sub(r'^([ \t]*){{CTA\|([^}]*)}}', cta_rep, s, flags=re.M)
        return s

    def block(self, b):
        t = b['type']
        out = ''
        if b.get('comment'):
            out += f'<!-- {b["comment"]} -->\n'
        if t == 'koma':
            fv = b.get('fv')
            attrs = ''
            if b.get('id'):
                attrs += f' id="{b["id"]}"'
            if b.get('ch'):
                attrs += f' data-ch="{b["ch"]}"'
            tag = self.img_tag(b['img'], b.get('alt', ''), lazy=not fv, extra=' fetchpriority="high"' if fv else '')
            out += f'<figure class="koma"{attrs}>{tag}</figure>\n'
        elif t == 'note':
            out += f'<p class="note">{b["html"]}</p>\n'
        elif t == 'manga_note':
            out += f'<p class="manga-note">{self.c["site"]["manga_note"]}</p>\n'
        elif t == 'chap':
            out += f'<div class="chap" id="{b["id"]}" data-ch="{b["ch"]}"><span class="q">{b["q"]}</span><p>{b["html"]}</p></div>\n'
        elif t == 'cta':
            tag = b.get('tag', 'section')
            cls = 'sec' + (' ' + b['cls'] if b.get('cls') else '')
            st = f' style="{b["style"]}"' if b.get('style') else ''
            out += f'<{tag} class="{cls}"{st}>\n' + self.cta(b.get('micro', ''), b['label'], b.get('sub', False)) + f'</{tag}>\n'
        elif t == 'html':
            out += self.expand(b['html']).rstrip('\n') + '\n'
        elif t == 'sim':
            s = self.c['sim']
            q1 = self.c['form']['steps'][0]
            out += ('<section class="sim" id="sim" aria-labelledby="simTtl">\n  <div class="sim-card">\n'
                    f'    <p class="sim-ttl" id="simTtl"><small>{s["small"]}</small>{s["title_html"]}</p>\n'
                    '    <div class="sq">\n'
                    f'      <p class="lab"><i>Q1</i>{q1["q"]}</p>\n' +
                    (f'      <p class="sim-note">{q1["note"]}</p>\n' if q1.get('note') else '') +
                    '      <div class="opts cards" id="simQ1"></div>\n    </div>\n'
                    f'    <p class="sim-hint">{s["hint_html"]}</p>\n' + self.gift_html('    ') +
                    '  </div>\n</section>\n')
        elif t == 'final':
            out += ('<div class="final">\n  ' + self.img_tag(b['img'], '') +
                    f'\n  <div class="over"><p>{b["html"]}</p></div>\n</div>\n')
        elif t == 'faq':
            out += (f'<section class="sec">\n  <p class="hd sm">{b.get("title", "よくあるご質問")}</p>\n'
                    '  <div id="faq" style="display:grid;gap:6px"></div>\n</section>\n')
        elif t == 'form':
            f = self.c['form']
            nq = len(f['steps'])
            out += ('<section class="sec sky" id="form" data-ch="form">\n'
                    f'  <p class="hd">{f["heading_html"]}</p>\n' + self.gift_html('  ') +
                    '  <form class="form" id="dxForm" novalidate>\n'
                    '    <div class="prog" aria-hidden="true"><i id="progBar"></i></div>\n'
                    f'    <p class="step-lab" id="stepLab">Q1 / {nq}</p>\n'
                    '    <div id="stepArea" style="display:grid;gap:12px"></div>\n'
                    '    <div class="hp" aria-hidden="true"><label>ウェブサイト<input type="text" id="in-website" tabindex="-1" autocomplete="off"></label></div>\n'
                    '  </form>\n')
            if f.get('trust'):
                out += f'  <p class="trust">{f["trust"]}</p>\n'
            if f.get('details'):
                d = f['details']
                out += f'  <details class="acc"><summary>{d["summary"]}</summary><div class="in" style="font-size:12px">\n'
                for it in d['items']:
                    out += f'    <span>{it}</span>\n'
                out += '  </div></details>\n'
            if f.get('fine'):
                out += f'  <p class="fine" style="text-align:center">{f["fine"]}</p>\n'
            out += '</section>\n'
        elif t == 'blank':
            pass
        else:
            raise SystemExit(f'不明なブロック: {t}')
        if b.get('gap', True) and t != 'blank':
            pass
        return out + ('\n' if b.get('after_blank') else '')

    def tokens(self):
        tk = dict(TOKENS_DEFAULT)
        tk.update(self.c.get('colors') or {})
        rows = ['  color-scheme:light;']
        for r in TOKEN_ROWS:
            rows.append('  ' + ' '.join(f'--{k}:{tk[k]};' for k in r))
        rows.append('  --f:"Noto Sans JP","Hiragino Sans","Hiragino Kaku Gothic ProN","Yu Gothic",sans-serif;')
        rows.append('  --w:480px;')
        extra = [k for k in tk if k not in TOKENS_DEFAULT]
        if extra:
            rows.append('  ' + ' '.join(f'--{k}:{tk[k]};' for k in extra))
        return ':root{\n' + '\n'.join(rows) + '\n}', tk

    def js_cfg(self):
        f = self.c['form']
        prod = self.mode == 'prod'
        cfg = {
            'faq': self.c.get('faq', []),
            'steps': f['steps'],
            'contactTitle': f.get('contact_title', '診断結果を確認する'),
            'submitLabel': f.get('submit_label', '結果をみる →'),
            'prefs': f['prefs'],
            'plan': f.get('plan', {}),
            'planDefault': f.get('plan_default', ''),
            'formId': f['form_id'],
            'payloadTitle': f['payload_title'],
            'gasUrl': f.get('gas_url', '') if prod else '',
            'mailEndpoint': f.get('mail_endpoint', 'mail.php') if prod else '',
            'prodHostRe': '(^|\\.)' + re.escape(self.c['site']['prod_host']) + '$',
            'preview': not prod,
        }
        return 'const CFG = ' + json.dumps(cfg, ensure_ascii=False, indent=1) + ';'

    def index(self):
        s = self.c['site']
        css = (TPL / 'manga.css').read_text()
        root, _ = self.tokens()
        css = css.replace('/*TOKENS*/', root)
        first = next(b for b in self.c['blocks'] if b['type'] == 'koma')
        note = (self.c.get('tracking') or {}).get('gtm_note')
        gh = self.gtm('head')
        if gh and note:
            gh = f'<!-- {note} -->\n' + gh
        main = ''.join(self.block(b) for b in self.c['blocks'])
        sticky = ''
        st = self.c.get('sticky')
        if st:
            sticky = ('<div class="sticky" id="sticky">\n' +
                      (f'  <p>{self.gift["sticky"]}</p>\n' if self.gift and self.gift.get('sticky') else '') +
                      f'  <button class="btn" type="button" data-go>{st["label"]}</button>\n</div>\n\n')
        js = (TPL / 'lp.js').read_text().replace('/*CFG*/', self.js_cfg())
        return f'''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
{gh}<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{s["title"]}</title>
<meta name="description" content="{html.escape(s["description"], quote=True)}">
<meta name="robots" content="noindex">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap">
<link rel="preload" as="image" href="{self.prefix}{first["img"]}">
<style>
{css}</style>
</head>
<body>
{self.gtm('body')}
<div class="page">

<header class="hdr">
  <a class="logo" href="#top" id="top">{s["name"]}<small>{s["tagline"]}</small></a>
  <button class="mini" type="button" data-go>{s.get("header_button", "無料診断")}</button>
</header>

<main>

{main}
</main>
<footer class="foot"><a href="privacy-policy.html">プライバシーポリシー</a><br>{s.get("footer", "© " + s["name"])}</footer>
</div>

{sticky}<script>
{js}</script>
</body>
</html>
'''

    def thanks(self):
        s, t = self.c['site'], self.c['thanks']
        _, tk = self.tokens()
        tok = ':root{color-scheme:light;' + ''.join(f'--{k}:{tk[k]};' for k in ['navy', 'ink', 'sub', 'line', 'bg', 'soft', 'cta', 'red', 'mark', 'gift', 'gift-bg'])
        tok = tok.rstrip(';') + '}'
        T = dict(t)
        if T.get('pairImg'):
            T['pairImg'] = self.prefix + T['pairImg']
        js = (TPL / 'thanks.js').read_text().replace('/*CFG*/', 'const T = ' + json.dumps(T, ensure_ascii=False, indent=1) + ';')
        out = (TPL / 'thanks.tmpl.html').read_text()
        rep = {'{{GTM_HEAD}}': self.gtm('head'), '{{GTM_BODY}}': self.gtm('body'), '{{THANKS_TITLE}}': t['title'],
               '{{THANKS_TOKENS}}': tok, '{{SITE_NAME}}': s['name'], '{{TAGLINE}}': s['tagline'], '{{THANKS_JS}}': js.rstrip('\n')}
        for k, v in rep.items():
            out = out.replace(k, v)
        return out

    def privacy(self):
        p = self.c.get('privacy') or {}
        if p.get('file'):
            src = Path(p['file']).expanduser().read_text()
            if self.mode != 'prod':  # 確認用はGTMを外す
                src = re.sub(r'<!-- Google Tag Manager -->.*?<!-- End Google Tag Manager -->\n', '', src, flags=re.S)
                src = re.sub(r'<!-- Google Tag Manager \(noscript\) -->.*?<!-- End Google Tag Manager \(noscript\) -->\n', '', src, flags=re.S)
            return src
        out = (TPL / 'privacy-policy.tmpl.html').read_text()
        g = (self.c.get('tracking') or {}).get('gtm')
        gh = gb = ''
        if self.mode == 'prod' and g:
            gh = '<!-- Google Tag Manager -->\n' + GTM_HEAD % g + '<!-- End Google Tag Manager -->\n'
            gb = ('<!-- Google Tag Manager (noscript) -->\n<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=%s"\n'
                  'height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>\n<!-- End Google Tag Manager (noscript) -->\n') % g
        op = ''.join(f'  <div class="footer-mini">{x}</div>\n' for x in p.get('operator', ['{{要確認：運営者の屋号}}', '{{要確認：運営者の住所}}']))
        for k, v in {'{{GTM_HEAD}}': gh, '{{GTM_BODY}}': gb, '{{OPERATOR}}': op, '{{BACK_LABEL}}': p.get('back_label', '← 診断ページに戻る')}.items():
            out = out.replace(k, v)
        return out


def cmd_build(a):
    cfg = json.loads(Path(a.config).read_text())
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    b = Builder(cfg, a.images, a.mode, a.flat)
    (out / 'index.html').write_text(b.index())
    (out / 'thanks.html').write_text(b.thanks())
    (out / 'privacy-policy.html').write_text(b.privacy())
    shutil.copy(TPL / 'style.css', out / 'style.css')
    img_out = out if a.flat else out / 'images'
    img_out.mkdir(exist_ok=True)
    used = set(re.findall(r'(?:src|href)="(?:images/)?([A-Za-z0-9_\-]+\.webp)"', (out / 'index.html').read_text()))
    if cfg.get('thanks', {}).get('pairImg'):
        used.add(cfg['thanks']['pairImg'])
    for f in sorted(used):
        shutil.copy(Path(a.images) / f, img_out / f)
    if a.mode == 'preview':
        (out / 'robots.txt').write_text('User-agent: *\nDisallow: /\n')
    print(f'書き出し：{out}（{a.mode}{"・flat" if a.flat else ""}／画像 {len(used)} 枚）')


# ---------------------------------------------------------------- check
def settings():
    p = Path.home() / '.config/manga-lp-auto/config.json'
    return json.loads(p.read_text()) if p.exists() else {}


def load_ng():
    words = []
    extra = [Path(x).expanduser() for x in settings().get('extra_ng_files', [])]
    for p in [SKILL / 'references' / 'ng_words.txt'] + extra:
        if p.exists():
            for line in p.read_text().splitlines():
                w = line.split('#')[0].strip()
                if w:
                    words.append(w)
    return words


def cmd_check(a):
    out = Path(a.out)
    probs, warns = [], []
    pages = {p.name: p.read_text() for p in out.glob('*.html')}
    for name, src in pages.items():
        for ref in re.findall(r'(?:src|href)="([^"#:]+\.(?:webp|png|jpg|css|html))"', src):
            if not (out / ref).exists():
                probs.append(f'{name}: 参照切れ {ref}')
        for m in re.findall(r'{{[^}]*}}', src):
            probs.append(f'{name}: 未記入 {m}')
        has_gtm = 'googletagmanager.com/gtm.js' in src
        if a.mode == 'preview' and has_gtm:
            probs.append(f'{name}: 確認用なのにGTMが入っている')
        if a.mode == 'prod' and not has_gtm:
            warns.append(f'{name}: GTMが入っていない（意図どおりか確認）')
        if a.mode == 'preview' and re.search(r'script\.google\.com/macros', src):
            probs.append(f'{name}: 確認用なのに送信先(GAS URL)が入っている')
    idx = pages.get('index.html', '')
    text = re.sub(r'<script.*?</script>|<style.*?</style>', '', idx, flags=re.S)
    text = re.sub(r'<[^>]+>', '', text)
    for w in load_ng():
        if w in text:
            warns.append(f'NG候補「{w}」が本文にある（根拠・注記を確認）')
    for alt in re.findall(r'<img [^>]*alt=""', idx):
        pass
    if a.mode == 'prod' and '"gasUrl": ""' in idx:
        warns.append('本番なのに送信先(GAS URL)が空')
    print('■ 必ず直す' if probs else '■ 必ず直す：なし')
    for p in probs:
        print('  - ' + p)
    print('■ 確認' if warns else '■ 確認：なし')
    for w in warns:
        print('  - ' + w)
    sys.exit(1 if probs else 0)


# ---------------------------------------------------------------- package
def cmd_package(a):
    src = Path(a.src)
    dest = Path(a.dest).expanduser()
    z = dest / f'{a.name}.zip'
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(src.rglob('*')):
            if p.name.startswith('.'):
                continue
            zf.write(p, Path(src.name) / p.relative_to(src))
    readme = src / 'README.txt'
    if readme.exists():
        shutil.copy(readme, dest / f'{a.name}_公開手順.txt')
    print(f'作成：{z}' + (f' / {dest / (a.name + "_公開手順.txt")}' if readme.exists() else '（README.txt が無いので公開手順は未作成）'))


def page_stats(site):
    site = Path(site)
    src = (site / 'index.html').read_text()
    imgdir = site / 'images' if (site / 'images').exists() else site
    komas = re.findall(r'<figure class="koma"[^>]*><img src="(?:images/)?([^"]+)"', src)
    tall = 0
    for f in komas:
        try:
            w, h = img_size(imgdir / f)
            tall += h > w
        except Exception:
            pass
    steps = re.search(r'id="stepLab">Q1 / (\d+)<', src)
    body = re.sub(r'<script.*?</script>|<style.*?</style>', '', src, flags=re.S)
    return {
        'コマ（画像）': len(komas),
        '縦長の図解・FV': tall,
        '章見出し': len(re.findall(r'class="chap"', src)),
        'CTAボタン（固定ボタン含む）': len(re.findall(r'data-go>', src)),
        '画像下の注記': len(re.findall(r'class="note"', src)),
        '漫画の注記（架空）': len(re.findall(r'class="manga-note"', src)),
        'HTMLの区切り（表・事例など）': len(re.findall(r'<section class="sec', src)),
        'シミュレーター': int('id="simQ1"' in src),
        'フォームの設問': int(steps.group(1)) if steps else 0,
        '本文の文字数': len(re.sub(r'<[^>]+>|\s', '', body)),
    }


def cmd_compare(a):
    n, b = page_stats(a.new), page_stats(a.bench)
    print('| 項目 | 今回 | 見本 | 判定 |\n|---|---|---|---|')
    for k in n:
        nv, bv = n[k], b[k]
        ok = '○' if nv >= bv * 0.8 or k in ('フォームの設問',) else '△ 少ない'
        if k == 'フォームの設問':
            ok = '○' if nv == bv else '確認（既存の診断LPとそろえる）'
        print(f'| {k} | {nv} | {bv} | {ok} |')
    print('\n数は目安。流れ・章ごとのCTA・引き継ぎ・文字の大きさ・注記の中身は references/benchmark_review.md で目で比べる')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('images'); p.add_argument('src'); p.add_argument('dst'); p.add_argument('--width', type=int, default=800); p.add_argument('--quality', type=int, default=82); p.set_defaults(f=cmd_images)
    p = sp.add_parser('build'); p.add_argument('config'); p.add_argument('--images', required=True); p.add_argument('--out', required=True)
    p.add_argument('--mode', choices=['prod', 'preview'], default='prod'); p.add_argument('--flat', action='store_true'); p.set_defaults(f=cmd_build)
    p = sp.add_parser('check'); p.add_argument('out'); p.add_argument('--mode', choices=['prod', 'preview'], default='prod'); p.set_defaults(f=cmd_check)
    p = sp.add_parser('compare'); p.add_argument('new'); p.add_argument('bench'); p.set_defaults(f=cmd_compare)
    p = sp.add_parser('package'); p.add_argument('src'); p.add_argument('--name', required=True); p.add_argument('--dest', default='~/Desktop'); p.set_defaults(f=cmd_package)
    a = ap.parse_args()
    a.f(a)


if __name__ == '__main__':
    main()
