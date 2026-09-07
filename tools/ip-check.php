<?php
/**
 * このサーバーが「外に出ていくとき」のグローバルIPアドレスを調べる。
 *
 * 【何のため】
 *   KDDI Message Cast の申込書に、接続元のグローバルIPアドレスを書く必要がある。
 *   レンジ指定は不可で、単一のIPを申告しなければならない。
 *   ロリポップのサーバーからAPIを叩く構成にできるかどうかは、
 *   ここで出るIPが固定されているかにかかっている。
 *
 * 【使い方】
 *   1. このファイルを ip-check.php という名前で保存する
 *   2. ロリポップのファイルマネージャー（またはFTP）で、公開フォルダの直下に置く
 *   3. ブラウザで https://（ドメイン）/ip-check.php を開く
 *   4. 表示された「外向きIP」をCMOに伝える
 *   5. ★確認が終わったら必ずこのファイルを削除する（置きっぱなしにしない）
 *
 * 【判定のしかた】
 *   時間を空けて2〜3回開いて、毎回同じIPが出るかを見る。
 *   毎回違う場合、この方式は使えない（KDDIはレンジ指定を認めていないため）。
 */

header('Content-Type: text/plain; charset=UTF-8');

/** 外部サービスを叩いて、返ってきた文字列を返す。curl → file_get_contents の順に試す */
function fetch_text($url)
{
    if (function_exists('curl_init')) {
        $ch = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 10,
            CURLOPT_FOLLOWLOCATION => true,
            CURLOPT_USERAGENT      => 'one-hitter-ip-check',
        ]);
        $body = curl_exec($ch);
        $err  = curl_error($ch);
        curl_close($ch);
        if ($body !== false && $body !== '') {
            return trim($body);
        }
        if ($err !== '') {
            return 'エラー: ' . $err;
        }
    }
    if (ini_get('allow_url_fopen')) {
        $ctx  = stream_context_create(['http' => ['timeout' => 10]]);
        $body = @file_get_contents($url, false, $ctx);
        if ($body !== false && $body !== '') {
            return trim($body);
        }
    }
    return '取得できませんでした';
}

echo "==============================================\n";
echo " ワンヒッター  接続元IPアドレスの確認\n";
echo " " . date('Y-m-d H:i:s') . "\n";
echo "==============================================\n\n";

echo "■ 外向きIP（KDDIの申込書に書くのはこれ）\n";
$results = [];
foreach ([
    'https://api.ipify.org'        => 'ipify',
    'https://checkip.amazonaws.com' => 'AWS',
    'https://ifconfig.me/ip'       => 'ifconfig.me',
] as $url => $name) {
    $ip = fetch_text($url);
    $results[] = $ip;
    printf("  %-12s : %s\n", $name, $ip);
}

$valid = array_values(array_unique(array_filter($results, function ($v) {
    return filter_var($v, FILTER_VALIDATE_IP) !== false;
})));

echo "\n■ 判定\n";
if (count($valid) === 0) {
    echo "  外部への通信ができませんでした。\n";
    echo "  このサーバーからAPIを叩く構成は使えない可能性が高いです。\n";
} elseif (count($valid) === 1) {
    echo "  外向きIPは 1つ に定まりました → " . $valid[0] . "\n";
    echo "  ※ 時間を空けて2〜3回開き、毎回同じ値になるか確かめてください。\n";
} else {
    echo "  外向きIPが複数ありました → " . implode(' , ', $valid) . "\n";
    echo "  複数のIPから出ていく構成です。KDDIはレンジ指定を認めていないため、\n";
    echo "  全部を申告するか、別の方法を検討する必要があります。\n";
}

echo "\n■ 参考情報\n";
echo "  このページを見ているあなたのIP : " . ($_SERVER['REMOTE_ADDR'] ?? '不明') . "\n";
echo "  サーバー自身のIP (SERVER_ADDR) : " . ($_SERVER['SERVER_ADDR'] ?? '不明') . "\n";
echo "  ホスト名                       : " . php_uname('n') . "\n";
echo "  PHPバージョン                  : " . PHP_VERSION . "\n";
echo "  curl                           : " . (function_exists('curl_init') ? '使える' : '使えない') . "\n";
echo "  allow_url_fopen                : " . (ini_get('allow_url_fopen') ? 'オン' : 'オフ') . "\n";

echo "\n----------------------------------------------\n";
echo "確認が終わったら、このファイルは削除してください。\n";
