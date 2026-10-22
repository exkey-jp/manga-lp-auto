# 画像の作り方（ChatGPT を基本、止まったら OpenAI API）

## 0. 作り始める前に1回だけ聞くこと（まとめて1回）

`AskUserQuestion` で次の2つを聞く。答えは `panels.json` の `"generator"` と `"download_ok"` に書いておき、再開時に聞き直さない。

1. **どちらで作るか**
   - ChatGPT（ログイン中のChromeを操作）（推奨：ユーザーの希望。追加料金なし。画面が変わると止まることがある）
   - OpenAI API（安定。1枚数十円程度・30枚で千円前後。`OPENAI_API_KEY` が必要＝人が設定）
   - ChatGPTで始めて、止まったらAPIに切り替える
2. **画像の保存（ダウンロード）を、この案件の間まとめて許可してよいか**：保存先 `~/Downloads/` → 案件の `img/`。ファイル名は `M01_shock.png` 等、1枚1〜3MB、30〜45枚（直しを含む）

ChatGPTで作る場合は、あわせて「ログイン中のChatGPTアカウントに送信を始めてよいか」も同じ質問で確認する（その日の最初の送信前に1回）。

## 1. ChatGPT（Claude in Chrome）

設定に `chatgpt_guide`（社内の共通手順）があれば先に読む。要点と漫画LP固有のこと：

- ツールは1回の ToolSearch でまとめて読み込む：
  `select:mcp__claude-in-chrome__list_connected_browsers,mcp__claude-in-chrome__select_browser,mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__find,mcp__claude-in-chrome__file_upload,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__browser_batch`
- `list_connected_browsers` で `onThisComputer` のChromeを選ぶ（違うと保存したファイルが手元に落ちない）
- **チャットの組み立て**
  1. 新しいチャット → 共通ルール（`rules.txt`）を送る → 「了解」を待つ
  2. 設定シートを作る（③）→ 確定したら以後このチャットで続ける
  3. 各コマ：`P0_chara.png` を添付（人物が出るコマ）→ プロンプトを入れて送信
  4. **6〜8枚ごとに新しいチャット**へ移る（重くなり、古い画像の取り違えが起きる）。新しいチャットでは共通ルールと P0 を最初に送り直す
- 長文は JavaScript の `insertText` で入れる（`computer type` は改行で送信されてしまう）。前の下書きを `selectAll→delete` で消してから
- **2026-10-22 時点の画面（実際に動かして確認）**：
  - 入力欄 `.ProseMirror[contenteditable=true]` が2つある（片方は非表示）。**表示されている方**を使う：`[...document.querySelectorAll('.ProseMirror[contenteditable=true]')].find(e => e.offsetParent !== null)`
  - 生成中の停止ボタンは `data-testid` が無く `aria-label="停止"`。生成が終わっても**非表示のまま残る**ので、`offsetParent !== null`（見えている）で判定する
  - `[data-message-author-role]` で発言を取れなくなった。返事の確認はスクリーンショットか、画像の枚数（幅512px以上の img）で
  - 添付した設定シートも「大きい画像」に数えられる。送信前の枚数を控えてから数える
  - 共通ルールの返事に約10秒、横長1枚に約60〜90秒、透過の正方形に約80秒
- 添付は `find "file input for uploading images"` → `file_upload`（クリップは押さない）
- 待つ：30秒ごとに大きい画像の枚数と停止ボタンを確認（1枚1〜2分、上限5分）。トップレベル `await` で書く
- 保存：**一番下までスクロール → 直前の画像とバイト数が違うことを確認 → `<a download>` で `~/Downloads/<file>.png`**。その後 `panel_tool.py save <案件> <ID> ~/Downloads/<file>.png`（前の版と同じなら止まる＝古い画像を落とした合図）
- 透過指定のコマは、ChatGPTの表示では透過に見えても白で塗られていることがある → `panel_tool.py check` の F で必ず確認
- 直しは同じチャットで「修正プロンプト」を送る（P0 を添付）。大きく外れたら新しく1枚

### 止まったとき
| 症状 | 対処 |
|---|---|
| 応答が空／Something went wrong | 「さきほどの内容で1枚作ってください」と短く送り直す（2回まで） |
| 生成回数の上限・待ち時間の表示 | そこで止め、**APIに切り替えてよいか**（generator が「止まったらAPI」なら確認なしで）切り替える |
| タブが固まる・JSがタイムアウト | 新しいチャットで共通ルール＋P0から続ける |
| ログイン切れ・別アカウント | 止めて人に伝える（ログインは代行しない） |
| 保存したのにファイルが増えない | Chromeの選び間違い → `select_browser` をやり直す |

## 2. OpenAI API（予備）

```bash
S=~/.claude/skills/manga-lp-auto/scripts
# 新しく作る（人物が出るコマは設定シートを --ref で必ず渡す）
python3 $S/openai_image.py gen --rules rules.txt --prompt-file prompts/M01.txt --size 1536x1024 \
  --ref img/P0_chara.png --out ~/Downloads/M01_shock.png
# 直す（今の画像＋設定シート）
python3 $S/openai_image.py edit --image img/M14_kaishu.png --ref img/P0_chara.png \
  --prompt-file prompts/M14_fix1.txt --size 1536x1024 --out ~/Downloads/M14_kaishu.png
# 透過
python3 $S/openai_image.py gen ... --size 1024x1024 --transparent
```
- APIは会話を覚えないので、**共通ルールを毎回 `--rules` で先頭につける**
- キーは `OPENAI_API_KEY`（または `~/.config/manga-lp-auto/openai_key`）。**キーの作成・入力は人にしてもらう**。見つからなければ止めて伝える
- 出力は `~/Downloads/` に置き、あとは ChatGPT と同じく `panel_tool.py save → check`
- ChatGPTとAPIで画風が少し変わるので、途中で切り替えたら最初の1枚を前のコマと並べて画風を確認する

## 3. 進め方（1コマのループ）

```
for コマ in panels（status != done）:
    生成（ChatGPT or API） → 保存（panel_tool save）
    → 機械チェック（panel_tool check）
    → 自分の点検（panel_checklist.md）＋ 判定AI（judge_prompt.md）
    → OK: mark ok → 次へ
    → NG: 修正プロンプトを1通 → 生成し直し（最大3回） → それでもNG: mark stop、人に聞く（他のコマは進めてよい）
```
- 人には**1枚ごとに見せない**（人は要所と最後の○×だけ）。ただし `ask_human` のコマが出たら、その時点で `qa/<ID>/zoom.png` と残った指摘を送って聞く
- 10枚ごとに `panel_tool.py status` の結果を1〜2行で報告する
- 目安：30枚で2〜3時間（直しを含む）
