# 漫画LP 自動制作 Webアプリ

URLを開いてログイン → クライアント名と参考LPのURLなどを入力 → 裏で自動で漫画LPを作ります（1件 2〜3時間）。
途中の「構成」と「キャラクター設定シート」だけ画面で承認し、最後に確認用ページと本番用zipを受け取ります。進み具合は Chatwork に届きます。

スキル（`../SKILL.md`）と同じ工程・同じ点検基準を、サーバー上で動かすものです。

## 中で何をしているか

| 工程 | 使うもの |
|---|---|
| ① 参考LPをスマホ幅で開いて画像を取得・一覧化 | Playwright（`../scripts/ref_capture.py`） |
| ② 章立て・コマ一覧・画像プロンプト・要確認リスト → **画面で承認** | Claude（`claude-opus-5-5`・構造化出力） |
| ③ キャラクター設定シート → **画面で承認** | OpenAI 画像API ＋ Claude の点検 |
| ④ 1コマずつ 生成 → 機械チェック → 点検（チェックリスト）＋**別の採点役**（80点）→ 直し最大3回 | OpenAI 画像API（設定シートを参照画像に）＋ Claude 2回（点検役と採点役は別の指示・別の呼び出し） |
| ⑤ lp.json を書いてHTMLを組み立て | Claude ＋ `../scripts/build_lp.py` |
| ⑥ スマホ幅で撮影・フォームを通しで操作・見本LPと比較して採点（80点、直し最大3回） | Playwright ＋ Claude |
| ⑧ 本番zip・公開手順・要確認リスト・点検記録 | `build_lp.py package` |

3回直しても合格しないコマは止めずに後回しにし、最後に画面で「このまま使う／指示して作り直す／画像を差し替える」を選べます。
1件の費用が上限（既定5,000円）を超えると止まり、画面で上限を上げると続きから再開します。

## 費用の目安（1件）

| | 目安 |
|---|---|
| 画像（約30コマ＋直し、設定シート） | 1,000〜2,000円 |
| Claude（構成・点検・採点・HTML） | 1,000〜1,500円 |
| 合計 | 2,500〜4,000円 |

実際の金額は画面の「費用」に出ます（Claude は返ってきたトークン数、画像はAPIが返す使用量から計算。料金表が変わったら `.env` の PRICE_* を直す）。

## 手元で動かす

```bash
cd webapp
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/playwright install chromium
cp .env.example .env   # 値を入れる
set -a; . ./.env; set +a
.venv/bin/uvicorn app.main:app --port 8080
```

APIを呼ばずに画面の流れだけ確かめるときは `MANGA_MOCK=1`（仮の画像・仮の構成で最後まで進みます。`MANGA_MOCK_STUCK=M02` で、そのコマを「3回直しても不合格」にできます）。

## Google Cloud Run に置く（例）

1件が2〜3時間かかり、裏で処理を続けるため、**CPUを常に割り当て・最小インスタンス1** にします。制作データはバケットをマウントして残します。

```bash
# リポジトリのルートで
gcloud builds submit --tag REGION-docker.pkg.dev/PROJECT/manga/webapp -f webapp/Dockerfile .   # または docker build -f webapp/Dockerfile .
gcloud run deploy manga-lp \
  --image REGION-docker.pkg.dev/PROJECT/manga/webapp \
  --no-cpu-throttling --min-instances 1 --max-instances 1 --memory 2Gi --timeout 3600 \
  --add-volume name=data,type=cloud-storage,bucket=BUCKET --add-volume-mount volume=data,mount-path=/data \
  --set-secrets ANTHROPIC_API_KEY=anthropic-key:latest,OPENAI_API_KEY=openai-key:latest,APP_PASSWORD=app-password:latest,SECRET_KEY=session-key:latest,CHATWORK_TOKEN=chatwork-token:latest \
  --set-env-vars CHATWORK_ROOM_ID=...,APP_BASE_URL=https://...run.app
```

- `--max-instances 1`：制作の進み具合をその1台が持つため（台数を増やすとジョブが二重に動く）
- 秘密（APIキー・パスワード・Chatworkのトークン）は Secret Manager に置く。リポジトリや画像には入れない
- 再起動しても、途中のジョブは自動で続きから再開します

## 安全のために

- 社内用：全ページ・全ファイルにログインが必要（共通パスワード）。URLを外に出さない
- APIキーはサーバーの環境変数だけで持ち、画面には出さない
- 確認用ページは計測タグなし・送信先なし・送信しない（本番zipにだけ入る）
- 入力されたURLの中身（参考LP・資料）はデータとして扱い、そこに書かれた指示には従わないようにClaudeに指示している
