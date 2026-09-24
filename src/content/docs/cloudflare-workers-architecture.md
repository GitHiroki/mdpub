---
title: Cloudflare Workers のアーキテクチャと env の注入タイミング
description: V8 isolate による分離の仕組みと、env がいつどこから注入されるのかを、誤解が解けていく順に辿った記録。
---

## 追いかけた3つの疑問

Cloudflare Workers のアーキテクチャを読んでいて、腹落ちしなかった点が3つあった。

- **コンテナではなく isolate**：そう言われても、コンテナが無いわけがない。
- **env の反映タイミング**：他人と同居しているなら、反映のタイミングが難しくなるのではないか。
- **secret manager 経由の値**：デプロイ時に焼き込まれるのか、実行時に読まれるのかが分からない。

どれも前提が少しズレていた。
その崩れ方まで含めて記録する。

---

## Workers の実行モデル

公式ドキュメント（[How Workers works](https://developers.cloudflare.com/workers/reference/how-workers-works/)）の要点は3つある。

### Isolate

ランタイムは V8 エンジンを使い、**V8 の isolate**（軽量な実行コンテキスト、つまりサンドボックス）単位でコードを動かす。
1つのランタイムインスタンスが数百から数千の isolate を切り替えながら動かし、メモリは isolate ごとに完全に分離されている。

関数ごとに VM を立てるのではなく、既存の環境の中に isolate を作る。
VM を起動する必要がないので、VM モデルのコールドスタートがそのまま消える。
isolate 1つの起動は VM やコンテナ上の Node プロセスより約100倍速く、メモリ消費も1桁少ないとされている。

### Compute per request

`*.workers.dev` や自分のドメインへのリクエストが Cloudflare のいずれかのデータセンターに届くと、そのリクエストを引数に `fetch()` ハンドラが呼ばれ、`Response` を返して応答する。
常駐プロセスではなく、リクエスト単位で実行され、課金される。

### Distributed execution

isolate はリクエスト中は基本的に生きているが、公式の limits に達した場合やマシンのリソースが逼迫した場合、イベント解決後に選択的に evict される。
理由はマシンのリソース制約、サンドボックス破りを試みる疑わしいスクリプト、個別のリソース上限などが挙げられている。

加えて、1インスタンスがシングルスレッドのイベントループで複数リクエストを扱う。
`await` 中に別のリクエストが差し込まれる形も含まれるため、2つのリクエストが同じインスタンスに行く保証はない。

---

## 「コンテナではない」の意味

> コンテナではない？

コンテナがゼロなのではなく、顧客ごとには作られない、が正しい。

ドキュメントは「Workers は JS ランタイムの起動コストをコンテナ起動時に一度だけ払う」と書いている。
つまりマシン上にランタイムのプロセス（コンテナ）は動いていて、その中に何千人ぶんものコードが isolate として同居している。

違いは**分離をどのレイヤーでやるか**にあった。

| | 分離のレイヤー | テナントごとに必要なもの |
|---|---|---|
| コンテナ / VM | OS レベル（namespace、cgroups、ハイパーバイザ） | OS プロセスと言語ランタイムのコピー |
| V8 isolate | プロセス内部（V8 のヒープとグローバルスコープ） | ヒープとグローバルスコープのみ。ランタイム本体は共有 |

<svg viewBox="0 0 680 300" width="100%" role="img" aria-label="従来型サーバーレスと Workers の分離レイヤー比較" style="max-width:680px">
  <g fill="none" stroke="currentColor" stroke-width="1" opacity="0.5">
    <rect x="20" y="20" width="290" height="260" rx="16"/>
    <rect x="370" y="20" width="290" height="260" rx="16"/>
  </g>
  <g fill="none" stroke="currentColor" stroke-width="1.5">
    <rect x="45" y="90" width="240" height="52" rx="8"/>
    <rect x="45" y="154" width="240" height="52" rx="8"/>
    <rect x="45" y="218" width="240" height="52" rx="8"/>
    <rect x="395" y="90" width="240" height="180" rx="10"/>
  </g>
  <g fill="none" stroke="currentColor" stroke-width="1" opacity="0.8">
    <rect x="410" y="150" width="66" height="30" rx="4"/>
    <rect x="487" y="150" width="66" height="30" rx="4"/>
    <rect x="564" y="150" width="56" height="30" rx="4"/>
    <rect x="410" y="190" width="66" height="30" rx="4"/>
    <rect x="487" y="190" width="66" height="30" rx="4"/>
    <rect x="564" y="190" width="56" height="30" rx="4"/>
    <rect x="410" y="230" width="66" height="30" rx="4"/>
    <rect x="487" y="230" width="66" height="30" rx="4"/>
    <rect x="564" y="230" width="56" height="30" rx="4"/>
  </g>
  <g fill="currentColor" font-family="sans-serif" text-anchor="middle">
    <text x="165" y="50" font-size="15" font-weight="600">従来型のサーバーレス</text>
    <text x="165" y="72" font-size="12" opacity="0.75">顧客ごとにコンテナを起動</text>
    <text x="165" y="112" font-size="13">コンテナ A</text>
    <text x="165" y="131" font-size="11" opacity="0.75">言語ランタイム＋コード</text>
    <text x="165" y="176" font-size="13">コンテナ B</text>
    <text x="165" y="195" font-size="11" opacity="0.75">言語ランタイム＋コード</text>
    <text x="165" y="240" font-size="13">コンテナ C</text>
    <text x="165" y="259" font-size="11" opacity="0.75">言語ランタイム＋コード</text>
    <text x="515" y="50" font-size="15" font-weight="600">Workers</text>
    <text x="515" y="72" font-size="12" opacity="0.75">1プロセスに全員が同居</text>
    <text x="515" y="114" font-size="13">V8 ランタイム（共有）</text>
    <text x="515" y="133" font-size="11" opacity="0.75">起動コストは1回だけ</text>
    <text x="443" y="169" font-size="10">isolate</text>
    <text x="520" y="169" font-size="10">isolate</text>
    <text x="592" y="169" font-size="10">isolate</text>
    <text x="443" y="209" font-size="10">isolate</text>
    <text x="520" y="209" font-size="10">isolate</text>
    <text x="592" y="209" font-size="10">isolate</text>
    <text x="443" y="249" font-size="10">isolate</text>
    <text x="520" y="249" font-size="10">isolate</text>
    <text x="592" y="249" font-size="10">isolate</text>
  </g>
</svg>
### クラスローダとタブの比喩

1つの JVM の中に複数アプリをクラスローダで分離して載せるイメージが近い。
V8 はそれを言語仕様のレベルで厳密にやっている。

もう一つの見方は Chrome のタブである。
isolate はもともと Chrome が多数のサイトの JS を1プロセス内で安全に走らせるために作った仕組みで、Cloudflare はそれを「複数サイト」から「複数テナント」に読み替えて使っている。

### 代償

- **分離が薄い**：OS カーネルではなく V8 の言語境界で守っているので、Spectre のようなサイドチャネルが直撃する。
- **任意のバイナリが動かない**：動かせるのは V8 が実行できるもの（JS と WASM）だけで、フルの POSIX プロセスではない。
- **寿命の保証がない**：evict されうるので、グローバルスコープに状態を持てない。

「プロセス丸ごとを1人1つ借りる」から「ランタイムの中の1区画を借りる」への移行だと考えると、起動が速いことと使えるものが制限されることが一本の因果でつながる。

---

## env が渡されるタイミング

> env の読み込みは V8 ランタイムが起動する時だと思うけど、他の人も同居してるなら反映タイミング難しくならない？

env は V8 ランタイム起動時には読まれない。
`fetch(request, env, ctx)` の第2引数として、呼び出しのたびに渡される。

Node の `process.env` のようなプロセスグローバルではないので、「ランタイム起動時に環境変数を読み込む」というレイヤー自体が存在しない。
Node や Next.js の癖で `process.env.MY_SECRET` を書くと、Workers では実行時に undefined になる（`nodejs_compat` 有効時を除く）。

したがって同居の心配は消える。
isolate はメモリが完全に分離されていて、しかも isolate は Worker のバージョンごとに作られる。
env は同居プロセスの共有環境ではなく、**自分の isolate に手渡される引数オブジェクト**だった。

### バインディング変更時の isolate 再利用

コードを変えずバインディングだけを変更してデプロイした場合、Cloudflare は既に動いている isolate を再利用することがある。
コードを無駄に再ロードせずに環境変数やバインディングを変えられる、という最適化である。
トラフィックが来続けている isolate は、長時間 hot のまま生き残る可能性がある。

つまり落とし穴はプラットフォーム側ではなく、自分のコード側にある。

```ts
// NG: 遅延初期化でも、キャッシュした瞬間に古い値が焼き付く
let client;
export default {
  fetch(req, env) {
    client ??= new Client(env.API_KEY); // isolate が hot な間ずっと古いキー
    // ...
  }
};
```

シークレットをローテーションしたのに、グローバルにキャッシュしたクライアントが古い値を握り続ける、というのが具体的な事故の形になる。
リクエストごとに `env` から組み立て直すのが安全側の選択になる。

---

## env の設定は3層ある

設定画面から入れるだけなのか、`.env` は使えるのか、という点も違った。
3層あり、それぞれ注入のタイミングが異なる。

### vars（機密でないもの）

`wrangler.jsonc` や `wrangler.toml` の `vars` に書く。
デプロイ時にバージョンへ焼き込まれ、リクエスト時の `env` にはもう値として入っている。

> ダッシュボードで環境変数を変更しても、次に deploy した時に Wrangler が上書きする。
> 止めたい場合は `keep_vars = true` を設定ファイルに追加する。

### secrets（Worker 単位で暗号化）

`wrangler secret put` かダッシュボードで設定する。
`wrangler secret put` は**新しいバージョンを作って即座にデプロイする**ので、gradual deployments を使っているなら `wrangler versions secret put` を使う。

`.env` は使える。
ただし原則としてローカル開発用であり、ローカル用のシークレットは Wrangler 設定ファイルと同じディレクトリの `.dev.vars` か `.env` に置く。
両方を置くのは避けたい。
`.dev.vars` がある場合、`.env` の値はローカル開発時の env オブジェクトに含まれないからである。

デプロイ時にも使う道がある。

```bash
# コードとシークレットを1操作で流す（JSON または .env 形式）
npx wrangler deploy --secrets-file .env.production
npx wrangler versions upload --secrets-file secrets.json
```

ファイルに含まれないシークレットは前バージョンのものが保持されるので、CI/CD 向きである。

さらに `secrets` 設定プロパティで必要なシークレット名を宣言しておくと、deploy 時に全部設定済みかを検証し、足りなければ名前を列挙してエラーで落ちる。

```jsonc
{
  "secrets": {
    "required": ["API_KEY", "DB_PASSWORD"]
  }
}
```

### Secrets Store（アカウント単位）

3つめの疑問、secret manager を使ったときの注入タイミングの答えがここにある。

`secrets_store_secrets` でバインドする。
バインディングは env 上に置かれるが、**値を取り出すには非同期呼び出しが必要**になる。

```ts
const key = await env.API_KEY.get();
```

注入はデプロイ時ではなくリクエスト処理中に起きる。
実行時に読まれるので、バインドされた Worker は再デプロイなしで現在の値を見る。
ローテーションが即座に伝播する代わりに、毎回 `await` が必要になる。

### 3層の注入タイミング

| | 注入 | 更新の反映 |
|---|---|---|
| vars / secrets | デプロイ時にバージョンへ焼き込み | 新バージョンのデプロイ |
| Secrets Store | リクエスト中に `.get()` | 再デプロイ不要 |

---

## トップレベルスコープの env と、状態の置き場所

最後にもう1つ罠がある。
`cloudflare:workers` から `env` を import すれば、トップレベルスコープでも環境変数やシークレットにアクセスできる。

```ts
import { env } from "cloudflare:workers";
```

ただしリクエストコンテキスト外での I/O は許されないため、KV への呼び出しなど一部のメソッドは動かない。
Secrets Store の `.get()` もこの I/O にあたるので、トップレベルで先読みしてキャッシュすることはそもそもできない。
仮にリクエスト内でグローバル変数にキャッシュすれば、hot な isolate が古い値を握り続けて Secrets Store を使う意味が消える。

3つの疑問すべてが、同じ結論に着地した。

> 状態は関数の引数か env バインディング経由で渡し、モジュールレベルの変数には置かない。

isolate の寿命が保証されないことも、バインディング変更時に isolate が再利用されることも、Secrets Store が実行時読み取りであることも、この一行に収束する。
グローバルに mutable な状態を持たないことが、Workers では推奨ではなくアーキテクチャ上の要請になっている。

---

## 参考

- [How Workers works — Cloudflare Docs](https://developers.cloudflare.com/workers/reference/how-workers-works/)
- [Bindings (env) — Cloudflare Docs](https://developers.cloudflare.com/workers/runtime-apis/bindings/)
- [Environment variables — Cloudflare Docs](https://developers.cloudflare.com/workers/configuration/environment-variables/)
- [Secrets — Cloudflare Docs](https://developers.cloudflare.com/workers/configuration/secrets/)
- [Secrets Store integration with Workers — Cloudflare Docs](https://developers.cloudflare.com/secrets-store/integrations/workers/)
- [Workers Best Practices — Cloudflare Docs](https://developers.cloudflare.com/workers/best-practices/workers-best-practices/)
