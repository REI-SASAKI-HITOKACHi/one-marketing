# このディレクトリの置き場所について

このシステムは **ヒトカチ株式会社（保険代理店業務）** のものだが、暫定的に
ワンヒッター株式会社のマーケティング用リポジトリ `one-marketing` に置いてある。

理由: 専用リポジトリを作ろうとしたが、このセッションの GitHub App に
リポジトリ作成権限がなく `403 Resource not accessible by integration` で弾かれたため。

## 専用リポジトリへ移す手順

このディレクトリは自己完結しているので、そのままコピーすれば動く。

```bash
# 1. GitHub で hitokachi-forms リポジトリを作る（Private 推奨）

# 2. 中身を移す
git clone https://github.com/REI-SASAKI-HITOKACHi/hitokachi-forms.git
cp -r one-marketing/hitokachi-forms/. hitokachi-forms/
cd hitokachi-forms
git add -A
git commit -m "適合性確認シート・意向把握シートの自動生成システム"
git push -u origin main

# 3. one-marketing 側から削除する
cd ../one-marketing
git rm -r hitokachi-forms
git commit -m "帳票自動作成システムを専用リポジトリへ移設"
git push
```

履歴ごと移したい場合は `git subtree split -P hitokachi-forms -b forms-only` で
このディレクトリだけのブランチを切り出せる。
