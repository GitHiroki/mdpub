# ドキュメント公開の流れ

Claude に md を渡してから、サイトに公開されるまでの流れをまとめたメモ。
各手順の詳細は、表の「使うもの」に書いたスキルやファイルが原本なので、そちらを読む。

## 全体の流れ

ここでいう「手元」は Claude のセッションが動いている環境（Claude Code on the web ならクラウド上のコンテナ）を指す。

| # | 手順 | 動く場所 | 使うもの |
| --- | --- | --- | --- |
| 1 | md を渡す | 人間 → セッション | |
| 2 | 推敲する。`report-only` なら差分を見せて合意を取る | 手元 | `.claude/skills/mdpub-proofread/` |
| 3 | バッジを更新して commit、push、PR を作る | 手元 → GitHub | `.claude/skills/mdpub-deploy/`（`update_badges.py`） |
| 4 | CI が動く（チェックスクリプトとビルド） | GitHub | `.github/workflows/check.yml` |
| 5 | チェックスクリプトを手元でも実行する | 手元 | `.claude/skills/mdpub-review/scripts/check_docs.py` |
| 6 | 新しいコンテキストのサブエージェントでレビューする | 手元 | `.claude/skills/mdpub-review/` |
| 7 | レビュー結果を PR にコメントする | 手元 → GitHub | |
| 8 | 判定する。`report-only` なら報告して止め、`auto-merge` なら条件を確認してマージする | 手元 → GitHub | `.claude/skills/mdpub-review/criteria.md` |
| 9 | main へのマージをきっかけにデプロイし、Slack に通知する | GitHub | `.github/workflows/deploy.yml` |

4 と 5〜6 は並行して進む。
マージは CI が通ったことを確認してから行う。

レビューより先に PR を作るのは、レビュー結果を PR のコメントとして残すためである。

## レビューを分けている理由

推敲した Claude 自身がレビューすると、自分がなぜそう直したかを知っているため、その理由づけに納得して成果物を疑えなくなる。
そこで、レビューは書き手の思考過程を持たない新しいコンテキストのサブエージェントに任せる。
レビュアーに渡すのは元原稿、成果物、基準ファイルの場所だけで、推敲の意図や PR の説明文は渡さない。

基準（`criteria.md`）は人間が決める。
書き手が基準を書くと、書き手の解釈が基準に入り込むためである。
Claude は `criteria.md` を自分の判断で書き換えない。

経緯は `src/content/docs/fold-subagents-into-main-loop.md` の壁打ちメモにある。

## 3 つの層

| 層 | 担当 | 見るもの |
| --- | --- | --- |
| 機械チェック | `check_docs.py`、CI の `Check docs` | frontmatter、バッジの値、日本語の文中のダッシュ、崩れる太字（error）、中黒（warning）、ビルド |
| 意味のレビュー | レビュー用サブエージェント | 論旨の改変、推量の断定化、原稿にない内容の追加、意味の取り違え、公開してはいけない情報 |
| 基準 | 人間 | 何をブロッカーとするか、運用モード |

毎回同じ結果が出るべきものはスクリプトに、意味の判断はモデルに、線引きは人間に置いている。

## チェックスクリプトが 2 回動く理由

手元と CI で同じ `check_docs.py` を実行している。

- **手元**：CI の結果を待たずに、レビューの前に機械的な誤りを直せる
- **CI**：結果が GitHub に記録として残る。Claude を通さずに作られた PR（GitHub 上で直接編集したものなど）にもかかる

手元で個別に試すときは次のように実行する。

```bash
python3 .claude/skills/mdpub-review/scripts/check_docs.py            # origin/main との差分が対象
python3 .claude/skills/mdpub-review/scripts/check_docs.py path/to/a.md
```

## 運用モード

`criteria.md` の `mode` で切り替える。

- **report-only**（初期値）：レビュー結果を PR にコメントして報告するだけ。推敲の差分も毎回人間に見せて合意を取る。マージは人間が行う
- **auto-merge**：推敲の合意は待たず、レビュアーの判定に任せる。次の条件をすべて満たしたら Claude がマージする
  - 変更が `src/content/docs/` 配下だけ
  - CI が通っている
  - レビューのブロッカーが 0 件

人間の判断とレビュアーの判断が数回続けて一致したら、`auto-merge` に切り替える。
スキル、ワークフロー、設定を変える PR は、モードによらず人間がマージする。

