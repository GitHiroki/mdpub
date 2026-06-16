---
name: mdpub-deploy
description: >
  doc配下に未コミットのMarkdownを追加・編集した状態で、mdpub（Astro Starlight）へ公開・デプロイしたいとき。
  新規/更新のサイドバーバッジ自動更新を含む。「mdpubに公開」「starlightにデプロイ」「doc配下をpush」
  などのフレーズで必ずこのskillを使うこと。Markdownをmdpubサイトへ反映したい場合は常にこのskillを使う。
---

# mdpub ドキュメント公開

doc配下のMarkdownをmdpub（Astro Starlight）に公開するワークフロー。
バッジ付け替えはスクリプトが行う。モデルはオーケストレーションに徹する。

## ワークフロー

### Step 1: バッジ更新スクリプトを実行する

```bash
python3 .claude/skills/mdpub-deploy/scripts/update_badges.py
```

スクリプトが `src/content/docs/` 配下の全Markdownを走査し、git diff結果に基づいてbadgeを付け替える。

### Step 2: スクリプトの結果を確認する

出力例:
```
=== バッジ更新結果 ===
  [新規] doc/foo/bar.md
  [更新] doc/baz/qux.md
  [スキップ(info)] doc/pinned/important.md

新規: 1 件 / 更新: 1 件 / クリア: 0 件 / info保護スキップ: 1 件
```

結果が想定通りであることを確認してユーザーに報告する。
おかしい場合（新規のはずが「更新」になっている等）はユーザーに確認を取る。

### Step 3: commit & push する

バッジ更新済みのファイルも含めて commit し、push する。

```bash
git add src/content/docs/
git commit -m "docs: <変更内容の要約>"
git push
```

コミットメッセージは変更内容を日本語で簡潔に表現する。

### Step 4: デプロイ確認

push 後、GitHub Actions が自動で Starlight をデプロイする。
push が成功したことをユーザーに伝え、デプロイが自動実行される旨を案内する。

---

## バッジ仕様（参考）

| badge値 | 意味 | 操作 |
|---------|------|------|
| `info` | 手動付与・保護対象 | スクリプトは絶対に触らない |
| `新規` | 今回追加されたファイル | git diff で A(追加) のもの |
| `更新` | 今回変更されたファイル | git diff で M(変更) のもの |
| なし | 変更なし | badge フィールドを削除 |

Starlight は frontmatter の `badge` フィールドで設定。1ページにつき1つのみ。

## 注意事項

- バッジ判定は全てスクリプト側で完結。モデルが diff を解釈して badge を書き換えてはいけない。
- `info` バッジのあるファイルを編集しても badge は `info` のまま維持される。
- スクリプトは冪等（複数回実行しても同じ結果になる）。
- ドキュメントパスは `src/content/docs/`（Starlight の autogenerate 構成）。
