#!/usr/bin/env python3
"""10/15〜16 の便を deploy/netlify に当てる（配信はしない。オーナーのOKのあと、これを流してから配信する）。

  python3 tools/haishin-1016.py              # preview/haishin-1016/ に書き出す（確認用）
  python3 tools/haishin-1016.py --apply      # deploy/netlify に当てる

1. 11月の入口の直し4点（tools/nov-1015.py：水まわり2本・年末2本）
2. 水まわり 学習版7：今の版3 の振り分け（tools/furiwake-mizumawari.py。1 の後に当てる）
3. アンケート：Googleクチコミのお願いは自社名義のときだけ（lp/survey → build-site の copy_kanseihin）
/aircon/ 系には触らない。詳しくは docs/LP-水まわり7対3とT050-2026-10-16.md
"""
import argparse, importlib.util, pathlib, shutil, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
DEPLOY = ROOT / "deploy" / "netlify"

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--apply", action="store_true"); a = ap.parse_args()
    out = DEPLOY if a.apply else ROOT / "preview" / "haishin-1016"
    py = sys.executable
    subprocess.run([py, str(ROOT / "tools" / "nov-1015.py"), "--src", str(DEPLOY), "--out", str(out)], check=True)
    m = out / "mizumawari" / "index.html"
    subprocess.run([py, str(ROOT / "tools" / "furiwake-mizumawari.py"), "--src", str(m), "--out", str(m)], check=True)
    spec = importlib.util.spec_from_file_location("bs", ROOT / "tools" / "build-site.py")
    bs = importlib.util.module_from_spec(spec); sys.argv = ["x"]; spec.loader.exec_module(bs)
    tmp = ROOT / "preview" / "haishin-1016-kansei"
    shutil.rmtree(tmp, ignore_errors=True)
    bs.copy_kanseihin(tmp, "netlify")
    (out / "survey").mkdir(parents=True, exist_ok=True)
    shutil.copy(tmp / "survey" / "index.html", out / "survey" / "index.html")
    pages = [out / p / "index.html" for p in ("mizumawari", "mizumawari-b", "nenmatsu", "nenmatsu-b", "survey")]
    r = subprocess.run([py, str(ROOT / "tools" / "check-public-page.py")] + [str(p) for p in pages])
    if r.returncode:
        sys.exit("check-public-page が落ちました")
    print(("deploy/netlify に当てました。次は python3 tools/haishin-kakunin.py → 配信" if a.apply
           else f"確認用に書き出しました: {out.relative_to(ROOT)}/"))

if __name__ == "__main__":
    main()
