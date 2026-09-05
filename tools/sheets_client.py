#!/usr/bin/env python3
"""
Google Sheets への読み書きクライアント（サービスアカウント認証）

認証情報は環境変数 GOOGLE_SHEETS_SA_KEY から読む。
値は サービスアカウントのJSONキーそのもの、または それをbase64エンコードした文字列。
このファイルにも、リポジトリのどこにも、鍵を書かないこと。

使い方:
  python3 tools/sheets_client.py whoami
  python3 tools/sheets_client.py tabs <spreadsheetId>
  python3 tools/sheets_client.py read <spreadsheetId> "'1月_売上/顧客'!A1:T20"
  python3 tools/sheets_client.py write <spreadsheetId> "'Sheet1'!A1" values.json
  python3 tools/sheets_client.py addtab <spreadsheetId> "タブ名"
"""

import base64
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://sheets.googleapis.com/v4/spreadsheets"
SCOPE = "https://www.googleapis.com/auth/spreadsheets"
ENV_KEY = "GOOGLE_SHEETS_SA_KEY"


def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def load_credentials() -> dict:
    raw = os.environ.get(ENV_KEY)
    if not raw:
        sys.exit(
            f"環境変数 {ENV_KEY} が設定されていません。\n"
            "docs/sheets-api-setup.md の手順で、サービスアカウントの鍵を環境変数に登録してください。"
        )
    raw = raw.strip()
    if not raw.startswith("{"):
        try:
            raw = base64.b64decode(raw).decode()
        except Exception:
            sys.exit(f"{ENV_KEY} をJSONとしてもbase64としても読めませんでした。")
    try:
        info = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.exit(f"{ENV_KEY} のJSONが壊れています: {e}")
    for field in ("client_email", "private_key", "token_uri"):
        if field not in info:
            sys.exit(f"{ENV_KEY} に {field} がありません。サービスアカウントの鍵か確認してください。")
    return info


def _sign_rs256(message: bytes, private_key_pem: str) -> bytes:
    """openssl で RS256 署名する。秘密鍵は 0600 の一時ファイルに置き、直後に消す。"""
    fd, path = tempfile.mkstemp(prefix="sa-", suffix=".pem")
    try:
        os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(fd, "w") as f:
            f.write(private_key_pem)
        proc = subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", path],
            input=message, capture_output=True,
        )
        if proc.returncode != 0:
            sys.exit("秘密鍵での署名に失敗しました: " + proc.stderr.decode("utf-8", "replace")[:400])
        return proc.stdout
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def access_token(info: dict, scope: str = SCOPE) -> str:
    """スコープ既定は Sheets。Drive を触るときは drive_client.py から別スコープを渡す。"""
    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    claims = {
        "iss": info["client_email"],
        "scope": scope,
        "aud": info.get("token_uri", TOKEN_URL),
        "iat": now,
        "exp": now + 3600,
    }
    signing_input = (
        _b64u(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + _b64u(json.dumps(claims, separators=(",", ":")).encode())
    ).encode()

    signature = _sign_rs256(signing_input, info["private_key"])
    assertion = signing_input.decode() + "." + _b64u(signature)

    body = urllib.parse.urlencode(
        {"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion}
    ).encode()
    req = urllib.request.Request(
        info.get("token_uri", TOKEN_URL),
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["access_token"]


def call(token: str, path: str, method: str = "GET", payload=None, query=None):
    url = f"{API}{path}"
    if query:
        url += "?" + urllib.parse.urlencode(query)
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        sys.exit(f"Sheets API {e.code}: {detail[:1200]}")


# ------------------------------ 操作 ------------------------------

def op_whoami(_argv):
    info = load_credentials()
    token = access_token(info)
    print("サービスアカウント:", info["client_email"])
    print("アクセストークン取得:", "成功" if token else "失敗")
    print("\nこのアドレスに対象スプレッドシートを「編集者」で共有してください。")


def op_tabs(argv):
    token = access_token(load_credentials())
    meta = call(token, f"/{argv[0]}", query={"fields": "properties.title,sheets.properties"})
    print("スプレッドシート:", meta["properties"]["title"])
    for s in meta.get("sheets", []):
        p = s["properties"]
        g = p.get("gridProperties", {})
        print(f'  [{p["sheetId"]:>10}] {p["title"]}  ({g.get("rowCount")}行 x {g.get("columnCount")}列)')


def op_read(argv):
    token = access_token(load_credentials())
    res = call(token, f"/{argv[0]}/values/{urllib.parse.quote(argv[1], safe='')}",
               query={"valueRenderOption": "UNFORMATTED_VALUE",
                      "dateTimeRenderOption": "FORMATTED_STRING"})
    print(json.dumps(res.get("values", []), ensure_ascii=False, indent=1))


def op_write(argv):
    """write <id> <range> <values.json>  — values.json は二次元配列"""
    token = access_token(load_credentials())
    with open(argv[2], encoding="utf-8") as f:
        values = json.load(f)
    res = call(token, f"/{argv[0]}/values/{urllib.parse.quote(argv[1], safe='')}",
               method="PUT", payload={"values": values},
               query={"valueInputOption": "USER_ENTERED"})
    print("更新:", res.get("updatedRange"), res.get("updatedCells"), "セル")


def op_addtab(argv):
    token = access_token(load_credentials())
    res = call(token, f"/{argv[0]}:batchUpdate", method="POST",
               payload={"requests": [{"addSheet": {"properties": {"title": argv[1]}}}]})
    p = res["replies"][0]["addSheet"]["properties"]
    print("作成:", p["title"], "sheetId=", p["sheetId"])


def op_batch(argv):
    """batch <id> <requests.json> — Sheets API の batchUpdate をそのまま送る"""
    token = access_token(load_credentials())
    with open(argv[1], encoding="utf-8") as f:
        requests = json.load(f)
    res = call(token, f"/{argv[0]}:batchUpdate", method="POST", payload={"requests": requests})
    print("適用:", len(res.get("replies", [])), "件")


OPS = {"whoami": op_whoami, "tabs": op_tabs, "read": op_read,
       "write": op_write, "addtab": op_addtab, "batch": op_batch}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in OPS:
        print(__doc__)
        sys.exit(1)
    OPS[sys.argv[1]](sys.argv[2:])
