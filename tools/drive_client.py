#!/usr/bin/env python3
"""
Google Drive への読み書きクライアント（サービスアカウント認証）

sheets_client.py と同じ鍵・同じ署名方式を使う。認証情報は環境変数
GOOGLE_SHEETS_SA_KEY から読む。このファイルにも、リポジトリのどこにも、鍵を書かないこと。

施工写真は iPhone の HEIC で入ってくる。Drive MCP 経由では HEIC を読めないので、
ここでダウンロードして JPEG に変換してから扱う。

使い方:
  python3 tools/drive_client.py list <folderId>
  python3 tools/drive_client.py get  <fileId> <保存先パス>
  python3 tools/drive_client.py sync <folderId> <保存先ディレクトリ>   # 未取得のものだけ落とす
"""
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sheets_client import access_token, load_credentials  # 認証は共通

API = "https://www.googleapis.com/drive/v3"
SCOPE = "https://www.googleapis.com/auth/drive"


def _token():
    return access_token(load_credentials(), scope=SCOPE)


def _get(url, token, binary=False):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Drive API {e.code}: {e.read().decode('utf-8', 'replace')[:400]}")
    return raw if binary else json.loads(raw.decode("utf-8"))


def list_folder(folder_id, token=None):
    """フォルダ直下のファイルを全ページぶん返す。"""
    token = token or _token()
    out, page = [], None
    while True:
        q = {
            "q": f"'{folder_id}' in parents and trashed = false",
            "fields": "nextPageToken,files(id,name,mimeType,size,createdTime,imageMediaMetadata)",
            "pageSize": "1000",
        }
        if page:
            q["pageToken"] = page
        res = _get(f"{API}/files?{urllib.parse.urlencode(q)}", token)
        out.extend(res.get("files", []))
        page = res.get("nextPageToken")
        if not page:
            return out


def download(file_id, dest, token=None):
    token = token or _token()
    raw = _get(f"{API}/files/{file_id}?alt=media", token, binary=True)
    pathlib.Path(dest).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(dest).write_bytes(raw)
    return len(raw)


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    op = sys.argv[1]
    token = _token()

    if op == "list":
        files = list_folder(sys.argv[2], token)
        print(json.dumps(files, ensure_ascii=False, indent=1))
        print(f"# {len(files)} 件", file=sys.stderr)

    elif op == "get":
        n = download(sys.argv[2], sys.argv[3], token)
        print(f"{sys.argv[3]}  {n // 1024}KB")

    elif op == "sync":
        folder, out = sys.argv[2], pathlib.Path(sys.argv[3])
        out.mkdir(parents=True, exist_ok=True)
        files = list_folder(folder, token)
        got = skipped = 0
        for f in files:
            dest = out / f["name"]
            if dest.exists() and dest.stat().st_size == int(f.get("size", 0)):
                skipped += 1
                continue
            download(f["id"], dest, token)
            got += 1
        print(f"取得 {got} 件 / 既取得 {skipped} 件 / 合計 {len(files)} 件")

    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
