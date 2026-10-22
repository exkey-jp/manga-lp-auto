"""設定はすべて環境変数から読む（秘密はリポジトリに入れない）。一覧は webapp/.env.example。"""
import os
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]          # manga-lp-auto/
SCRIPTS = SKILL_DIR / 'scripts'
REFS = SKILL_DIR / 'references'
TEMPLATE_CONFIG = SKILL_DIR / 'config.example.json'


def env(name, default=''):
    return os.environ.get(name, default)


DATA_DIR = Path(env('DATA_DIR', str(Path(__file__).resolve().parents[1] / 'data'))).expanduser()
APP_BASE_URL = env('APP_BASE_URL', 'http://localhost:8080').rstrip('/')
APP_PASSWORD = env('APP_PASSWORD')                 # 社内用の共通パスワード（必須）
SECRET_KEY = env('SECRET_KEY', 'change-me')        # セッション署名用
MOCK = env('MANGA_MOCK') == '1'                    # 1 = APIを呼ばずに仮のデータで通す（動作確認用）

CLAUDE_MODEL = env('CLAUDE_MODEL', 'claude-opus-5-5')
CLAUDE_EFFORT = env('CLAUDE_EFFORT', 'high')
IMAGE_MODEL = env('OPENAI_IMAGE_MODEL', 'gpt-image-1')
IMAGE_QUALITY = env('OPENAI_IMAGE_QUALITY', 'high')

# 費用（USD）。料金表が変わったら環境変数で直す
PRICE_CLAUDE_IN = float(env('PRICE_CLAUDE_IN', '4'))         # $/1M input
PRICE_CLAUDE_OUT = float(env('PRICE_CLAUDE_OUT', '20'))      # $/1M output
PRICE_CLAUDE_CACHE_READ = float(env('PRICE_CLAUDE_CACHE_READ', '0.2'))
PRICE_CLAUDE_CACHE_WRITE = float(env('PRICE_CLAUDE_CACHE_WRITE', '5'))
PRICE_IMG_TEXT_IN = float(env('PRICE_IMG_TEXT_IN', '5'))     # $/1M（画像APIの文字入力）
PRICE_IMG_IMAGE_IN = float(env('PRICE_IMG_IMAGE_IN', '10'))  # $/1M（画像APIの画像入力）
PRICE_IMG_OUT = float(env('PRICE_IMG_OUT', '40'))            # $/1M（画像出力）
PRICE_IMG_FALLBACK = float(env('PRICE_IMG_FALLBACK', '0.25'))  # usage が返らないときの1枚あたり
USD_JPY = float(env('USD_JPY', '150'))
JOB_BUDGET_JPY = float(env('JOB_BUDGET_JPY', '5000'))        # 1件の上限。超えたら止めて人に聞く

MAX_FIX = int(env('MAX_FIX', '3'))
PASS_SCORE = int(env('PASS_SCORE', '80'))
PANEL_WORKERS = int(env('PANEL_WORKERS', '3'))               # 同時に作るコマ数

CHATWORK_TOKEN = env('CHATWORK_TOKEN')
CHATWORK_ROOM_ID = env('CHATWORK_ROOM_ID')

# 見本（過去の合格LP）。あれば比較する
BENCHMARK_SITE = env('BENCHMARK_SITE')                       # 見本LPのフォルダ（index.html と images/）
EXTRA_NG_FILE = env('EXTRA_NG_FILE')
