# manga-lp-auto

参考にしたいLPのURLとクライアント名を渡すと、**会話で進む「漫画LP」（スマホ縦読みの漫画＋図解＋シミュレーター＋フォーム）**を、構成づくりから納品用のファイルまで通しで作る [Claude Code](https://claude.com/claude-code) のスキルです。

- 漫画のコマと図解は **ChatGPT の画像生成**で1枚ずつ作ります（ブラウザ操作。止まったら OpenAI API に切り替え可）
- 1コマごとに、セリフの一字一句・人物のすり替え・グラフの比率・矢印の向き・スマホでの文字の大きさ・背景透過・NG表現を点検し、**別のAIが採点**（80点未満は自動で直す、最大3回）
- 数字・注記・表・フォーム・シミュレーターは HTML で作るので、文字化けや数字の間違いが画像に残りません
- 人が見るのは3か所だけ：**コマ一覧**・**キャラクター設定シート**・**最後の○×**

> 日本語の広告LP向けです。景品表示法を意識した表現ルール（0円・割引・先着・架空の体験談を実例に見せない等）を含みますが、法的な判断を代わりにするものではありません。

## 流れ

| # | 工程 | 人の確認 |
|---|---|---|
| ① | 参考LPをスマホ幅で開き、画像を順番どおりに取得して番号つき一覧にする | |
| ② | 章立て・コマ一覧・ChatGPTへのプロンプト・要確認リストを作る | **○** |
| ③ | キャラクター設定シートを作る | **○** |
| ④ | 1コマずつ 生成 → 機械チェック → 点検＋別AI採点 → 修正（最大3回） | 3回でダメなときだけ |
| ⑤ | 設定ファイル（lp.json）から本番用・確認用のHTMLを組み立てる | |
| ⑥ | スマホ幅で表示・フォームを確認し、見本（過去の合格LP）と比べて採点 | |
| ⑦ | 確認用URL（GitHub Pages など）に公開 | 最初の公開前に一言 |
| ⑧ | 本番用zip＋公開手順をまとめる | **○×** |

## 必要なもの

- Claude Code（デスクトップアプリ、または CLI）
- Python 3.10+ と `pip install pillow playwright requests` ＋ `playwright install chromium`
- 画像の作り方はどちらか
  - **ChatGPT**：Chrome に [Claude in Chrome](https://claude.com/chrome) 拡張を入れ、ChatGPT にログインしておく（画像生成が使えるプラン）
  - **OpenAI API**：環境変数 `OPENAI_API_KEY`（または `~/.config/manga-lp-auto/openai_key` に1行）。キーはリポジトリに入れないでください
- 確認用URLを作る場合：GitHub アカウント（Pages を使う）

## インストール

```bash
git clone https://github.com/<owner>/manga-lp-auto.git ~/.claude/skills/manga-lp-auto
mkdir -p ~/.config/manga-lp-auto
cp ~/.claude/skills/manga-lp-auto/settings.example.json ~/.config/manga-lp-auto/config.json
# config.json を自分の環境に合わせて書き換える（GitHubアカウント名、追加のNG語リスト、見本LPの場所など）
```

Claude Code を開き直すとスキルが読み込まれます。

## 使い方

Claude Code にこう頼みます。

```
〇〇社の漫画LPを作って。参考はこのURL：https://example.com/lp/
LP戦略シート（またはワイヤー）はこれ：…
```

最初に「ChatGPT と API のどちらで作るか」「画像の保存をまとめて許可するか」を聞かれます。

## Webアプリ版

URLを開いて入力するだけで、裏で自動で作る版もあります（社内向け・ログインあり・Chatwork通知）。画像は OpenAI の画像API、構成・点検・採点は Claude API で動かします。手順は [`webapp/README.md`](webapp/README.md)。

## 設定ファイル

| ファイル | 置き場所 | 中身 |
|---|---|---|
| `config.example.json` | このリポジトリ（サンプル） | 1案件の設定。案件フォルダに `lp.json` としてコピーして使う：サイト名・色・ページの並び・シミュレーターの設問・送信先・計測ID・サンクスの文言 |
| `settings.example.json` | このリポジトリ（サンプル） | 各自の環境の設定。`~/.config/manga-lp-auto/config.json` にコピー：GitHubアカウント・NG語リスト・見本LP・社内ルール |
| `~/.config/manga-lp-auto/house_rules.md` | 各自（任意） | 社内やクライアントごとの決まり。スキルが最初に読む |

**秘密（APIキー・フォームの送信先URL・計測ID）は、リポジトリではなく各案件の `lp.json` や環境変数に書いてください。**確認用ビルド（`--mode preview`）は計測タグと送信先を自動で外し、送信もしません。

## 試してみる（サンプル）

```bash
S=~/.claude/skills/manga-lp-auto
python3 $S/scripts/build_lp.py build $S/config.example.json --images $S/examples/sample/img --out /tmp/manga-sample --mode preview
python3 -m http.server 8000 --directory /tmp/manga-sample   # http://localhost:8000 をスマホ幅で
```

サンプルは架空ブランドで、画像は仮の絵です。

## 中身

```
SKILL.md                     スキル本体（工程と判断のルール）
references/                  工程ごとの詳しい手順
  story_and_prompts.md         参考LPの読み方・章立て・プロンプトの書き方・設定シート
  panel_checklist.md           1コマの点検項目（実際に起きたNG例つき）と修正プロンプトの型
  judge_prompt.md              別AIの採点の文
  image_generation.md          ChatGPT（ブラウザ操作）と OpenAI API
  expression_rules.md          NG表現・景表法の注意・要確認リスト
  html_build.md                lp.json の書き方・部品・初期値
  benchmark_review.md          見本LPとの比較
  publish.md                   スマホ確認・確認用URL・納品
scripts/
  ref_capture.py               参考LPの画像取得と一覧化
  panel_tool.py                1コマの保存・機械チェック・記録
  openai_image.py              OpenAI API で生成・修正（予備）
  build_lp.py                  HTMLの組み立て・点検・比較・zip
assets/template/             HTMLテンプレート（CSS・JS・サンクス・プライバシーポリシー）
examples/sample/             架空ブランドのサンプル（panels.json と仮の画像）
config.example.json          1案件の設定のサンプル
settings.example.json        各自の環境の設定のサンプル
```

## ライセンス

MIT
