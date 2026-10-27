#!/usr/bin/env python3
"""SNS広告の再プレゼン資料（嶺さんの査読用・1枚）。依頼 20261027-01-web-inflow。
  python3 tools/build-ad-presen.py   → deliver/ad-creatives-2026-10/プレゼン1枚.png
A1・A2・B1・B2（deliver/ad-creatives-2026-10/）を並べ、狙い・誰に・どの面・予算・止める基準・調査から取り入れたことを1行ずつ。
予算・止める基準は docs/SNS広告-再検討案-2026-10-16.md の案（日1,000円×14日＝上限14,000円）を引いたもの。出稿はしない。
"""
import pathlib
import subprocess

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / "deliver" / "ad-creatives-2026-10"
FF = imageio_ffmpeg.get_ffmpeg_exe()
TMP = ROOT / "dist" / "ad-creatives" / "_tmp"
FONTS = ROOT / "assets" / "fonts"
INK, DEEP = (13, 59, 92), (6, 26, 42)


def font(s, w=700):
    return ImageFont.truetype(str(FONTS / f"ZenKakuGothicNew-{w}.ttf"), s)


def frames(video, name, ts):
    TMP.mkdir(parents=True, exist_ok=True)
    out = []
    for i, t in enumerate(ts):
        p = TMP / f"pz-{name}-{i}.png"
        subprocess.run([FF, "-y", "-loglevel", "error", "-ss", str(t), "-i", str(video), "-frames:v", "1",
                        "-vf", "scale=210:374", str(p)], check=True)
        out.append(Image.open(p).convert("RGB"))
    return out


def wrap(d, text, f, w):
    lines, cur = [], ""
    for ch in text:
        if d.textlength(cur + ch, font=f) > w:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    return lines + [cur]


ROWS = [
    ("A1　エアコン・静止画", "A1-エアコン-静止画.png", None,
     [("狙い", "暖房を使う前に、吹き出し口の奥を見てもらい、11月の予約ページへ送る。11月は1台10%引き（9,702円・税込）と防カビコート無料（3,300円・税込）を1画面で見せる"),
      ("誰に", "江戸川区と隣接（江東・墨田・葛飾・市川・浦安）。年齢・性別は絞らず、結果を見て絞る"),
      ("どの面", "Instagram フィード・Facebook フィード（4:5）。リンク先は予約ページ（?src=ig_ad／?src=fb_ad）"),
      ("予算", "上限14,000円（日1,000円×14日）のうち、エアコンのテーマに7,000円（日500円）の案。静止画と動画は同じ条件で並べて比べる"),
      ("止める基準", "7日で予約ページ到達が0〜数件なら、冒頭の画か文面を替えて1回だけやり直す。14日（上限）で予約の送信が0なら停止"),
      ("調査から", "見出し1つ・価格の帯・行動の促しを1つに絞った（字幕を短く／最後に具体的な行動）")]),
    ("A2　エアコン・縦動画（11.5秒）", "A2-エアコン-動画.mp4", (0.6, 4.0, 7.2, 10.2),
     [("狙い", "洗い出した水と、洗ったあとの内部を見せて、A1と同じ予約ページへ送る。最後のカードに10%引きと防カビ無料の1行"),
      ("誰に", "A1と同じ（動画は見てもらえる人が広がるため、同じ条件で比べる）"),
      ("どの面", "Instagram リール・Facebook リール（9:16）。リンク先は A1 と同じ"),
      ("予算", "A1と同じ枠の内数。動画で3秒視聴率が目安（米国479本の中央値 20.9%）を下回れば、冒頭の画を差し替え"),
      ("止める基準", "A1と同じ。いつでも、日予算を超える・審査で不承認・不審な動きがあればその場で停止"),
      ("調査から", "1秒目に洗い出した水／11.5秒（15秒以内）／縦型・音あり（自作BGM）／和真さんの現場の実写（スマホ撮影）／最後に「空いている日を見る」")]),
    ("B1　年末の水まわり・静止画", "B1-水まわり-静止画.png", None,
     [("狙い", "年末の大掃除の前に、換気扇フィルターの油汚れを見せ、レンジフード・浴室・キッチンの11月10%引き（1箇所 16,632円・税込）を知らせる"),
      ("誰に", "A1と同じ。年末の大掃除を考え始める人（地域のみで絞る）"),
      ("どの面", "Instagram フィード・Facebook フィード（4:5）。リンク先は予約ページ"),
      ("予算", "上限14,000円のうち、水まわりのテーマに7,000円（日500円）の案"),
      ("止める基準", "A1と同じ（7日／14日／いつでも）"),
      ("調査から", "写真を画面の約半分に大きく／見出し1つ／価格と対象（1箇所）を下の帯に固定")]),
    ("B2　年末の水まわり・縦動画（11.5秒）", "B2-水まわり-動画.mp4", (0.6, 3.6, 6.6, 10.4),
     [("狙い", "B1と同じ。油汚れの写真3枚で見せて、最後のカードで11月10%引きを知らせる"),
      ("誰に", "B1と同じ"),
      ("どの面", "Instagram リール・Facebook リール（9:16）"),
      ("予算", "B1と同じ枠の内数。素材が静止画のため、動きは拡大だけ。水まわりの現場動画が撮れたら差し替え"),
      ("止める基準", "A1と同じ"),
      ("調査から", "1秒目に最も汚れの強い画（フィルターの油汚れ）／11.5秒／見出しは1場面1つ")]),
]


def main():
    W, rowh = 2400, 620
    H = 400 + rowh * 4 + 190
    im = Image.new("RGB", (W, H), (246, 243, 238))
    d = ImageDraw.Draw(im)
    d.text((50, 30), "SNS広告の再プレゼン（嶺さんの査読用）", font=font(52, 900), fill=DEEP)
    heads = ["2026-10-27 作成 ／ web-inflow ／ 出稿はしていません。合格をいただいてから、cmo→browser で設定します（お金は動きません）。",
             "前提：Instagram／Facebook。地域は江戸川区と隣接。予算は案で、上限14,000円（日1,000円×14日）。根拠になる過去実績は無いため、金額の妥当性は未検証。止める基準は案で、オーナーの許容額に合わせて変えられます。",
             "前回（10/21に低いと言われた版）との違い：静止画をゆっくり動かした21〜23秒のリール → 現場の実写・11.5秒・見出し1つ・最後に具体的な行動の促し。業界横断の調査（20例・公式3社と大規模分析）から型を取り入れました。",
             "10%引きは「1箇所のご依頼が対象」。防カビコート無料は「11月のネット予約・エアコン1台分・作業日11/1〜11/30」（cmo 決定）。"]
    yh = 105
    for h in heads:
        for ln in wrap(d, h, font(26, 500), W - 100):
            d.text((50, yh), ln, font=font(26, 500), fill=(60, 70, 80))
            yh += 36
    y0 = 330
    for k, (title, fn, ts, items) in enumerate(ROWS):
        y = y0 + k * rowh
        d.rounded_rectangle((30, y, W - 30, y + rowh - 20), radius=18, fill=(255, 255, 255), outline=(215, 210, 200))
        d.text((60, y + 18), title, font=font(36, 900), fill=INK)
        if ts:
            fr = frames(D / fn, fn[:2], ts)
            for i, f in enumerate(fr):
                im.paste(f, (60 + i * 220, y + 80))
            im.paste(Image.new("RGB", (1, 1)), (0, 0))
        else:
            st = Image.open(D / fn)
            st = st.resize((420, int(420 * st.height / st.width)))
            im.paste(st, (60, y + 80))
        tx = 60 + 4 * 220 + 40 if ts else 60 + 470 + 40
        if ts:
            tx = 60 + 4 * 220 + 30
        yy = y + 80
        for label, text in items:
            d.text((tx, yy), label, font=font(26, 900), fill=INK)
            lines = wrap(d, text, font(25, 500), W - 60 - tx - 150)
            for ln in lines:
                d.text((tx + 140, yy), ln, font=font(25, 500), fill=(40, 50, 60))
                yy += 34
            yy += 14
    d.text((50, H - 150), "確認できていない点：Meta の広告審査と、広告アカウント上での動画の表示。9,702円・16,632円は税込の10%引き（10,780円・18,480円の90%）。", font=font(25, 500), fill=(60, 70, 80))
    d.text((50, H - 110), "守った点：本舗のロゴ・社名・番号／お客様の名前／電話番号なし。出張費の言い切りなし。汚水に台数・杯数なし。素材は目視で確認済み。", font=font(25, 500), fill=(60, 70, 80))
    d.text((50, H - 70), "ファイル：deliver/ad-creatives-2026-10/（A1・B1 PNG／A2・B2 MP4／確認ページ.png／このプレゼン1枚.png）　調査：docs/動画広告-業種を問わない調査-1枚-2026-10-24.md", font=font(25, 500), fill=(60, 70, 80))
    out = D / "プレゼン1枚.png"
    im.save(out)
    print(out, im.size)


if __name__ == "__main__":
    main()
