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
  python3 tools/drive_client.py mkdir <フォルダ名> [親フォルダId]
  python3 tools/drive_client.py upload <ローカルパス> [親フォルダId] [Drive上の名前]

※ mkdir は使える（フォルダは容量を消費しないため）。
※ upload は My Drive に対しては使えない。
  サービスアカウントには保存容量が割り当てられておらず、
  「Service Accounts do not have storage quota」で失敗する。
  共有ドライブ（Google Workspace）があればそこには置ける。
  そうでない場合、ファイルの受け渡しはオーナーのアカウント経由で行うこと。
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

    elif op == "mkdir":
        op_mkdir(sys.argv[2:])

    elif op == "upload":
        op_upload(sys.argv[2:])

    else:
        raise SystemExit(__doc__)




def op_upload(argv):
    """upload <ローカルパス> [親フォルダId] [Drive上の名前]

    サービスアカウントの権限でアップロードする。
    親フォルダを指定する場合、そのフォルダがサービスアカウント
    （鍵の client_email）に「編集者」で共有されている必要がある。
    """
    import mimetypes
    import uuid

    path = pathlib.Path(argv[0])
    if not path.exists():
        sys.exit(f"ファイルがありません: {path}")
    parent = argv[1] if len(argv) > 1 else None
    name = argv[2] if len(argv) > 2 else path.name

    meta = {"name": name}
    if parent:
        meta["parents"] = [parent]
    ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"

    boundary = "----onehitter" + uuid.uuid4().hex
    body = b""
    body += f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
    body += json.dumps(meta, ensure_ascii=False).encode() + b"\r\n"
    body += f"--{boundary}\r\nContent-Type: {ctype}\r\n\r\n".encode()
    body += path.read_bytes() + b"\r\n"
    body += f"--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true",
        data=body, method="POST",
        headers={
            "Authorization": f"Bearer {_token()}",
            "Content-Type": f"multipart/related; boundary={boundary}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            res = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        sys.exit(f"Drive API {e.code}: {e.read().decode(errors='replace')[:500]}")
    print("アップロード:", res.get("name"), res.get("id"))
    print("URL: https://drive.google.com/file/d/%s/view" % res.get("id"))


def op_mkdir(argv):
    """mkdir <フォルダ名> [親フォルダId]"""
    meta = {"name": argv[0], "mimeType": "application/vnd.google-apps.folder"}
    if len(argv) > 1:
        meta["parents"] = [argv[1]]
    req = urllib.request.Request(
        "https://www.googleapis.com/drive/v3/files?supportsAllDrives=true",
        data=json.dumps(meta, ensure_ascii=False).encode(), method="POST",
        headers={"Authorization": f"Bearer {_token()}",
                 "Content-Type": "application/json; charset=UTF-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            res = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        sys.exit(f"Drive API {e.code}: {e.read().decode(errors='replace')[:500]}")
    print("フォルダ作成:", res.get("name"), res.get("id"))


if __name__ == "__main__":
    main()
