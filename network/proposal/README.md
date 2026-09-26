# 協力店ネット（仮称）企画書（配布用PDF）

- `proposal.html` … 原本（A4横、13ページ、図はインラインSVG）
- `協力店ネット_企画書.pdf` … 配布物。Chromium で印刷して生成
- 不特定多数に渡る前提なので、**FC関連の懸念事項・個別の会社名・人名は書かない**

## 作り直し方

1. フォント：Google Fonts の Noto Sans JP（400/700）を `fonts/` に置き、`fonts/noto-local.css` から参照する（`fonts/` は git に入れない）。無ければ IPAゴシックで描画される
2. `proposal.html` を編集
3. Playwright の Chromium で `page.pdf({format:'A4', landscape:true, printBackground:true, preferCSSPageSize:true})`
