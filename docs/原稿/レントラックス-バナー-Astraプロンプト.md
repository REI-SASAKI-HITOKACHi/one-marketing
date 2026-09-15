# レントラックス提出用バナー：Astra への画像生成プロンプト（2026-09-15 CMO）

提出サイズは **300×250 / 250×250 / 200×200 の3点**（`docs/レントラックス-Web提出の回答集.md` 項目12で回答済み）。
掲載先LPは `https://lp.onehitter.jp/mizumawari/`（水まわりセット）。

---

## ⚠️ 先に読むこと：文字は2案で出す

**日本語の文字をAIに描かせると、崩れたり別の字になったりします。**バナーは文字が命なので、両方投げてください。

- **A案（文字込み）** … そのまま使えれば最速。**必ず1文字ずつ目視で確認**すること
- **B案（文字なしの背景だけ）** … 文字はこちらで後から重ねる。**確実。A案が崩れたらこちら**

---

## 共通の指定（3サイズとも同じ。各プロンプトの冒頭に貼る）

```
Brand: ONE HITTER (Japanese house-cleaning company, Tokyo).
Palette (use exactly): deep navy #0D3B5C as the base, warm apricot #FFB894 as the single
accent, light cyan #6FD0E4 for small highlights, pale blue-grey #EDF4F8 for negative space.
White #FFFFFF for primary text.
Mood: clean, calm, trustworthy, professional. A real cleaning company, not a discount coupon.
Style: flat modern graphic design with generous negative space. Crisp geometric shapes.
NO photorealism of people's faces. NO stock-photo look. NO gradients that muddy the navy.
Composition: strong left-to-right or top-to-bottom hierarchy; one dominant price figure.
Output: flat web banner, sharp edges, no drop shadows heavier than 2px, no 3D bevels,
no glossy web-2.0 buttons, no starbursts, no exclamation marks, no sparkle/shine effects.
It must still read clearly when scaled down to 50% size.
```

---

## ① 300×250（レクタングル）

### A案（文字込み）

```
[共通の指定をここに貼る]

Create a 300x250 pixel web advertising banner.

Layout:
- Deep navy #0D3B5C background panel occupying the full canvas.
- Top-left: the wordmark "ONE HITTER" in white, clean geometric sans-serif, letter-spaced.
  Directly beneath it, smaller, in light cyan #6FD0E4: "ハウスクリーニング"
- Centre: the headline in white bold Japanese gothic: "浴室＋キッチン"
- Below the headline, the dominant element: "33,660円" very large in warm apricot #FFB894,
  with a smaller white "（税込）" immediately after it on the same baseline.
- Beneath the price, one thin apricot rule, then in white at small size:
  "下請けに出さない自社施工"
- Bottom strip: pale blue-grey #EDF4F8 band with navy text: "東京・千葉・神奈川"
- Bottom-right of that strip: a small apricot rounded rectangle with navy text "詳しく見る"

Render all Japanese text exactly as written, in a clean Japanese gothic typeface.
Do not invent, translate, or alter any characters. Do not add any text I have not specified.
```

### B案（文字なし）

```
[共通の指定をここに貼る]

Create a 300x250 pixel web banner BACKGROUND with NO TEXT AT ALL.

Deep navy #0D3B5C field. Along the right third, a subtle flat-illustration cluster of
household cleaning subjects rendered as simple geometric shapes in light cyan #6FD0E4 and
white line work: a bathtub silhouette, a kitchen sink with a faucet, a few water droplets.
Keep them small and understated — they are supporting texture, not the subject.
Leave the LEFT TWO THIRDS almost empty for text to be added later.
A pale blue-grey #EDF4F8 band across the bottom 18% of the canvas, empty.
A single warm apricot #FFB894 accent shape in one corner.
Absolutely no letters, numbers, logos, watermarks or characters of any language.
```

---

## ② 250×250（スクエア）

### A案（文字込み）

```
[共通の指定をここに貼る]

Create a 250x250 pixel square web advertising banner.

Layout, stacked vertically and centred:
- Top: wordmark "ONE HITTER" in white geometric sans-serif, letter-spaced, modest size.
- Middle: "浴室＋キッチン" in white bold Japanese gothic.
- Dominant element directly below: "33,660円" very large in warm apricot #FFB894,
  with smaller white "（税込）" after it.
- One thin apricot rule.
- Below: "自社施工" in white, small.
- Bottom band: pale blue-grey #EDF4F8 with navy #0D3B5C text "東京・千葉・神奈川"

Background: deep navy #0D3B5C. Keep the layout airy; the price must be the first thing seen.
Render all Japanese text exactly as written. Do not add any text I have not specified.
```

### B案（文字なし）

```
[共通の指定をここに貼る]

Create a 250x250 pixel square web banner BACKGROUND with NO TEXT AT ALL.
Deep navy #0D3B5C field. A restrained flat-geometric motif of water droplets and a simple
bathtub outline in light cyan #6FD0E4, confined to the bottom-right corner and kept subtle.
The upper two thirds must stay almost empty for text to be added later.
A pale blue-grey #EDF4F8 band across the bottom 18%, empty.
One warm apricot #FFB894 accent shape, small, top-left.
Absolutely no letters, numbers, logos, watermarks or characters of any language.
```

---

## ③ 200×200（スモールスクエア）

**この大きさでは要素を3つに絞ります。**詰め込むと全部読めなくなります。

### A案（文字込み）

```
[共通の指定をここに貼る]

Create a 200x200 pixel square web advertising banner. Extremely simple — only three elements.

- Top: wordmark "ONE HITTER" in white geometric sans-serif, small, letter-spaced.
- Centre, dominant, filling most of the canvas: "33,660円" in warm apricot #FFB894,
  with a much smaller white "（税込）" beneath it.
- Bottom: "浴室＋キッチン" in white, small, on a single line.

Background: deep navy #0D3B5C, plain, with one thin apricot rule separating the price
from the bottom line. No illustration, no icons, no decoration.
The price must remain legible at 100x100 pixels.
Render all Japanese text exactly as written. Do not add any text I have not specified.
```

### B案（文字なし）

```
[共通の指定をここに貼る]

Create a 200x200 pixel square web banner BACKGROUND with NO TEXT AT ALL.
Plain deep navy #0D3B5C field. One thin warm apricot #FFB894 horizontal rule at 72% height.
One very subtle light cyan #6FD0E4 water-droplet shape in the top-right corner, small.
Everything else empty, for text to be added later.
Absolutely no letters, numbers, logos, watermarks or characters of any language.
```

---

## 🚫 バナーに入れてはいけないもの（提出済みの禁止事項に対応）

先方への案件紹介文で、**当社からパートナー様に禁止事項として明示しています。**バナーも同じ縛りを受けます。

| 入れないもの | 理由 |
|---|---|
| **「98.8%」** | 根拠と一致しない。正しくは 98.6% |
| **「98.6%」も、このバナーでは使わない** | 使うなら「209名中206名／2023年1月〜2025年12月」の注記が必須。**250×250 に読める大きさで入らない。**注記なしで数字だけ出すのが一番危ない |
| **「★5.0」も同様に使わない** | クチコミ件数（24件）の併記が要る。同じ理由で入らない |
| 「日本一」「業界No.1」「地域最安」 | 根拠のない最上級表現。景表法 |
| 「必ず◯◯円」「追加料金は絶対にかからない」 | 金額の確約。実際の料金は現地確認後に確定する |
| 全国対応に見える表現 | **対応は東京・千葉・神奈川のみ** |
| 「！」「★」「今だけ」等の煽り | クローズドASPのパートナーはSEO・リスティングのプロ。品のないバナーは貼られない |

**価格は必ず「（税込）」を併記。** 2021年4月から総額表示が義務です。

## ✅ 使った事実の出どころ

- **33,660円**＝浴室クリーニング18,480円＋キッチンクリーニング18,480円（各単品・税込）から同時施工で3,300円引き。
  **本番LPに表示されている金額と一致**（`https://lp.onehitter.jp/mizumawari/`、9/15 実測）
- **下請けに出さない自社施工**／**東京・千葉・神奈川**＝`docs/price-master.md`

## 納品後にやること

1. `python3 tools/check-ad-consistency.py` を流して、バナーの金額とLPの表示が食い違っていないか機械で確認
2. CMO査読
3. 先方へ提出（オーナーかブラウザ担当が管理画面から）
