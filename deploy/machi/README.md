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

## nenmatsu-b/・mizumawari-b/（カードの初めの金額・依頼 20261019-02-lp）

「よくある頼み方」カードの「キッチン＋レンジフード＋コンロ」の、HTML に書いた最初の金額が 39,710円（12月 49,610円）のままだった。
コンロのセット価格が 6,050円だったころの値（10/16 の税の訂正で漏れていた）。JS が動けば 39,160円（12月 49,060円）に計算し直すので、
画面に出ていたのは JS が動かない場合だけ。作り方：今の配信物に `python3 tools/zei-1016.py` を当てただけ（差は2行と1行）。

**CMO の OK が出たら：**
```
cp deploy/machi/nenmatsu-b/index.html deploy/netlify/nenmatsu-b/index.html
cp deploy/machi/mizumawari-b/index.html deploy/netlify/mizumawari-b/index.html
python3 tools/zei-1016.py --check deploy/netlify/*/index.html
python3 tools/haishin-kakunin.py      # 全部通ったら
python3 tools/deploy-netlify.py
python3 tools/haishin-kakunin.py --honban
```
