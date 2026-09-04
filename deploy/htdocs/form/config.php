<?php
// 予約フォームの送信先。ここだけ書き換えれば宛先を変えられます。
return [
    // 受信するアドレス
    'to'   => 'k-watanabe@one-hitter.her.jp',
    'cc'   => 'info@one-hitter.her.jp',

    // 送信元。one-hitter.her.jp 上に実在するアドレスにしてください。
    // 別ドメインのアドレスを入れると、なりすまし扱いで届かなくなります。
    'from' => 'info@one-hitter.her.jp',

    // 件名の頭に付く文字列
    'subject_prefix' => '【LP予約】',
];
