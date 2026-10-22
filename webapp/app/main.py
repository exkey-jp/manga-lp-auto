"""漫画LP 自動制作 Webアプリ。URLを開く → ログイン → 入力 → 裏で自動制作 → 要所で承認 → 確認用URLとzip。"""
import hmac
import json
import shutil
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import config as C
from .jobs import Job, all_jobs, enqueue, start_worker
from .pipeline import LABELS, run

app = FastAPI(title='漫画LP 自動制作')
app.add_middleware(SessionMiddleware, secret_key=C.SECRET_KEY, https_only=C.APP_BASE_URL.startswith('https'), max_age=60 * 60 * 24 * 14)
T = Jinja2Templates(directory=str(Path(__file__).parent / 'templates'))
STEPS = ['capture', 'plan', 'chara', 'panels', 'build', 'review', 'package', 'done']


@app.on_event('startup')
def _start():
    C.DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not C.APP_PASSWORD:
        raise RuntimeError('APP_PASSWORD を設定してください（社内用ログインのパスワード）')
    start_worker(run)


def user(request):
    u = request.session.get('user')
    if not u:
        raise HTTPException(303, headers={'Location': '/login'})
    return u


def job_or_404(jid):
    if '/' in jid or '..' in jid:
        raise HTTPException(404)
    j = Job(jid)
    if not j.state:
        raise HTTPException(404)
    return j


def page(request, name, **ctx):
    return T.TemplateResponse(request, name, {'user': request.session.get('user'), 'mock': C.MOCK, **ctx})


# ------------------------------------------------------------------ ログイン
@app.get('/login', response_class=HTMLResponse)
def login_form(request: Request):
    return page(request, 'login.html', error=None)


@app.post('/login')
def login(request: Request, name: str = Form(...), password: str = Form(...)):
    if not hmac.compare_digest(password.encode(), C.APP_PASSWORD.encode()):
        return page(request, 'login.html', error='パスワードが違います')
    request.session['user'] = name.strip()[:40] or 'user'
    return RedirectResponse('/', 303)


@app.get('/logout')
def logout(request: Request):
    request.session.clear()
    return RedirectResponse('/login', 303)


# ------------------------------------------------------------------ 一覧・新規
@app.get('/', response_class=HTMLResponse)
def index(request: Request):
    user(request)
    return page(request, 'index.html', jobs=all_jobs()[:50], labels=LABELS)


@app.get('/new', response_class=HTMLResponse)
def new_form(request: Request):
    user(request)
    return page(request, 'new.html')


FIELDS = ['client', 'product', 'ref_url', 'site_url', 'strategy_url', 'diag_url', 'area', 'numbers', 'offer',
          'prod_host', 'form_id', 'gas_url', 'mail_endpoint', 'gtm', 'notes']


@app.post('/new')
async def new(request: Request):
    u = user(request)
    f = await request.form()
    inputs = {k: (f.get(k) or '').strip() for k in FIELDS}
    if not inputs['client'] or not inputs['ref_url'].startswith('http'):
        return page(request, 'new.html', error='クライアント名と参考LPのURLは必須です', v=inputs)
    j = Job.create(inputs, u)
    j.log(f'{u} が作成')
    enqueue(j.id)
    return RedirectResponse(f'/jobs/{j.id}', 303)


# ------------------------------------------------------------------ 進捗・承認
@app.get('/jobs/{jid}', response_class=HTMLResponse)
def job_page(request: Request, jid: str):
    user(request)
    j = job_or_404(jid)
    pj = json.loads((j.dir / 'panels.json').read_text()) if (j.dir / 'panels.json').exists() else None
    files = {p.name for p in (j.dir / 'img').glob('*')} if (j.dir / 'img').exists() else set()
    for p in (pj or {}).get('panels', []):
        p['img'] = next((f'{p["file"]}{e}' for e in ('.png', '.webp', '.jpg') if f'{p["file"]}{e}' in files), None)
        q = j.dir / 'qa' / p['id']
        js = sorted(q.glob('judge_v*.json')) if q.exists() else []
        p['judge'] = json.loads(js[-1].read_text()) if js else None
    kakunin = (j.dir / '要確認リスト.md').read_text() if (j.dir / '要確認リスト.md').exists() else ''
    story = (j.dir / 'プロンプト集.md').read_text() if (j.dir / 'プロンプト集.md').exists() else ''
    return page(request, 'job.html', j=j, s=j.state, pj=pj, steps=STEPS, labels=LABELS, kakunin=kakunin, story=story,
                screens=sorted(p.name for p in (j.dir / 'qa' / 'screens').glob('*.png')) if (j.dir / 'qa' / 'screens').exists() else [])


@app.get('/api/jobs/{jid}')
def job_json(request: Request, jid: str):
    user(request)
    j = job_or_404(jid)
    s = j.state
    return {'status': s.get('status'), 'stage': s.get('stage'), 'waiting': s.get('waiting'), 'cost': s.get('cost'), 'log': s.get('log', [])[-5:]}


def resume(j, stage=None, **kw):
    j.set(status='queued', waiting=None, **({'stage': stage} if stage else {}), **kw)
    enqueue(j.id)


@app.post('/jobs/{jid}/plan')
def gate_plan(request: Request, jid: str, action: str = Form(...), feedback: str = Form('')):
    u = user(request)
    j = job_or_404(jid)
    if j.state.get('waiting') != 'plan':
        raise HTTPException(409, '構成の確認待ちではありません')
    if action == 'approve':
        j.log(f'{u} が構成を承認')
        resume(j, 'chara')
    else:
        j.log(f'{u} が構成に修正指示：{feedback[:80]}')
        resume(j, 'plan', plan_feedback=j.state.get('plan_feedback', []) + [feedback])
    return RedirectResponse(f'/jobs/{jid}', 303)


@app.post('/jobs/{jid}/chara')
def gate_chara(request: Request, jid: str, action: str = Form(...), feedback: str = Form('')):
    u = user(request)
    j = job_or_404(jid)
    if j.state.get('waiting') != 'chara':
        raise HTTPException(409, '設定シートの確認待ちではありません')
    if action == 'approve':
        j.log(f'{u} が設定シートを承認')
        resume(j, 'panels')
    else:
        j.log(f'{u} が設定シートに修正指示：{feedback[:80]}')
        resume(j, 'chara', chara_feedback=feedback)
    return RedirectResponse(f'/jobs/{jid}', 303)


@app.post('/jobs/{jid}/panel/{pid}')
async def gate_panel(request: Request, jid: str, pid: str):
    u = user(request)
    j = job_or_404(jid)
    f = await request.form()
    action = f.get('action')
    from .pipeline import update_panel, get_panel
    pj, p = get_panel(j, pid)
    if action == 'accept':
        update_panel(j, pid, status='accepted')
        j.log(f'{u} が {pid} をこのまま採用')
    elif action == 'retry':
        update_panel(j, pid, status='todo', attempts=0, human_feedback=f.get('feedback', ''))
        j.log(f'{u} が {pid} に指示して作り直し：{(f.get("feedback") or "")[:60]}')
    elif action == 'upload':
        up: UploadFile = f.get('file')
        if not up or not up.filename:
            raise HTTPException(400, '画像を選んでください')
        ext = Path(up.filename).suffix.lower()
        if ext not in ('.png', '.webp', '.jpg', '.jpeg'):
            raise HTTPException(400, 'png / webp / jpg を選んでください')
        cur = next((j.dir / 'img' / f'{p["file"]}{e}' for e in ('.png', '.webp', '.jpg') if (j.dir / 'img' / f'{p["file"]}{e}').exists()), None)
        if cur:
            from .pipeline import backup
            backup(cur)
            cur.unlink()
        dst = j.dir / 'img' / f'{p["file"]}{".jpg" if ext == ".jpeg" else ext}'
        dst.write_bytes(await up.read())
        update_panel(j, pid, status='accepted')
        j.log(f'{u} が {pid} の画像を差し替え')
    return RedirectResponse(f'/jobs/{jid}#panels', 303)


@app.post('/jobs/{jid}/continue')
def gate_continue(request: Request, jid: str):
    u = user(request)
    j = job_or_404(jid)
    j.log(f'{u} が再開')
    if j.state.get('status') in ('waiting', 'failed'):
        resume(j)
    return RedirectResponse(f'/jobs/{jid}', 303)


@app.post('/jobs/{jid}/budget')
def gate_budget(request: Request, jid: str, add: int = Form(5000)):
    u = user(request)
    j = job_or_404(jid)
    j.set(budget_jpy=j.state.get('budget_jpy', C.JOB_BUDGET_JPY) + max(0, min(add, 50000)))
    j.log(f'{u} が上限を {j.state["budget_jpy"]:,}円 に変更')
    if j.state.get('waiting') == 'budget':
        resume(j)
    return RedirectResponse(f'/jobs/{jid}', 303)


# ------------------------------------------------------------------ ファイル
def safe(base: Path, rel: str):
    p = (base / rel).resolve()
    if not str(p).startswith(str(base.resolve())) or not p.is_file():
        raise HTTPException(404)
    return p


@app.get('/files/{jid}/{rel:path}')
def files(request: Request, jid: str, rel: str):
    user(request)
    return FileResponse(safe(job_or_404(jid).dir, rel))


@app.get('/preview/{jid}/{rel:path}')
def preview(request: Request, jid: str, rel: str):
    user(request)
    return FileResponse(safe(job_or_404(jid).dir / 'preview', rel or 'index.html'))


@app.get('/download/{jid}')
def download(request: Request, jid: str):
    user(request)
    j = job_or_404(jid)
    if not j.state.get('zip'):
        raise HTTPException(404)
    p = safe(j.dir, j.state['zip'])
    return FileResponse(p, filename=p.name)


@app.get('/healthz')
def health():
    return {'ok': True, 'mock': C.MOCK}
