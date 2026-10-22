"""Claude（構成・点検・採点・HTML設定）と OpenAI 画像API（コマ生成）の呼び出し。費用はジョブごとに記録する。"""
import base64
import io
import json
import re
import threading
from pathlib import Path

from . import config as C

_lock = threading.Lock()


class BudgetExceeded(Exception):
    pass


class Cost:
    """ジョブの費用（円）を数える。上限を超えたら BudgetExceeded。"""

    def __init__(self, job):
        self.job = job

    def add(self, kind, usd, detail=''):
        with _lock:
            c = self.job.state.setdefault('cost', {'claude_jpy': 0, 'image_jpy': 0, 'images': 0, 'claude_calls': 0})
            jpy = usd * C.USD_JPY
            if kind == 'claude':
                c['claude_jpy'] += jpy
                c['claude_calls'] += 1
            else:
                c['image_jpy'] += jpy
                c['images'] += 1
            c['total_jpy'] = round(c['claude_jpy'] + c['image_jpy'])
            self.job.save()
            budget = self.job.state.get('budget_jpy', C.JOB_BUDGET_JPY)
            if c['total_jpy'] > budget:
                raise BudgetExceeded(f'費用が上限（{budget:,.0f}円）を超えました：{c["total_jpy"]:,}円')


# ------------------------------------------------------------------ Claude
_client = None


def claude():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic()   # ANTHROPIC_API_KEY を環境変数から読む
    return _client


def image_block(path, max_side=1568):
    """画像をClaudeに渡す形にする（長辺を縮めてPNG）。"""
    from PIL import Image
    im = Image.open(path)
    im = im.convert('RGBA') if im.mode in ('RGBA', 'LA', 'P') else im.convert('RGB')
    if max(im.size) > max_side:
        r = max_side / max(im.size)
        im = im.resize((round(im.width * r), round(im.height * r)))
    buf = io.BytesIO()
    im.save(buf, 'PNG')
    return {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png',
                                        'data': base64.standard_b64encode(buf.getvalue()).decode()}}


def ask_json(cost, system, content, schema=None, max_tokens=64000, effort=None, mock=None):
    """Claude に聞いて JSON を返す。
    schema あり → structured outputs（json_schema）で必ずその形。schema なし → 本文の最初の JSON を取り出す。
    system は毎回同じ文字列にしてキャッシュを効かせる（参照資料は system に入れる）。"""
    if C.MOCK:
        return mock() if mock else {}
    import anthropic
    oc = {'effort': effort or C.CLAUDE_EFFORT}
    if schema:
        oc['format'] = {'type': 'json_schema', 'schema': schema}
    with claude().beta.messages.stream(
        model=C.CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=[{'type': 'text', 'text': system, 'cache_control': {'type': 'ephemeral'}}],
        messages=[{'role': 'user', 'content': content}],
        thinking={'type': 'adaptive'},
        output_config=oc,
        betas=['server-side-fallback-2026-07-01'],
        fallbacks='default',      # 安全判定で断られたときは推奨モデルで自動的にやり直す
    ) as stream:
        msg = stream.get_final_message()
    u = msg.usage
    usd = ((u.input_tokens or 0) * C.PRICE_CLAUDE_IN + (u.output_tokens or 0) * C.PRICE_CLAUDE_OUT
           + (getattr(u, 'cache_read_input_tokens', 0) or 0) * C.PRICE_CLAUDE_CACHE_READ
           + (getattr(u, 'cache_creation_input_tokens', 0) or 0) * C.PRICE_CLAUDE_CACHE_WRITE) / 1e6
    cost.add('claude', usd)
    if msg.stop_reason == 'refusal':
        raise RuntimeError('Claude が回答を断りました（refusal）。入力内容を確認してください')
    if msg.stop_reason == 'max_tokens':
        raise RuntimeError('Claude の出力が長すぎて途中で切れました')
    text = ''.join(b.text for b in msg.content if b.type == 'text')
    if schema:
        return json.loads(text)
    m = re.search(r'```json\s*(.*?)```', text, re.S)
    raw = m.group(1) if m else text[text.find('{'): text.rfind('}') + 1]
    return json.loads(raw)


# ------------------------------------------------------------------ OpenAI 画像
_oa = None


def openai_client():
    global _oa
    if _oa is None:
        import openai
        _oa = openai.OpenAI()   # OPENAI_API_KEY を環境変数から読む
    return _oa


def _image_cost(resp):
    u = getattr(resp, 'usage', None)
    if not u:
        return C.PRICE_IMG_FALLBACK
    d = getattr(u, 'input_tokens_details', None)
    text_in = getattr(d, 'text_tokens', 0) if d else 0
    img_in = getattr(d, 'image_tokens', 0) if d else 0
    out = getattr(u, 'output_tokens', 0) or 0
    return (text_in * C.PRICE_IMG_TEXT_IN + img_in * C.PRICE_IMG_IMAGE_IN + out * C.PRICE_IMG_OUT) / 1e6


def make_image(cost, prompt, size, out_path, refs=(), transparent=False, mock_label=''):
    """1枚作って out_path（PNG）に保存。refs があれば参照画像つき（edits）で、人物や前の版を保つ。"""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if C.MOCK:
        _mock_image(prompt, size, out_path, transparent, mock_label)
        return out_path
    kw = dict(model=C.IMAGE_MODEL, prompt=prompt, size=size, quality=C.IMAGE_QUALITY, n=1, output_format='png')
    if transparent:
        kw['background'] = 'transparent'
    oa = openai_client()
    if refs:
        files = [open(r, 'rb') for r in refs]
        try:
            resp = oa.images.edit(image=files, input_fidelity='high', **kw)
        finally:
            for f in files:
                f.close()
    else:
        resp = oa.images.generate(**kw)
    cost.add('image', _image_cost(resp))
    out_path.write_bytes(base64.b64decode(resp.data[0].b64_json))
    return out_path


def _mock_image(prompt, size, out_path, transparent, label):
    from PIL import Image, ImageDraw, ImageFont
    w, h = [int(x) for x in size.split('x')]
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0) if transparent else (235, 240, 250, 255))
    d = ImageDraw.Draw(im)
    if transparent:
        d.ellipse((w * .3, h * .2, w * .7, h * .95), fill=(250, 200, 170, 255))
    else:
        d.rectangle((4, 4, w - 5, h - 5), outline=(30, 30, 30, 255), width=6)
    font = None
    for f in ['/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc', '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc']:
        try:
            font = ImageFont.truetype(f, 48)
            break
        except Exception:
            pass
    d.text((w / 2, h / 2), f'（仮）{label}', font=font, fill=(20, 30, 50, 255), anchor='mm')
    im.save(out_path, 'PNG')
