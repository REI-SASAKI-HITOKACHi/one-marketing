#!/usr/bin/env python3
"""青山リアルティー様のご紹介カード（案2 夜の藍）を、ラクスルの「箔押し名刺」の入稿データにする。

【何のためか】オーナー 2026-10-30「案２なんだけど、高級感が超重要だから金箔とか押せるならその形式で」
  「青山様の窓口のまま」「前回と同じ 100部」「青山様へ直送」。表の金（ARA・細線・RESIDENCE CARE）を本物の金箔にする。

【ラクスルの決まり（2026-10-30 に箔押しの入稿ガイドで確認）】
  - 箔は表面だけ。箔の部分は黒1色のパス・文字で、画像は不可。箔の部分と箔以外は別に作る
  - Office 方式の PDF は「全体のデザイン（完成イメージ）」「箔押し以外のデータ」「箔押し部分のデータ」の3ページ
  - 印刷は箔の上に乗る → 箔の下の背景は抜く。ズレが約1mm出るので、箔は抜きより少し大きく作る
  - 文字6pt以上・箔の線0.5pt（0.2mm）以上
  仕上がり 91×55mm。塗り足しは手元の版と同じ各3mm（97×61mm）。

    python3 tools/build-aoyama-foil.py
    → dist/partner-cards/aoyama-foil/omote-3page.pdf（完成イメージ・箔以外・箔の3ページ）
      omote-kansei.pdf / omote-hakuigai.pdf / omote-haku.pdf / ura.pdf と、確かめ用の png

  元のデザインは print/partner-cards/cards.html の #aoyama-2-omote・#aoyama-2-ura（書き換えない）。
"""
import pathlib
import json
import re
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "print" / "partner-cards" / "cards.html"
OUT = ROOT / "dist" / "partner-cards" / "aoyama-foil"

# 箔にする要素（表の金色 #CDB781 の3つ）
HAKU = (".a2o .mono", ".a2o .line", ".a2o .en")
# 箔を抜きより太らせる量（ズレ対策。文字の輪郭に足す）
FUTORASE = "0.35pt"


def bubun(html, id_):
    """id の div（表または裏の1面）を取り出す。"""
    m = re.search(r'<div class="page[^"]*" id="%s">.*?\n</div>' % id_, html, re.S)
    if not m:
        raise SystemExit(f"{id_} が cards.html に見つかりません")
    return m.group(0)


def main():
    html = SRC.read_text(encoding="utf-8")
    head = re.search(r"<head>.*?</head>", html, re.S).group(0)
    omote, ura = bubun(html, "aoyama-2-omote"), bubun(html, "aoyama-2-ura")
    sel = ",".join(HAKU)
    styles = {
        # 1 完成イメージ：元のまま
        "kansei": "",
        # 2 箔押し以外：箔の部分を紙の白で抜く（印刷しない）
        "hakuigai": f"{sel}{{color:#FFFFFF !important}} .a2o .line{{background:#FFFFFF !important}}",
        # 3 箔押し部分：白地に箔の要素だけ黒（少し太らせる）。ほかは消す
        "haku": (".a2o{background:#FFFFFF !important} .a2o .jp{visibility:hidden}"
                 f" {sel}{{color:#000000 !important;-webkit-text-stroke:{FUTORASE} #000000}}"
                 " .a2o .line{background:#000000 !important;height:.35mm !important}"),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        files = {}
        for k, css in styles.items():
            p = td / f"omote-{k}.html"
            p.write_text(f"<!doctype html><html lang='ja'>{head.replace('</head>', f'<style>{css}</style></head>')}<body>{omote}</body></html>", encoding="utf-8")
            files[f"omote-{k}"] = p
        p = td / "ura.html"
        p.write_text(f"<!doctype html><html lang='ja'>{head}<body>{ura}</body></html>", encoding="utf-8")
        files["ura"] = p
        js = td / "r.js"
        js.write_text("""
const { chromium } = require(require('child_process').execSync('npm root -g').toString().trim() + '/playwright');
(async () => {
  const b = await chromium.launch();
  const pg = await b.newPage({ deviceScaleFactor: 4 });
  for (const [name, src] of JSON.parse(process.argv[2])) {
    await pg.goto('file://' + src, { waitUntil: 'networkidle' });
    await pg.evaluate(() => document.fonts.ready); await pg.waitForTimeout(300);
    await pg.pdf({ path: process.argv[3] + '/' + name + '.pdf', width: '97mm', height: '61mm', printBackground: true, pageRanges: '1' });
    await pg.locator('.page').first().screenshot({ path: process.argv[3] + '/' + name + '.png' });
  }
  await b.close();
})();
""", encoding="utf-8")
        subprocess.run(["node", str(js), json.dumps([[k, str(v)] for k, v in files.items()]), str(OUT)], check=True)
    # 3ページの PDF は1ページずつの PDF をつなぐ
    tsunagu(OUT, ["omote-kansei", "omote-hakuigai", "omote-haku"], OUT / "omote-3page.pdf")
    for f in sorted(OUT.iterdir()):
        print(f.relative_to(ROOT), f.stat().st_size)


def tsunagu(d, names, out):
    """PDF をつなぐ。pypdf があれば使い、なければ qpdf、どちらも無ければ作らない。"""
    srcs = [str(d / f"{n}.pdf") for n in names]
    try:
        from pypdf import PdfWriter
        w = PdfWriter()
        for s in srcs:
            w.append(s)
        with open(out, "wb") as f:
            w.write(f)
        return
    except ImportError:
        pass
    if subprocess.run(["which", "qpdf"], capture_output=True).returncode == 0:
        subprocess.run(["qpdf", "--empty", "--pages", *srcs, "--", str(out)], check=True)
    else:
        print("⚠ pypdf も qpdf も無いので 3ページの PDF は作っていません（1ページずつの PDF を使う）")


if __name__ == "__main__":
    main()
