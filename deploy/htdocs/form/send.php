<?php
/**
 * LP予約フォームの受け口。
 *
 * POSTを受け取り、内容をメールで送るだけの処理です。
 * 個人情報をサーバー上のファイルに残さないよう、ログは書きません。
 */
declare(strict_types=1);

mb_internal_encoding('UTF-8');
mb_language('uni');

$config = require __DIR__ . '/config.php';

/** 戻り先のLPを、送信元ページから決める（外部URLへは飛ばさない） */
function lp_path(string $raw): string
{
    return $raw === 'mizumawari' ? '/mizumawari/' : '/aircon/';
}

/** ヘッダーに入れる値から改行を落とす（ヘッダーインジェクション対策） */
function header_safe(string $value): string
{
    return trim(str_replace(["\r", "\n", "\0"], '', $value));
}

/** 本文用。1行入力なので改行と制御文字を落とし、長さを切る */
function body_safe(string $value, int $limit = 200): string
{
    $value = preg_replace('/[\x00-\x1F\x7F]/u', ' ', $value) ?? '';
    return mb_substr(trim($value), 0, $limit);
}

function bail(string $lp, string $reason): void
{
    http_response_code(400);
    $back = htmlspecialchars($lp, ENT_QUOTES, 'UTF-8');
    $msg  = htmlspecialchars($reason, ENT_QUOTES, 'UTF-8');
    echo <<<HTML
<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>送信できませんでした｜ONE HITTER</title>
<style>
body{margin:0;background:#FAF7F2;color:#14323D;font-family:"Hiragino Sans","Yu Gothic UI",system-ui,sans-serif;line-height:1.9;}
.w{max-width:560px;margin:0 auto;padding:56px 22px;}
h1{font-size:22px;line-height:1.5;margin:0 0 14px;}
p{margin:0 0 14px;font-size:15px;}
a.btn{display:inline-block;margin-top:10px;background:#C4461D;color:#fff;text-decoration:none;
 font-weight:700;padding:15px 26px;border-radius:9999px;}
a.tel{color:#0A5C6E;font-weight:700;}
.sub{font-size:13px;color:#566B73;}
</style></head><body><div class="w">
<h1>送信できませんでした</h1>
<p>{$msg}</p>
<p class="sub">お急ぎの場合は、お電話でも承っています。<br>
<a class="tel" href="tel:08080438259">080-8043-8259</a>（受付：渡辺／8:00–20:00）</p>
<a class="btn" href="{$back}#form">入力画面に戻る</a>
</div></body></html>
HTML;
    exit;
}

$lp = lp_path((string)($_POST['lp'] ?? ''));

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    header('Location: ' . $lp, true, 303);
    exit;
}

// 自動投稿よけ。人間には見えない欄に何か入っていたら黙って終わる。
//
// 「表示から数秒以内の送信を弾く」判定も入れていたが、外した。
// 誤って弾いたときお客様には送信できたように見えるので、問い合わせが
// 黙って消える。迷惑投稿を少し減らすより、そちらの害のほうが大きい。
if (($_POST['x_field'] ?? '') !== '') {
    header('Location: ' . $lp . 'thanks.html', true, 303);
    exit;
}

$name = body_safe((string)($_POST['name'] ?? ''), 60);
$tel  = body_safe((string)($_POST['tel']  ?? ''), 30);
$zip  = body_safe((string)($_POST['zip']  ?? ''), 12);
$menu = body_safe((string)($_POST['menu'] ?? ''), 200);
$when = body_safe((string)($_POST['when'] ?? ''), 120);

if ($name === '' || $tel === '' || $zip === '') {
    bail($lp, 'お名前・お電話番号・郵便番号は、いずれも入力が必要です。');
}
if (!preg_match('/\A[0-9０-９\-ー－\s()]{9,20}\z/u', $tel)) {
    bail($lp, 'お電話番号の形式をご確認ください。数字とハイフンでご入力ください。');
}
if (!preg_match('/\A[0-9０-９]{3}[\-ー－]?[0-9０-９]{4}\z/u', $zip)) {
    bail($lp, '郵便番号の形式をご確認ください。例：134-0081');
}

$lpLabel = $lp === '/mizumawari/' ? '水まわりセット' : 'エアコン';
$sentAt  = (new DateTimeImmutable('now', new DateTimeZone('Asia/Tokyo')))->format('Y-m-d H:i');
$whenShown = $when !== '' ? $when : '（未入力）';

$body = <<<TXT
LPから予約のお申し込みがありました。

── お客様のご入力 ──────────
お名前　　　： {$name}
お電話番号　： {$tel}
郵便番号　　： {$zip}
ご希望の内容： {$menu}
ご希望の時期： {$whenShown}

── 受付情報 ────────────
流入元LP　　： {$lpLabel}（{$lp}）
受付日時　　： {$sentAt}

このメールはLPの予約フォームから自動送信されています。
TXT;

$from = header_safe($config['from']);
$to   = header_safe($config['to']);
$cc   = header_safe($config['cc']);

$headers = [
    'From: ' . mb_encode_mimeheader('ONE HITTER 予約フォーム') . ' <' . $from . '>',
    'Reply-To: ' . $from,
    'Content-Type: text/plain; charset=UTF-8',
    'X-Mailer: PHP/' . PHP_VERSION,
];
if ($cc !== '') {
    $headers[] = 'Cc: ' . $cc;
}

$subject = $config['subject_prefix'] . $lpLabel . '／' . header_safe($name) . ' 様';

$ok = mb_send_mail($to, $subject, $body, implode("\r\n", $headers), '-f' . $from);

if (!$ok) {
    bail($lp, 'システム側の不具合で送信できませんでした。お手数ですが、お電話でご連絡ください。');
}

header('Location: ' . $lp . 'thanks.html', true, 303);
exit;
