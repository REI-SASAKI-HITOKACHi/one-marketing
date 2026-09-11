#!/usr/bin/env python3
"""SNS投稿の実行係。data/sns-queue.json の「承認済み・予定時刻を過ぎたもの」を Instagram と Facebookページに出す。

なぜ手で投稿しないか：オーナー決定（2026-09-11）で投稿は全部このスレッドが実行し、1回の承認で以後は自動にする。
承認の証拠は queue の status（approved）。draft のものはこのスクリプトが絶対に触らない。

  python3 tools/sns-post.py --dry-run             # 出す予定のものと、公開URL・本文を表示するだけ（API に書き込まない）
  python3 tools/sns-post.py                       # 予定時刻 <= 今 の approved を順に投稿
  python3 tools/sns-post.py --id w01-1            # 1件だけ（予定時刻は無視。status は approved が要る）
  python3 tools/sns-post.py --id w01-1 --only-container   # Instagram のコンテナを作って状態を見るだけ。公開しない
  python3 tools/sns-post.py --test-container assets/photos/IMG_7976.jpg   # 疎通確認：試し画像でコンテナを1つ作る。公開しない
  python3 tools/sns-post.py --check               # フォロワー数・投稿数（meta_client.check）

流れ
  1. 媒体を dist/sns-media/<id>-<n>.jpg|.mp4 に複製して整える（長辺1440px・JPEG q85・縦横比を 4:5〜1.91:1 に紙色で余白。切り抜きはしない）
  2. tools/deploy-sns-media.py で公開URLにする（Graph API は公開URLからしか取り込めない）
  3. Instagram: コンテナ作成 → status_code が FINISHED になるまで待つ → media_publish → permalink
     Facebook : /{page_id}/photos（複数なら unpublished で上げて /feed に attached_media）／動画は /{page_id}/videos の file_url
  4. data/sns-log.json に追記し、queue の status を posted（失敗なら failed＋error）にする

再試行：5xx・レート制限は 3回まで（10秒→30秒）。それでも駄目なら failed。片方の媒体だけ成功したときは
その結果を results に残し、次回はもう片方だけ出す（二重投稿を防ぐ）。
トークン：~/.config/one-hitter/meta.json。ページトークンは /me/accounts から取り ~/.config/one-hitter/meta-page.json に控える。
どちらも print しない。エラー文は meta_client.mask() を通す。
"""
import argparse
import datetime as dt
import importlib.util
import json
import pathlib
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import meta_client as mc  # noqa: E402
from meta_client import GraphError, mask  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
QUEUE = ROOT / "data" / "sns-queue.json"
LOG = ROOT / "data" / "sns-log.json"
MEDIA_DIR = ROOT / "dist" / "sns-media"
JST = dt.timezone(dt.timedelta(hours=9))
PAPER = (0xFB, 0xFA, 0xF7)          # 余白の紙色。LP・カードと同じ
MAX_SIDE = 1440                     # IG が受ける横幅の上限
RATIO_MIN, RATIO_MAX = 4 / 5, 1.91  # IG フィード／カルーセルの縦横比
RETRY_WAIT = (10, 30)               # 1回目失敗→10秒、2回目失敗→30秒


def _load_deploy():
    """tools/deploy-sns-media.py はハイフン入りなので importlib で読む。"""
    p = pathlib.Path(__file__).resolve().parent / "deploy-sns-media.py"
    spec = importlib.util.spec_from_file_location("deploy_sns_media", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---------- queue / log ----------

def load_queue() -> list:
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def save_queue(q: list) -> None:
    QUEUE.write_text(json.dumps(q, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_log(rec: dict) -> None:
    log = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else []
    log.append(rec)
    LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def now_jst() -> dt.datetime:
    return dt.datetime.now(JST)


def due(entry: dict, now: dt.datetime) -> bool:
    return dt.datetime.fromisoformat(entry["scheduled_at"]) <= now


# ---------- media prep ----------

def prep_image(src: pathlib.Path, dst: pathlib.Path) -> tuple[int, int]:
    """IG の制約に合わせて複製する。汚れの写真を切り抜くと「加工」になるので、比率が外れるときは紙色で余白を足す。"""
    from PIL import Image
    im = Image.open(src)
    im = im.convert("RGB")
    w, h = im.size
    r = w / h
    if r < RATIO_MIN:      # 縦長すぎ → 左右に余白
        nw = int(round(h * RATIO_MIN))
        bg = Image.new("RGB", (nw, h), PAPER)
        bg.paste(im, ((nw - w) // 2, 0))
        im = bg
    elif r > RATIO_MAX:    # 横長すぎ → 上下に余白
        nh = int(round(w / RATIO_MAX))
        bg = Image.new("RGB", (w, nh), PAPER)
        bg.paste(im, (0, (nh - h) // 2))
        im = bg
    im.thumbnail((MAX_SIDE, MAX_SIDE))
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, "JPEG", quality=85, optimize=True)
    return im.size


def ffmpeg_exe() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def probe_video(path: pathlib.Path) -> dict:
    """ffprobe が無い環境なので ffmpeg -i の標準エラー出力から読む。"""
    out = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr
    info = {"video": None, "audio": None, "w": 0, "h": 0, "sec": 0.0}
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", out)
    if m:
        info["sec"] = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
    m = re.search(r"Video: (\w+).*?(\d{2,5})x(\d{2,5})", out)
    if m:
        info["video"], info["w"], info["h"] = m[1], int(m[2]), int(m[3])
    m = re.search(r"Audio: (\w+)", out)
    if m:
        info["audio"] = m[1]
    return info


def prep_video(src: pathlib.Path, dst: pathlib.Path) -> dict:
    """リールの条件（9:16・90秒以内・h264/aac）を確かめて複製する。無音なら無音AACを足す（Meta 側の取り込み失敗を避けるため）。"""
    info = probe_video(src)
    if info["video"] != "h264":
        raise ValueError(f"{src.name}: 映像が h264 ではありません（{info['video']}）")
    if abs(info["w"] / info["h"] - 9 / 16) > 0.01:
        raise ValueError(f"{src.name}: 9:16 ではありません（{info['w']}x{info['h']}）")
    if info["sec"] > 90:
        raise ValueError(f"{src.name}: 90秒を超えています（{info['sec']:.1f}s）")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if info["audio"] == "aac":
        shutil.copyfile(src, dst)
    else:
        subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(src),
                        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                        "-shortest", "-c:v", "copy", "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", str(dst)], check=True)
        info["audio"] = "aac(無音を追加)"
    return info


def prepare_media(entry: dict) -> list[pathlib.Path]:
    """queue の media を dist/sns-media/<id>-<n>.<ext> に整えて置き、そのパス一覧を返す。"""
    out = []
    for n, rel in enumerate(entry["media"], 1):
        src = ROOT / rel
        if not src.exists():
            raise FileNotFoundError(f"{entry['id']}: {rel} がありません")
        if entry["type"] == "reel":
            dst = MEDIA_DIR / f"{entry['id']}-{n}.mp4"
            info = prep_video(src, dst)
            print(f"    動画 {rel} → {dst.relative_to(ROOT)}  {info['w']}x{info['h']} {info['sec']:.1f}s {info['video']}/{info['audio']}")
        else:
            dst = MEDIA_DIR / f"{entry['id']}-{n}.jpg"
            size = prep_image(src, dst)
            print(f"    画像 {rel} → {dst.relative_to(ROOT)}  {size[0]}x{size[1]}")
        out.append(dst)
    return out


# ---------- Graph API（再試行つき） ----------

def api(path, params=None, method="GET", data=None, token=None, attempts=3):
    """5xx・レート制限は待って再試行。それ以外（4xx の指定ミスなど）は即座に上げる。"""
    for i in range(attempts):
        try:
            return mc.request(path, params, method, data, token=token)
        except GraphError as e:
            if i < attempts - 1 and e.retryable():
                print(f"    再試行 {i + 1}/{attempts - 1}（{e.status} code={e.code}）{RETRY_WAIT[i]}秒待つ")
                time.sleep(RETRY_WAIT[i])
                continue
            raise


def wait_container(cid: str, timeout: int, label: str) -> str:
    """コンテナの status_code が FINISHED になるまで待つ。ERROR / EXPIRED は例外。"""
    t0 = time.time()
    interval = 5
    while True:
        r = api(cid, {"fields": "status_code,status"})
        st = r.get("status_code")
        if st == "FINISHED":
            print(f"    {label} {cid}: FINISHED（{time.time() - t0:.0f}秒）")
            return st
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"{label} {cid}: {st} {mask(str(r.get('status')))}")
        if time.time() - t0 > timeout:
            raise RuntimeError(f"{label} {cid}: {timeout}秒待っても {st}")
        time.sleep(interval)
        interval = min(interval * 1.5, 20)


def ig_post(entry: dict, urls: list[str], only_container: bool) -> dict:
    """Instagram。IMAGE／CAROUSEL／REELS を分けて作り、FINISHED を待ってから公開する。"""
    ig = mc.conf()["ig_user_id"]
    cap = entry["caption"]
    if entry["type"] == "image":
        c = api(f"{ig}/media", method="POST", data={"image_url": urls[0], "caption": cap})
        cid = c["id"]
        wait_container(cid, 180, "IMAGE")
    elif entry["type"] == "carousel":
        kids = []
        for u in urls:
            c = api(f"{ig}/media", method="POST", data={"image_url": u, "is_carousel_item": "true"})
            kids.append(c["id"])
        for k in kids:
            wait_container(k, 180, "子")
        c = api(f"{ig}/media", method="POST", data={"media_type": "CAROUSEL", "children": ",".join(kids), "caption": cap})
        cid = c["id"]
        wait_container(cid, 180, "CAROUSEL")
    elif entry["type"] == "reel":
        c = api(f"{ig}/media", method="POST", data={"media_type": "REELS", "video_url": urls[0], "caption": cap, "share_to_feed": "true"})
        cid = c["id"]
        wait_container(cid, 900, "REELS")   # 動画の取り込みは数分かかる
    else:
        raise ValueError(entry["type"])
    if only_container:
        print(f"    --only-container: コンテナ {cid} を作って止めます（公開しない）")
        return {"container_id": cid, "published": False}
    pub = api(f"{ig}/media_publish", method="POST", data={"creation_id": cid})
    mid = pub["id"]
    info = api(mid, {"fields": "permalink,media_type"})
    return {"container_id": cid, "media_id": mid, "permalink": info.get("permalink"), "published": True}


def fb_message(entry: dict) -> str:
    """Facebook用の本文。ハッシュタグの行は外す（Facebookでは効かず、宣伝臭くなる）。末尾にLPのリンク（?src=fb）"""
    lines = [ln for ln in entry["caption"].splitlines() if not ln.strip().startswith("#")]
    body = "\n".join(lines).rstrip()
    return body + ("\n\n" + entry["link"] if entry.get("link") else "")


def fb_post(entry: dict, urls: list[str]) -> dict:
    """Facebookページ。写真1枚は /photos、複数は unpublished で上げて /feed に束ねる、動画は /videos。"""
    page = mc.conf()["page_id"]
    tok = mc.page_token(page)
    msg = fb_message(entry)
    if entry["type"] == "reel":
        r = api(f"{page}/videos", method="POST", data={"file_url": urls[0], "description": msg}, token=tok)
        vid = r["id"]
        return {"video_id": vid, "post_id": vid, "permalink": f"https://www.facebook.com/{page}/videos/{vid}", "media_ids": [vid]}
    if len(urls) == 1:
        r = api(f"{page}/photos", method="POST", data={"url": urls[0], "message": msg}, token=tok)
        pid, post_id = r["id"], r.get("post_id")
        media_ids = [pid]
    else:
        media_ids = []
        for u in urls:
            r = api(f"{page}/photos", method="POST", data={"url": u, "published": "false"}, token=tok)
            media_ids.append(r["id"])
        data = {"message": msg}
        for i, m in enumerate(media_ids):
            data[f"attached_media[{i}]"] = json.dumps({"media_fbid": m})
        r = api(f"{page}/feed", method="POST", data=data, token=tok)
        post_id = r["id"]
    link = None
    if post_id:
        try:
            link = api(post_id, {"fields": "permalink_url"}, token=tok).get("permalink_url")
        except GraphError:
            pass
    return {"post_id": post_id, "permalink": link, "media_ids": media_ids}


# ---------- 1件を処理 ----------

def process(entry: dict, dry_run: bool, only_container: bool, deployer) -> None:
    print(f"\n■ {entry['id']}  {entry['scheduled_at']}  {entry['type']}  {'/'.join(entry['platforms'])}  [{entry['status']}]"
          + (f"  {entry.pop('_due')}" if "_due" in entry else ""))
    if entry.get("memo"):
        print("  ", entry["memo"])
    paths = prepare_media(entry)
    urls = deployer.publish_files(paths, dry_run=dry_run)
    ulist = [urls[str(p)] for p in paths]
    for u in ulist:
        print("    公開URL:", u, "（dry-run：未配信）" if dry_run else "")
    if dry_run:
        print("    IG caption:", entry["caption"].replace("\n", "⏎")[:80], "…")
        if "facebook" in entry["platforms"]:
            print("    FB message 末尾:", fb_message(entry).splitlines()[-1])
        return

    results = entry.setdefault("results", {})
    errors = []
    for pf in entry["platforms"]:
        if results.get(pf, {}).get("published") or results.get(pf, {}).get("post_id"):
            print(f"    {pf}: 前回すでに投稿済み。飛ばす")
            continue
        try:
            if pf == "instagram":
                r = ig_post(entry, ulist, only_container)
            elif pf == "facebook":
                if only_container:
                    print("    facebook: --only-container なので出さない")
                    continue
                r = fb_post(entry, ulist)
            else:
                raise ValueError(f"未対応の媒体: {pf}")
            results[pf] = r
            print(f"    {pf}: OK", r.get("permalink") or r.get("container_id"))
            if r.get("published") or r.get("post_id"):
                append_log({"id": entry["id"], "platform": pf, "posted_at": now_jst().isoformat(timespec="seconds"),
                            "permalink": r.get("permalink"), "post_id": r.get("post_id") or r.get("media_id"),
                            "media_ids": r.get("media_ids") or [r.get("media_id")]})
        except (GraphError, RuntimeError, ValueError) as e:
            msg = mask(str(e))
            print(f"    {pf}: 失敗 {msg}")
            errors.append(f"{pf}: {msg}")
    if only_container:
        return
    if errors:
        entry["status"] = "failed"
        entry["error"] = " / ".join(errors)[:1000]
        entry["failed_at"] = now_jst().isoformat(timespec="seconds")
    else:
        entry["status"] = "posted"
        entry.pop("error", None)
        entry["posted_at"] = now_jst().isoformat(timespec="seconds")
        entry["permalinks"] = {pf: r.get("permalink") for pf, r in results.items()}


def test_container(image: str, deployer) -> None:
    """疎通確認。試し画像でコンテナを1つ作り、status_code を読むだけ。media_publish は呼ばない。"""
    entry = {"id": "test", "type": "image", "media": [image], "caption": "テスト（公開しません）"}
    paths = prepare_media(entry)
    urls = deployer.publish_files(paths, only=True)   # 試し画像だけをサイトに置く
    u = urls[str(paths[0])]
    print("    公開URL:", u)
    ig = mc.conf()["ig_user_id"]
    c = api(f"{ig}/media", method="POST", data={"image_url": u, "caption": entry["caption"]})
    cid = c["id"]
    print("    コンテナ:", cid)
    st = wait_container(cid, 180, "IMAGE")
    print("    status_code:", st, "（公開していません。コンテナは24時間で消えます）")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--id", help="この投稿IDだけ（予定時刻は無視。draft は出さない）")
    ap.add_argument("--only-container", action="store_true", help="IG コンテナを作って status を見るだけ。公開しない")
    ap.add_argument("--test-container", metavar="IMAGE", help="試し画像でコンテナを1つ作る。公開しない")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    if a.check:
        mc.check()
        return
    deployer = _load_deploy()
    if a.test_container:
        test_container(a.test_container, deployer)
        return

    q = load_queue()
    now = now_jst()
    if a.id:
        targets = [e for e in q if e["id"] == a.id]
        if not targets:
            sys.exit(f"{a.id} が queue にありません")
        if not a.dry_run and targets[0]["status"] != "approved":
            sys.exit(f"{a.id} は {targets[0]['status']} です。approved にしてから")
    elif a.dry_run:
        # dry-run は「いまの queue 全体がどう出るか」を見るためのもの。予定時刻に関係なく未投稿を全部見せる
        targets = [e for e in q if e["status"] != "posted"]
        for e in targets:
            e["_due"] = "予定時刻を過ぎている→本番なら出す" if (e["status"] == "approved" and due(e, now)) else "まだ出さない"
    else:
        targets = [e for e in q if e["status"] == "approved" and due(e, now)]
    print(f"今 {now.isoformat(timespec='minutes')}／対象 {len(targets)}件" + ("（dry-run）" if a.dry_run else ""))
    if not targets:
        print("出すものはありません")
        return
    for e in targets:
        try:
            process(e, a.dry_run, a.only_container, deployer)
        except (FileNotFoundError, ValueError, RuntimeError) as ex:
            print("    準備で失敗:", mask(str(ex)))
            if not a.dry_run:
                e["status"] = "failed"
                e["error"] = mask(str(ex))[:1000]
        finally:
            if not a.dry_run and not a.only_container:
                save_queue(q)


if __name__ == "__main__":
    main()
