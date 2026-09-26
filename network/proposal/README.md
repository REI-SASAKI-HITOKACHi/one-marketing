# 協力店ネット（仮称）企画書（配布用PDF）

- `proposal.html` … 原本（A4横、13ページ。図はHTML/CSSとSVG、SVGの中に文字は置かない）
- `協力店ネット_企画書.pdf` … 配布物。Chromium で印刷して生成
- 不特定多数に渡る前提なので、**FC関連の懸念事項・個別の会社名・人名は書かない**
- 「網」という表現は使わない。自社は「運営会社」と書く（社名は出さない）

## 作り直し方

1. フォント：Google Fonts の Noto Sans JP（400/700）を `fonts/` に置き、`fonts/noto-local.css` から参照する（`fonts/` は git に入れない）。無ければ IPAゴシックで描画される
2. `proposal.html` を編集
3. `NODE_PATH=/opt/node22/lib/node_modules node check/build.js` … PDFを書き出し、ブラウザ上で枠からのはみ出し・余白の偏り・禁止語を検査
4. `python3 check/verify-pdf.py`（要 `pip install pymupdf`）… **書き出したPDFファイルそのもの**を読み込んで検査
   （ページ外・フッターとの重なり・文字同士の重なり・枠外の文字・3文字以下の行・カタカナ語の途中での改行・禁止語）
5. 両方が「問題なし」になったら、PDFを画像にして全ページを目で確認してから完成とする
