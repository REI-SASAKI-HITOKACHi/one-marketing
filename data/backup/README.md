# シートのバックアップ（**このフォルダにJSONを置かない**）

**2026-09-11 変更：控えのJSONは git に入れない。** 顧客の電話番号が約700件入るため、
リポジトリ（GitHub）に載せるのをやめた。置き場所は各実行環境の `~/.cache/one-hitter/backup/`。
恒久的な控えはオーナーのDriveにスプレッドシートごとコピーする（CLAUDE.md の「変更前にバックアップ」の本来の形）。

# シートのバックアップ

`~/.cache/one-hitter/backup/冬季見込み客_2026-YYYYMMDD-HHMM.json` は、`tools/build-sms-list.py` で
タブを作り直す**前**に取った、そのタブの中身そのままの控え。

作り直しは A1:Y1000 をいったん消してから書き直すので、**F列「送信済み」と
G列「返信メモ」（和真さんが手で入れたもの）は、この控えにしか残らない**。

戻したいときは、このJSONの中身をそのままタブに書けばよい。

取り方：
```
python3 tools/sheets_client.py read <シートID> '冬季見込み客_2026!A1:Z1000' \
  > ~/.cache/one-hitter/backup/"冬季見込み客_2026-$(date +%Y%m%d-%H%M).json"
```
