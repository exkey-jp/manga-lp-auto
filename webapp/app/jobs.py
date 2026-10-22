"""ジョブ（1件のLP制作）の状態を data/<id>/job.json に持つ。処理は1本の裏方スレッドが順番に進める。"""
import json
import queue
import secrets
import threading
import time
import traceback
from pathlib import Path

from . import config as C

_locks = {}
_q = queue.Queue()


class Job:
    def __init__(self, jid):
        self.id = jid
        self.dir = C.DATA_DIR / jid
        self.path = self.dir / 'job.json'
        self.lock = _locks.setdefault(jid, threading.RLock())
        self.state = json.loads(self.path.read_text()) if self.path.exists() else {}

    @classmethod
    def create(cls, inputs, user):
        jid = time.strftime('%Y%m%d-%H%M%S-') + secrets.token_hex(3)
        j = cls(jid)
        j.dir.mkdir(parents=True, exist_ok=True)
        j.state = {'id': jid, 'inputs': inputs, 'user': user, 'created': time.strftime('%Y-%m-%d %H:%M'),
                   'stage': 'capture', 'status': 'queued', 'log': [], 'budget_jpy': C.JOB_BUDGET_JPY}
        j.save()
        return j

    def save(self):
        with self.lock:
            tmp = self.path.with_suffix('.tmp')
            tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=1))
            tmp.replace(self.path)

    def log(self, msg):
        with self.lock:
            self.state.setdefault('log', []).append({'at': time.strftime('%m/%d %H:%M:%S'), 'msg': msg})
            self.state['log'] = self.state['log'][-300:]
            self.save()

    def set(self, **kw):
        with self.lock:
            self.state.update(kw)
            self.save()

    @property
    def name(self):
        return self.state.get('inputs', {}).get('client', self.id)


def all_jobs():
    if not C.DATA_DIR.exists():
        return []
    out = [Job(p.name) for p in sorted(C.DATA_DIR.iterdir(), reverse=True) if (p / 'job.json').exists()]
    return out


def enqueue(jid):
    _q.put(jid)


def start_worker(run_fn):
    """裏方スレッド。起動時に途中だったジョブ（running / queued）を積み直す。"""
    for j in all_jobs():
        if j.state.get('status') in ('running', 'queued'):
            j.set(status='queued')
            _q.put(j.id)

    def loop():
        while True:
            jid = _q.get()
            j = Job(jid)
            if j.state.get('status') not in ('queued',):
                continue
            try:
                j.set(status='running')
                run_fn(j)
            except Exception as e:  # 想定外の失敗は止めて人に知らせる
                j.log('止まりました：' + str(e))
                j.set(status='failed', error=str(e), trace=traceback.format_exc()[-3000:])
                from .notify import notify
                notify(j, f'止まりました：{e}')
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t
