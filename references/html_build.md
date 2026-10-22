# HTMLへの組み込み（工程⑤）— lp.json の書き方

テンプレートは、実際に合格した漫画LP（30コマ）から作ったもの。その設定ファイルから元のLPと同じ index.html を再現できることを確認済み（`<script>` 以外がバイト単位で一致、送信データ・サンクス表示が同じ。回帰テストは `benchmark_review.md` の4章）。新しい案件は `config.example.json`（または設定の `benchmark.lp_json`）を案件フォルダに `lp.json` としてコピーして書き換える。

```bash
S=~/.claude/skills/manga-lp-auto/scripts
python3 $S/build_lp.py images img/ build/images            # 確定画像 → 幅800pxのwebp（_v1・P0は除く）
python3 $S/build_lp.py build lp.json --images build/images --out site            # 本番用（GTM・送信先あり）
python3 $S/build_lp.py build lp.json --images build/images --out preview --mode preview --flat   # 確認用
python3 $S/build_lp.py check site; python3 $S/build_lp.py check preview --mode preview
```

## 本番用と確認用の違い（必ず残すこと）
| | 本番 `site/` | 確認用 `preview/` |
|---|---|---|
| GTM | 入る（`tracking.gtm`） | 入れない（クライアントのGA4・広告に確認のアクセスを記録しない） |
| 送信先（GAS・mail.php） | 入る | 空（公開リポジトリに送信先URLを載せない） |
| 送信 | `site.prod_host` のドメインのときだけ送る（localhostでは送らずサンクスへ） | 送らない（`preview:true`） |
| robots.txt | なし（noindexのみ） | `Disallow: /` |
| 画像 | `images/` | `--flat` で同じ階層（GitHubのWeb画面から1回で上げやすい） |

## lp.json の項目

| キー | 中身 |
|---|---|
| `site` | name（ロゴ文字・フッター）, tagline, title, description, header_button, footer, **prod_host**（送信を許すドメイン）, manga_note（漫画の注記） |
| `colors` | 上書きする色だけ。既定：navy #14284b（見出し帯）, cta #f07a12（ボタン）, mark #ffe55c（マーカー）, red #e0201b, gift #c2410c ほか。**クライアントのブランド色を実測して navy・cta を合わせる** |
| `tracking` | gtm（例 GTM-XXXX）, gtm_note（コメント） |
| `gift` | 特典がある時だけ：badge, text, sticky。無ければ `null`（`{{GIFT}}` は消える） |
| `sticky` | 画面下に固定するボタンの文字 |
| `sim` | 漫画の途中に置くシミュレーター（1問目だけ）の見出し：small, title_html, hint_html |
| `form` | form_id, gas_url, mail_endpoint, payload_title, heading_html, trust, details（開くと読める条件）, fine, prefs（都道府県）, **steps**（設問）, plan（サンクスの「お電話でご案内すること」）, plan_default |
| `faq` | [質問, 答え] の配列 |
| `thanks` | サンクスページの文言・想定額の出し方・demo（`thanks.html?demo=1` で表示） |
| `privacy` | operator（運営者の屋号・住所の行）。クライアントの既存ポリシーがあれば `file` にパス |
| `blocks` | ページの中身（下） |

### steps（設問）の約束
- 最後に連絡先（お名前・都道府県・電話番号）が自動で付く
- 1問目は漫画の途中（`sim` ブロック）にも出る。選ぶとフォームへ移り2問目から続く
- 選択肢に持たせる値：`save`/`year`（サンクスの想定額。円）、`bill`・`intent`（スコア）、`qualify:true`（対象者。その設問に `qualifier:true`）、`key`（plan の見出し）
- 既存の診断LPと設問・送信データの形を**そろえる**。送信先のスプレッドシートが同じ形を前提にしているため。新しいクライアントは、既存の送信先の形を先に確認する
- 想定額を出さない商材は `thanks.amount` を `null` に

## blocks（上から順）

| type | 書くこと | 出るもの |
|---|---|---|
| `koma` | img, alt（セリフを含めて具体的に）, ch（計測の章名）, id, fv:true（1枚目） | 漫画・図解の画像。幅高さは画像から自動 |
| `note` | html | 画像のすぐ下の小さい注記（※） |
| `manga_note` | — | 「※漫画はイメージです…」 |
| `chap` | id, ch, q（Q1 など）, html | 紺の章見出し |
| `cta` | micro, label, sub, cls（soft/sky）, tag, style | 特典＋ひと言＋ボタン |
| `sim` | — | シミュレーター（1問目） |
| `html` | html | 表・比較・実例カード・タブ・チェックリスト等。下の部品を使う |
| `faq` | title | FAQ（`faq` から生成） |
| `final` | img, html | 最終CTAの背景画像＋大きな文字 |
| `form` | — | フォーム（steps から生成） |

共通：`comment`（HTMLコメント）, `after_blank`（後ろに空行）。
html ブロックの中で使える差し込み：`{{IMG}}`（画像の置き場所）, `{{GIFT}}`（特典の枠）, `{{CTA|ひと言|ボタン文字}}`（`|sub` で紺のボタン）, `{{SITE_NAME}}`。

### html ブロックの部品（CSSは assets/template/manga.css）
`config.example.json` と、設定の `benchmark.lp_json` に実物がある。
- `.sec`（.soft / .sky）… 区切りの白・薄青の帯。`.hd.sm` 見出し、`.mk` 黄色マーカー、`.lead`、`.fine`（※）
- 実例カード `.slider > .case`（.who .eq .bf .af .cut .yr）… 横スワイプ。**導入前の金額と削減額を大きく、エリアを散らす**
- 表 `table`（`.best` で推し列）、比較 `.vs`、タブ `[data-tabs] .tablist .panel` と棒 `.bars`
- タイル `.g2/.g3 > .tile`（`.ico`）、チェック `.checks`（`.checkwrap` で横に透過イラスト）、カード `.card`、アコーディオン `details.acc`、手順 `.steps`

## 初期値（過去の案件で受けた指示。新しい案件でも最初から守る。社内・クライアント固有の決まりは `house_rules.md` へ）
- 確認用の色付け・「作成例」の表示は**出さない**
- **未確認の情報は載せない**（保証・メーカー・設置実績・点検・お客様の声・会社概要・根拠のないFAQは削る）。要確認リストへ
- 実例カードは「当社試算のモデルケース（実在のお客様の事例ではありません）」と注記し、個人名（K様）は使わず「千葉県・4人家族」
- 事例はエリアを散らし（**対応エリアの県を必ず含める**）、**導入前の金額と削減額・削減率を大きく**
- 特典の内訳（相談¥2,000…）の小さい注記はCTAに出さない（フォーム下の「進呈条件」にだけ）
- 最終CTAの文字は大きく：スマホ幅で約28px以上（`.final .over p` は `min(7.6vw,36px)`＝390px幅で約30px）
- シミュレーターは、クライアントの既存の診断LPの設問・送信データの形にそろえる。結果の金額はクライアントの前提（例：約9割削減）に合わせ、注記に前提を書く
- サイト名は、クライアントが指定した表記に（画像内の表記と食い違ったら要確認リストへ）
