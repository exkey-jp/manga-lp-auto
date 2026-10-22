# 確認・公開・納品（工程⑥〜⑧）

## ⑥ スマホ幅での確認

1. `~/.claude/launch.json` に確認用サーバーを足す（無ければ）：
   `{"name":"manga-<案件>","runtimeExecutable":"python3","runtimeArgs":["-m","http.server","<空いている番号>","--bind","127.0.0.1","--directory","<案件>/site"],"port":<番号>}`
2. `preview_start` → `resize_window {preset:"mobile"}` → 上から順にスクリーンショット（`qa/screens/01.png…`）。見ること：
   - 画像が全部出る（`read_network_requests` に404がない）・コンソールにエラーがない
   - 横スクロールが出ない（`document.documentElement.scrollWidth <= innerWidth`）
   - 画像の下の注記が画像と合っている、章見出し・CTAの位置
   - 1枚目（FV）で誰向け・何がわかるかが分かる。固定ボタンがFVから出ている
3. **フォームを通しで動かす**：シミュレーターの1問目 → フォームへ移る → 2問目以降 → 連絡先（テスト値）→「結果をみる」→ サンクスに想定額が出る。localhost なので送信はされない（コンソールに「未送信」と送信データが出る）。送信データの形を `qa/送信データ.json` に保存
4. **見本と比べる**：`benchmark_review.md` の手順（`build_lp.py compare` で数を比べ、スクリーンショットを別AIに渡して採点。80点未満は直す）
5. 終わったら `resize_window {preset:"desktop"}` に戻す

## ⑦ 確認用URL（GitHub Pages）

- 公開してよいのは **確認用ビルド（`--mode preview --flat`）だけ**。GTM・送信先（GAS URL）・mail.php の場所を公開リポジトリに載せない（自動モードでも拒否される）
- クライアントの社名・ブランド入りのページをネットに出すので、**最初の公開の前に人に一言確認**する（「GitHub Pagesで確認用URLを作ってよいか。noindex・robots.txtで検索には出ないが、URLを知っていれば誰でも見られる」）
- アカウントは設定の `github_owner`。`gh`（GitHub CLI）が使えるならそれで作成・push する。使えなければ、**GitHub にログイン済みの Chrome**（設定の `chrome_profile_hint`。`list_connected_browsers` で確かめる）から Web 画面で操作する
  1. `https://github.com/new` → リポジトリ名 `<client>-manga-lp`（public）→ 作成
  2. 「uploading an existing file」→ `find "file input"` → `file_upload` で `preview/` の全ファイル（`--flat` で画像も同じ階層）→ Commit。サブフォルダがあるときは `https://github.com/<owner>/<repo>/upload/main/<フォルダ>` を開いてフォルダごとに上げる（Web画面のファイル選択ではフォルダ構成が保たれないため）
  3. Settings → Pages → Branch: main / root → Save。1〜2分で `https://<github_owner>.github.io/<repo>/`
  4. 開いてスマホ幅で表示・フォームが最後まで動くことを確認
- 直したら、変わったファイルだけ同じ手順で上げ直す

## ⑧ 本番zip＋公開手順（人の○×）

1. `site/README.txt` を `assets/README.tmpl.txt` から書く（中身・公開手順・設定済みのもの・計測イベント・確認用URL・未決定事項）
2. `python3 $S/build_lp.py package site --name "<サイト名>_漫画LP"` → デスクトップに `<名前>.zip` と `<名前>_公開手順.txt`
3. 人に送るもの（`SendUserFile`）：確認用URL、スクリーンショット（FV・シミュレーター・フォーム・サンクス）、`要確認リスト.md`、`qa/点検記録.md`、`人の最終チェック.md`
4. `人の最終チェック.md`（○×だけ。好みで直さない）
   - [ ] スマホで1画面目に「誰向け・何がわかる・ボタン」がある
   - [ ] 話の流れが自然で、人物が最後まで同じ人に見える
   - [ ] 漫画の文字・数字が正しく、注記が付いている
   - [ ] 使っていない表現（0円・割引・先着・架空の声）が出ていない
   - [ ] シミュレーター → フォーム → サンクスが動き、想定額が出る
   - [ ] 要確認リストの残りを、このまま公開してよいか
5. ×が付いたら該当工程だけ直し、確認用URLとzipを作り直す

本番サーバーへのアップロードはしない（サーバーの管理画面に入る手段がない／クライアント側の作業）。公開担当者へは zip と公開手順.txt を渡す。
