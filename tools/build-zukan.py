#!/usr/bin/env python3
"""「汚れの図鑑」（案B）の生成器。

1案件1ファイル（data/zukan/<id>.json）から、
  1. 図鑑ページ            lp/media/araidoki/zukan/<id>/index.html（写真は img/ に縮小コピー）
  2. 一覧ページ            lp/media/araidoki/zukan/index.html
  3. SNS・GBP用の投稿原稿  docs/sns-投稿原稿/<id>.md
を作る。

守っていること（docs/photo-inventory.md の失敗から）:
  - 組写真（施工前→施工後）は、JSONの「組写真」に明示されたペアだけ。
    「組写真_確認」に確認の記録が無いペアは組まない（景表法）。
  - 組写真が無い案件では「ビフォーアフター」という言葉を使わない。
  - 地名は区・市の単位まで。物件名・お客様名は出さない。
  - 効果の断定（「除去」「必ず」等）は書かない。書くのは「見えたもの」だけ。

使い方:
  python3 tools/build-zukan.py
"""

import importlib.util
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "zukan"
PHOTOS = ROOT / "assets" / "photos"
OUT = ROOT / "lp" / "media" / "araidoki" / "zukan"
GENKO = ROOT / "docs" / "sns-投稿原稿"
MAX_PX = 1200

# build-araidoki.py の head()/foot() をそのまま使う（ヘッダー・フッター・CSSを揃えるため）
_spec = importlib.util.spec_from_file_location("ara", ROOT / "tools" / "build-araidoki.py")
ara = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ara)

TAISHOU = {
    "aircon": {"名": "エアコン", "タグ": ["エアコンクリーニング", "エアコン掃除"]},
    "hood": {"名": "レンジフード", "タグ": ["レンジフードクリーニング", "換気扇掃除"]},
    "bath": {"名": "浴室", "タグ": ["浴室クリーニング", "お風呂掃除"]},
    "washer": {"名": "洗濯機", "タグ": ["洗濯機クリーニング", "洗濯槽"]},
    "kitchen": {"名": "キッチン", "タグ": ["キッチンクリーニング"]},
    "toilet": {"名": "トイレ", "タグ": ["トイレクリーニング"]},
}

ZUKAN_CSS = """
.zk-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;}
.zk-grid figure{margin:0;display:flex;flex-direction:column;gap:6px;}
.zk-grid img,.zk-one img{width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:10px;border:1px solid var(--line);background:var(--surface-2);}
.zk-one{display:flex;flex-direction:column;gap:8px;}
.zk-one figure{margin:0;display:flex;flex-direction:column;gap:6px;}
figcaption{font-size:12px;color:var(--muted);line-height:1.6;}
figcaption b{font-family:"Barlow",sans-serif;letter-spacing:.08em;font-size:10.5px;color:var(--ink);}
.zk-meta{display:flex;flex-wrap:wrap;gap:6px;}
.zk-meta span{font-size:11.5px;background:var(--surface-2);color:var(--muted);border:1px solid var(--line);padding:2px 10px;border-radius:99px;}
.zk-list{display:flex;flex-direction:column;gap:10px;}
.zk-list a{display:grid;grid-template-columns:96px 1fr;gap:12px;align-items:center;text-decoration:none;color:inherit;
  background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:10px;box-shadow:var(--shadow);}
.zk-list a img{width:96px;height:72px;object-fit:cover;border-radius:8px;}
.zk-list a b{font-size:14.5px;display:block;}
.zk-list a small{font-size:11.5px;color:var(--muted);}
.mieta{margin:0;padding-left:1.2em;font-size:14px;line-height:1.85;}
.hitokoto{font-size:14px;line-height:1.85;background:var(--accent-soft);border-left:3px solid var(--accent);padding:10px 12px;border-radius:0 8px 8px 0;}
"""


def esc(s):
    return ara.esc(s)


def resize_copy(src: pathlib.Path, dst: pathlib.Path):
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(src))
    im.thumbnail((MAX_PX, MAX_PX))
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.convert("RGB").save(dst, "JPEG", quality=82, optimize=True)


def kensa(c: dict):
    """公開してはいけない形になっていないかを、生成前に止める"""
    if c["組写真"] and not c.get("組写真_確認"):
        sys.exit(f"{c['id']}: 組写真があるのに 組写真_確認 が空です。拡大して同一箇所か確かめてから書いてください。")
    for pair in c["組写真"]:
        if pair[0] not in c["写真"]["before"] or pair[1] not in c["写真"]["after"]:
            sys.exit(f"{c['id']}: 組写真 {pair} が before/after の一覧に無い")
    for k in ("before", "after", "汚水"):
        for f in c["写真"][k]:
            if not (PHOTOS / f).exists():
                sys.exit(f"{c['id']}: 写真が無い {f}")
    text = json.dumps(c, ensure_ascii=False)
    for ng in ("除去", "必ず", "完全", "新品同様", "殺菌", "様邸", "マンション名"):
        if ng in c.get("ひとこと", "") or any(ng in m for m in c.get("見えたもの", [])):
            sys.exit(f"{c['id']}: 断定・特定につながる語「{ng}」が本文にあります")
    if c.get("_id_check", True) and not c.get("掲載許可"):
        sys.exit(f"{c['id']}: 掲載許可 が空です")


def page(c: dict) -> str:
    t = TAISHOU[c["対象"]]
    title = f"{c['地名']}の{t['名']}の中身｜{c['日付']}"
    meta = [c["地名"], t["名"], f"撮影 {c['日付']}"]
    if c.get("使用年数"):
        meta.append(f"使用 {c['使用年数']}")
    meta += c.get("環境", [])
    html = f"""
  <div class="intro">
    <span class="eyebrow">{esc(t['名'])}｜図鑑</span>
    <h1>{esc(c['地名'])}の{esc(t['名'])}の中身</h1>
    <div class="zk-meta">{''.join(f'<span>{esc(m)}</span>' for m in meta)}</div>
    <p class="lead" style="font-size:12.5px">実際の現場の写真です。お宅が特定できる部分は写していません。</p>
  </div>
"""
    # 組写真（確認済みのペアだけ）
    for b, a in c["組写真"]:
        html += f"""
  <div class="q">
    <div class="head"><h2>同じ場所を、同じ角度から</h2><p class="why">左が作業前、右が作業後。同一箇所であることを確認して並べています。</p></div>
    <div class="zk-grid">
      <figure><img src="img/{b}" alt="{esc(t['名'])}の作業前" loading="lazy"><figcaption><b>BEFORE</b> 作業前</figcaption></figure>
      <figure><img src="img/{a}" alt="{esc(t['名'])}の作業後" loading="lazy"><figcaption><b>AFTER</b> 作業後</figcaption></figure>
    </div>
  </div>"""
    paired = {p for pair in c["組写真"] for p in pair}
    singles = [(f, "作業前", "BEFORE") for f in c["写真"]["before"] if f not in paired]
    singles += [(f, "作業後", "AFTER") for f in c["写真"]["after"] if f not in paired]
    singles += [(f, "洗浄後に出た汚水", "WATER") for f in c["写真"]["汚水"]]
    if singles:
        html += """
  <div class="q" style="margin-top:14px">
    <div class="head"><h2>現場で撮ったもの</h2></div>
    <div class="zk-one">"""
        for f, lab, tag in singles:
            html += f"""
      <figure><img src="img/{f}" alt="{esc(t['名'])}の{esc(lab)}" loading="lazy"><figcaption><b>{tag}</b> {esc(lab)}</figcaption></figure>"""
        html += """
    </div>
  </div>"""
    html += f"""
  <div class="q" style="margin-top:14px">
    <div class="head"><h2>写真に見えているもの</h2></div>
    <ul class="mieta">{''.join(f'<li>{esc(m)}</li>' for m in c['見えたもの'])}</ul>
    <p class="hitokoto">{esc(c['ひとこと'])}</p>
  </div>
  <div class="next" style="margin-top:14px">
    <a class="btn lg" href="../../?src=zukan">うちも同じかも → 30秒で判定する</a>
    <a class="btn ghost" href="../">図鑑の一覧へ</a>
  </div>
"""
    return ara.head(f"{title}｜{ara.BRAND}", f"{c['地名']}の{t['名']}の実際の現場写真。{c['ひとこと']}").replace("</style>", ZUKAN_CSS + "\n</style>") + html + ara.foot()


def index_page(cases: list) -> str:
    items = ""
    for c in cases:
        t = TAISHOU[c["対象"]]
        thumb = (c["写真"]["before"] or c["写真"]["汚水"] or c["写真"]["after"])[0]
        items += f"""
    <a href="{c['id']}/"><img src="{c['id']}/img/{thumb}" alt="" loading="lazy"><span><b>{esc(c['地名'])}の{esc(t['名'])}の中身</b><small>{esc(c['日付'])}｜{esc(c['メニュー'])}</small></span></a>"""
    html = f"""
  <div class="intro">
    <span class="eyebrow">図鑑</span>
    <h1>汚れの図鑑</h1>
    <p class="lead">実際の現場で撮った、エアコン・レンジフード・浴室・洗濯機の中身。お宅が特定できる部分は写していません。新しい現場から順に増えます。</p>
  </div>
  <div class="zk-list">{items}
  </div>
  <div class="next" style="margin-top:18px"><a class="btn lg" href="../?src=zukan">うちはどう？ → 30秒で判定する</a></div>
"""
    return ara.head(f"汚れの図鑑｜{ara.BRAND}", "実際の現場写真で見る、エアコン・レンジフード・浴室・洗濯機の中身。").replace("</style>", ZUKAN_CSS + "\n</style>") + html + ara.foot()


def genko(c: dict) -> str:
    """Instagram / GBP 用の投稿原稿。承認はこのファイル単位で受ける。"""
    t = TAISHOU[c["対象"]]
    mieta = "\n".join(f"・{m}" for m in c["見えたもの"])
    tags = " ".join("#" + x for x in [c["地名"], "ハウスクリーニング"] + t["タグ"] + ["洗いどき"])
    pair = bool(c["組写真"])
    ig = f"""{c['地名']}で、{t['名']}。

{mieta}

{c['ひとこと']}

{'同じ場所を同じ角度から撮っています。' if pair else '作業前の写真です。'}撮影 {c['日付']}。お宅が特定できる部分は写していません。
うちはどう？ → プロフィールのリンクから30秒で判定できます。

{tags}"""
    gbp = f"""{c['地名']}で{t['名']}の内部を洗いました。

{mieta}

{c['ひとこと']}

「うちはどうだろう」と思ったら、洗いどき相談所で30秒で判定できます（プロが要るか、今は不要かを正直にお伝えします）。"""
    photos = []
    for b, a in c["組写真"]:
        photos.append(f"1枚目: {b}（作業前）→ 2枚目: {a}（作業後）※同一箇所・確認済み")
    for f in c["写真"]["汚水"]:
        photos.append(f"{f}（洗浄後の汚水）")
    for f in c["写真"]["before"]:
        if not any(f in p for p in c["組写真"]):
            photos.append(f"{f}（作業前）")
    return f"""# 投稿原稿｜{c['id']}

- 生成: tools/build-zukan.py（元データ data/zukan/{c['id']}.json）
- 状態: **未承認**（オーナーの週1回のまとめ承認を受けてから投稿する）
- 図鑑ページ: lp/media/araidoki/zukan/{c['id']}/
- 組写真: {'あり（' + c['組写真_確認'] + '）' if pair else 'なし。「ビフォーアフター」とは書かない'}

## 写真の順番
{chr(10).join('- ' + p for p in photos)}

## Instagram（キャプション {len(ig)}字）

```
{ig}
```

## Googleビジネスプロフィール 投稿（{len(gbp)}字）

```
{gbp}
```

- GBPの写真は1枚。組写真があるときは作業前の1枚（汚れが伝わるほう）
- ボタン「詳細」→ 図鑑ページのURL

## Facebook

Instagramと同じ本文をAPIでページにも投稿する（ハッシュタグは外す）。
"""


def main():
    cases = []
    for p in sorted(SRC.glob("*.json")):
        c = json.loads(p.read_text(encoding="utf-8"))
        kensa(c)
        cases.append(c)
    if not cases:
        sys.exit("data/zukan/ に案件がありません")
    cases.sort(key=lambda c: c["日付"], reverse=True)
    OUT.mkdir(parents=True, exist_ok=True)
    GENKO.mkdir(parents=True, exist_ok=True)
    for c in cases:
        d = OUT / c["id"]
        for k in ("before", "after", "汚水"):
            for f in c["写真"][k]:
                resize_copy(PHOTOS / f, d / "img" / f)
        (d / "index.html").write_text(page(c), encoding="utf-8")
        (GENKO / f"{c['id']}.md").write_text(genko(c), encoding="utf-8")
    (OUT / "index.html").write_text(index_page(cases), encoding="utf-8")
    print(f"図鑑 {len(cases)}件を書き出しました → {OUT}／原稿 → {GENKO}")


if __name__ == "__main__":
    main()
