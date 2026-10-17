# 配信待ちの置き場（deploy/machi/）

`deploy/netlify/` に置くと、別の用事の配信で一緒に公開されてしまう。オーナーの合格前のものはここに置く。

## kabi/（カビ特化LP・T069）

作り方：`python3 tools/make-kabi.py --out deploy/machi/kabi`（指摘があれば `--alt bunkai,koe-namae` など。docs/LP-カビ特化-代案-2026-10-17.md）

**合格したら（10分）：**
```
cp -r deploy/machi/kabi deploy/netlify/kabi
python3 tools/check-public-page.py deploy/netlify/kabi/index.html deploy/netlify/kabi/thanks.html
python3 tools/haishin-kakunin.py      # 全部通ったら
python3 tools/deploy-netlify.py
python3 tools/haishin-kakunin.py --honban
```
広告の最終ページURL：`https://lp.onehitter.jp/kabi/?src=gads_kabi&cid={campaignid}&ag={adgroupid}`
