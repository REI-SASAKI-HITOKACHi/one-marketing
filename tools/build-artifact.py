#!/usr/bin/env python3
"""LPをArtifactで公開できる1ファイルにまとめる。

lp/<name>/index.html は img/ を相対パスで参照している（実際の配信ではこちらが正）。
Artifactのビューアは外部画像を読み込めないため、公開用にだけ画像を data URI に
埋め込んだコピーを dist/ に書き出す。

  python3 tools/build-artifact.py            # 両方
  python3 tools/build-artifact.py aircon     # 片方だけ
"""
import base64
import mimetypes
import pathlib
import re
import sys

def strip_comments(html: str) -> str:
    """公開する文書からコメントを落とす。

    lp/ 配下のソースには、なぜその値なのかを書いた注記を残してある。
    ただし公開ページのソースに設計メモが並んでいるのは正常な状態ではないので、
    書き出すときに外す。CSSのコメントは <style> の中だけを対象にする
    （JavaScript の中の /* */ を巻き込まないため）。
    """
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)

    def _style(m):
        return m.group(1) + re.sub(r"/\*.*?\*/", "", m.group(2), flags=re.S) + m.group(3)

    html = re.sub(r"(<style[^>]*>)(.*?)(</style>)", _style, html, flags=re.S)
    # コメントを抜いた跡に残る空行を畳む
    html = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", html)
    return html


ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"


def inline(name: str) -> pathlib.Path:
    src = ROOT / "lp" / name / "index.html"
    html = src.read_text(encoding="utf-8")

    def repl(m: re.Match) -> str:
        rel = m.group(1)
        path = src.parent / rel
        if not path.exists():
            raise SystemExit(f"{src}: 参照先が見つかりません -> {rel}")
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = base64.b64encode(path.read_bytes()).decode()
        return f'src="data:{mime};base64,{data}"'

    html, n = re.subn(r'src="((?!data:|https?:)[^"]+)"', repl, html)
    DIST.mkdir(exist_ok=True)
    out = DIST / f"lp-{name}.html"
    out.write_text(strip_comments(html), encoding="utf-8")
    print(f"{out}  画像{n}点  {out.stat().st_size // 1024}KB")
    return out


if __name__ == "__main__":
    for name in sys.argv[1:] or ["aircon", "mizumawari"]:
        inline(name)
