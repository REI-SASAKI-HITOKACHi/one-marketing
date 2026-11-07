#!/usr/bin/env python3
"""和真さんのイラスト案（SVG・手組み）を3案つくる。写真は使わない（座標は元写真の重ね合わせで目で合わせた値）。

20261107-02-web-inflow。枠は lp/_staff/staff.svg＝1:1・132px丸（原画1200×1200）。viewBox は 0 0 1000 1000。
自動のベクター化（tools/make-staff-illust-v2.py）は、目・服の形が崩れて不自然だったため、
輪郭・髪・目鼻口を手で組んだ。写真を外部に渡さず、元写真もこのリポジトリに入れない。

  python3 tools/make-staff-illust-hand.py [出力フォルダ]     # 既定 deliver/staff-illust-2026-11/
  a 基本（表情は元写真のまま）／b a＋墨の線でふち取り／c 口角を少し上げた（似ている感じは a より下がる）
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

SKIN, SKIN_SH, SKIN_HI = "#d2aa91", "#bf977f", "#dcb8a1"
HAIR, HAIR_HI = "#3d3d40", "#5b5b60"
SHIRT, SHIRT_SH = "#4c4f57", "#3c3e45"
BG = "#e8f0ee"


def svg(smile=0, outline=False):
    ol = ' stroke="#2c2626" stroke-width="5" stroke-linejoin="round"' if outline else ""
    m = smile  # 口角を上げる量
    mouth = (f'<path d="M446 {578-m} C470 566 485 568 500 574 C515 568 530 566 554 {578-m} '
             f'C530 {600+m} 470 {600+m} 446 {578-m} Z" fill="#a06f6c"/>'
             f'<path d="M446 {578-m} C475 {586+m} 525 {586+m} 554 {578-m}" stroke="#5e3c3c" stroke-width="6" fill="none" stroke-linecap="round"/>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000" width="1200" height="1200">
  <defs><clipPath id="face"><path d="M345 300 C345 255 420 235 500 235 C580 235 655 255 655 300 L660 440 C662 520 640 590 600 640 C570 680 535 698 500 698 C465 698 430 680 400 640 C360 590 340 520 342 440 Z"/></clipPath></defs>
  <rect width="1000" height="1000" fill="{BG}"/>
  <path d="M70 1000 C80 900 110 830 215 800 L350 748 L650 748 L785 800 C890 830 925 900 935 1000 Z" fill="{SHIRT}"{ol}/>
  <path d="M350 748 C372 795 432 842 500 842 C568 842 628 795 650 748 L632 730 C602 790 552 815 500 815 C448 815 398 790 368 730 Z" fill="{SHIRT_SH}"/>
  <path d="M412 630 C414 690 410 725 372 733 C400 790 450 815 500 815 C550 815 600 790 628 733 C590 725 600 690 604 630 Z" fill="{SKIN_SH}"{ol}/>
  <path d="M342 440 C318 438 318 485 332 522 C340 540 352 545 360 540 Z" fill="{SKIN}"{ol}/>
  <path d="M660 440 C686 436 684 485 670 522 C662 540 650 545 642 540 Z" fill="{SKIN}"{ol}/>
  <path d="M338 466 C330 474 332 500 342 516" stroke="{SKIN_SH}" stroke-width="7" fill="none" stroke-linecap="round"/>
  <path d="M664 466 C672 474 670 500 660 516" stroke="{SKIN_SH}" stroke-width="7" fill="none" stroke-linecap="round"/>
  <path d="M345 300 C345 255 420 235 500 235 C580 235 655 255 655 300 L660 440 C662 520 640 590 600 640 C570 680 535 698 500 698 C465 698 430 680 400 640 C360 590 340 520 342 440 Z" fill="{SKIN}"{ol}/>
  <g clip-path="url(#face)">
    <path d="M330 420 C340 540 372 610 430 668 C455 690 480 700 500 700 C455 650 400 590 384 520 C376 485 376 450 380 420 Z" fill="{SKIN_SH}" opacity=".75"/>
    <path d="M670 420 C662 540 632 610 575 668 C552 690 525 700 500 700 C545 650 600 590 616 520 C624 485 624 450 620 420 Z" fill="{SKIN_SH}" opacity=".75"/>
    <path d="M440 262 C480 250 540 252 575 268 C560 296 470 300 440 262 Z" fill="{SKIN_HI}"/>
  </g>
  <path d="M424 551 C452 558 480 554 500 560 C520 554 548 558 578 551 C582 562 574 574 556 578 C530 566 470 566 446 578 C428 574 420 562 424 551 Z" fill="#6f5a52" opacity=".36"/>
  <path d="M452 624 C470 640 530 640 548 624 C556 656 538 684 500 690 C462 684 444 656 452 624 Z" fill="#6f5a52" opacity=".42"/>
  <path d="M322 450 C316 380 322 300 360 252 C382 220 420 196 452 176 C462 168 470 160 478 156 C490 164 498 168 505 168 C525 160 545 158 565 164 C580 158 592 152 600 148 C600 156 604 162 612 172 C648 196 676 244 682 310 C686 360 678 410 672 450 C666 400 660 340 650 310 C630 262 575 245 500 245 C430 245 372 262 352 310 C340 350 332 400 322 450 Z" fill="{HAIR}"{ol}/>
  <path d="M424 200 C452 180 490 172 520 180" stroke="{HAIR_HI}" stroke-width="10" fill="none" stroke-linecap="round" opacity=".7"/>
  <path d="M372 392 C395 372 430 366 458 372 C440 382 405 390 372 392 Z" fill="#37312f"/>
  <path d="M545 372 C575 366 610 372 630 392 C598 390 563 382 545 372 Z" fill="#37312f"/>
  <path d="M388 424 C405 408 440 408 455 424 C440 432 405 434 388 424 Z" fill="#f4ece6"/>
  <path d="M545 420 C562 406 598 406 612 420 C598 428 562 430 545 420 Z" fill="#f4ece6"/>
  <circle cx="422" cy="421" r="10" fill="#2e2523"/><circle cx="578" cy="417" r="10" fill="#2e2523"/>
  <path d="M385 424 C405 405 442 405 458 424" stroke="#2e2523" stroke-width="7" fill="none" stroke-linecap="round"/>
  <path d="M542 420 C558 403 597 403 615 420" stroke="#2e2523" stroke-width="7" fill="none" stroke-linecap="round"/>
  <path d="M488 432 C484 470 478 495 462 512 C478 528 522 528 538 512 C522 495 516 470 512 432" stroke="{SKIN_SH}" stroke-width="7" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
  <ellipse cx="474" cy="520" rx="9" ry="5" fill="#7a5a50"/><ellipse cx="526" cy="520" rx="9" ry="5" fill="#7a5a50"/>
  {mouth}
</svg>
'''


def main():
    out = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "deliver" / "staff-illust-2026-11"
    out.mkdir(parents=True, exist_ok=True)
    for key, kw in (("a", {}), ("b", {"outline": True}), ("c", {"smile": 7})):
        (out / f"kazuma-{key}.svg").write_text(svg(**kw), encoding="utf-8")
    print("ok", out)


if __name__ == "__main__":
    main()
