# バナー v2：Astra への修正プロンプト（2026-09-15 CMO）

v1 の納品物（`ONE-HITTER-A/B-{300x250,250x250,200x200}.png`）を見ての修正指示。

---

## v1 の評価：**作りは正確。足りないのは「広告として効くか」**

**先に、できていたところ。**

- 日本語が1文字も崩れていない（AI生成では珍しい）
- サイズが3つとも正確。配色も指定どおり（`#0D3B5C` / `#FFB894`）
- 金額・税込表記・エリアの記載が正しい。**禁止事項（98.8%・最上級表現・全国対応に見える表現）は1つも入っていない**

**足りないのはここ。**

| # | 問題 | なぜ効くか |
|---|---|---|
| 1 | **写真が1枚も無い** | ハウスクリーニングは**見た目が商品**。文字だけの紺色の箱は、提携サイトの中で「システムのお知らせ」に見える。**いちばん大きい欠点** |
| 2 | **250×250 と 200×200 にボタンが無い** | 押す場所が無いバナーは「告知」であって「広告」ではない |
| 3 | **300×250 の「詳しく見る」が小さく、右下で目立たない** | 押させる気が伝わらない |
| 4 | **200×200 は「何の 33,660円」か一瞬わからない** | 価格が主役なのに、対象が下端の小さい行にある |
| 5 | 紺一色で奥行きが無い | 3サイズとも同じ「のっぺり感」。**5は些細。1〜4を直せば消える** |

---

## 🚫 やってはいけない修正：**AIに「掃除の写真」を作らせない**

**「清掃前後の写真風の画像を生成する」は禁止です。**

当社の広告として出す以上、**実際の施工でない画像を「施工例」に見えるかたちで載せると、景表法上の問題になります**（優良誤認）。
**ビフォーアフター風の生成画像は、その典型です。**

→ **写真は当社の実写を使います。**`assets/photos/`（7月撮影の新着24枚を含む計54枚）。
→ **Astra には「写真を入れる枠組み」を作らせて、写真は当社ではめ込みます。**

---

## 修正プロンプト

### 共通（各プロンプトの冒頭に貼る）

```
Brand: ONE HITTER (Japanese house-cleaning company, Tokyo).
Palette (use exactly): deep navy #0D3B5C base, warm apricot #FFB894 single accent,
light cyan #6FD0E4 small highlights, pale blue-grey #EDF4F8 negative space, white #FFFFFF text.
Mood: clean, calm, trustworthy. A real cleaning company, not a discount coupon.
Style: flat modern graphic design, crisp geometry, generous negative space.
No drop shadows heavier than 2px, no 3D bevels, no glossy buttons, no starbursts,
no sparkle effects, no exclamation marks. Must stay legible at 50% scale.

IMPORTANT: Do NOT generate any photograph or illustration of cleaning, bathrooms,
kitchens, before/after results, water, dirt, or people. Leave a clearly defined empty
region where a real photograph will be placed afterwards. That region must be a plain
flat block of #EDF4F8 with no texture, no placeholder icon, and no text.
```

### ① 300×250

```
[共通をここに貼る]

Create a 300x250 pixel web advertising banner with a dedicated photo slot.

Layout — two horizontal bands:
- TOP BAND, exactly the upper 45% of the canvas: a plain flat #EDF4F8 rectangle,
  completely empty. This is the photo slot. Nothing inside it.
- BOTTOM BAND, the lower 55%: deep navy #0D3B5C.
  - Top-left of the navy band: "ONE HITTER" in white geometric sans-serif, small, letter-spaced.
  - Below it, white bold Japanese gothic, one line: "浴室＋キッチン"
  - Dominant: "33,660円" very large in warm apricot #FFB894, with smaller white "（税込）"
    on the same baseline.
  - Bottom-left, small white text: "東京・千葉・神奈川"
  - BOTTOM-RIGHT: a solid warm apricot #FFB894 rounded rectangle button, clearly larger
    than in a typical banner — at least 96x30 pixels — with navy #0D3B5C bold text
    "詳しく見る". This button must be the second thing the eye reaches after the price.

Render all Japanese text exactly as written. Add no text I have not specified.
```

### ② 250×250

```
[共通をここに貼る]

Create a 250x250 pixel square web advertising banner with a dedicated photo slot.

- TOP 40% of the canvas: a plain flat #EDF4F8 rectangle, completely empty (photo slot).
- REMAINING 60%: deep navy #0D3B5C, contents stacked and centred:
  - "ONE HITTER" white geometric sans-serif, small, letter-spaced
  - "浴室＋キッチン" white bold Japanese gothic
  - "33,660円" very large in warm apricot #FFB894, smaller white "（税込）" after it
  - A solid warm apricot #FFB894 rounded rectangle button, at least 88x28 pixels,
    navy bold text "詳しく見る", centred, with clear breathing room above and below

Drop "自社施工" and "東京・千葉・神奈川" from this size — there is not room for them
and still have a button. The button matters more.

Render all Japanese text exactly as written. Add no text I have not specified.
```

### ③ 200×200

```
[共通をここに貼る]

Create a 200x200 pixel square web advertising banner. Only four elements, no photo slot
(the canvas is too small to divide).

Stacked, centred, on a plain deep navy #0D3B5C field:
1. "ONE HITTER" white geometric sans-serif, small, letter-spaced, at the very top.
2. "浴室＋キッチン" in white — place this ABOVE the price, not below it. The reader must
   know what the number refers to before they read the number.
3. "33,660円" very large in warm apricot #FFB894, with a much smaller white "（税込）".
4. A solid warm apricot #FFB894 rounded rectangle button at the bottom, at least 76x24
   pixels, navy bold text "詳しく見る".

No illustration, no icons, no decoration, no horizontal rules.
The price must stay legible at 100x100 pixels.

Render all Japanese text exactly as written. Add no text I have not specified.
```

---

## 納品後にこちらでやること

1. **写真をはめる。**`assets/photos/` から、浴室またはキッチンの**施工後**の1枚を選ぶ
   - **ビフォーアフターの並置はバナーではやらない**（200〜300pxでは両方とも潰れて、かえって安っぽくなる）
   - **汚水の写真は使わない**（SNSでは反応が取れるが、提携サイトのバナーとしては品が落ちる）
2. `python3 tools/check-ad-consistency.py` で金額とLPの表示の一致を確認
3. CMO査読 → 提出（**公開後でよいと先方が回答済み。公開のブロッカーではない**）

## 変わっていない禁止事項

98.8%／98.6%／★5.0 は**バナーに入れない**（注記が入らないため）。最上級表現・金額の確約・全国対応に見える表現も不可。価格には必ず「（税込）」。
