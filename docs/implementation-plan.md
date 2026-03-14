# pulse-kestra 実装準備計画

本書は Phase 1 に着手する前提で、最初に決めるべきこと、作る順番、初期レイアウト、検証観点をまとめた実装準備ドキュメントです。

## 1. 実装準備のゴール

- 要件を bridge、flow、adapter、notifier の責務へ落とし込む
- repo の最小レイアウトを決める
- 外部依存と secrets を洗い出す
- Phase 1 完了条件までの着手順を固定する

## 2. Phase 1 の実装対象

### 2.1 必須

- Misskey webhook 受信 endpoint
- secret 検証
- EventEnvelope 生成
- `agent-taskstate` task/run 起票
- Kestra mention flow 起動
- 1 worker adapter の実行
- Misskey 返信
- `trace_id` ログ出力

### 2.2 後回しにするもの

- PostgreSQL 永続化の最適化
- output guard
- 複数 worker chaining
- plugin 化
- 高度な検索強化

## 3. 初期ディレクトリ案

実装開始時は次の構成を推奨する。

```text
pulse-kestra/
  README.md
  docs/
  bridge/
    cmd/server/
    internal/http/
    internal/misskey/
    internal/guard/
    internal/events/
    internal/taskstate/
    internal/kestra/
    internal/reply/
  kestra/
    flows/
  adapters/
    memx-resolver/
  scripts/
  fixtures/
```

### 3.1 役割

- `bridge/`: HTTP 受信と外部 I/F の吸収
- `kestra/flows/`: mention、heartbeat、manual replay などの flow 定義
- `adapters/`: worker ごとの実行差異を吸収
- `scripts/`: ローカル検証と開発補助
- `fixtures/`: webhook payload と adapter response のサンプル

## 4. 外部依存の整理

### 4.1 接続先

- Misskey webhook / API
- Kestra webhook trigger
- `agent-taskstate`
- 初期採用 worker 1 件

### 4.2 環境変数候補

| 名前 | 用途 |
|---|---|
| `MISSKEY_WEBHOOK_SECRET` | webhook 検証 |
| `MISSKEY_API_BASE_URL` | Misskey API 接続先 |
| `MISSKEY_API_TOKEN` | Misskey 投稿 |
| `KESTRA_BASE_URL` | Kestra 接続先 |
| `KESTRA_WEBHOOK_KEY` | Kestra trigger 認証 |
| `TASKSTATE_BASE_URL` | `agent-taskstate` 接続先 |
| `TASKSTATE_TOKEN` | taskstate 認証 |
| `DEFAULT_WORKER` | 初期 worker 名 |
| `LOG_LEVEL` | ログ詳細度 |

## 5. 実装順序

### Step 1: schema と fixture を先に固定する

- `EventEnvelope`
- `TaskRecord`
- Worker request/response
- Misskey mention payload fixture

### Step 2: bridge の入口を作る

- webhook endpoint
- secret 検証
- event 判定
- 早期 return

### Step 3: taskstate 起票と Kestra 起動をつなぐ

- 起票 client
- `trace_id` 付与
- Kestra webhook trigger client

### Step 4: worker adapter を 1 本接続する

- request mapping
- 実行
- response 正規化

### Step 5: reply notifier を作る

- 固定文返信
- worker 結果返信
- 失敗時ログ

### Step 6: heartbeat の最小版を追加する

- due / retry / stuck / 未通知探索
- 重処理は別 task 化

## 6. テスト準備

### 6.1 最初に用意するテスト

- secret 検証 unit test
- EventEnvelope 正規化 unit test
- taskstate 起票 client の contract test
- worker adapter の response 正規化 test
- mention から reply までの最小 integration test

### 6.2 fixture

- mention webhook 正常 payload
- mention webhook 異常 payload
- guard reject payload
- worker success response
- worker failed response
- Misskey reply success / failure response

## 7. 運用準備チェック

- secret をコードへ埋め込まない
- webhook 再送時の idempotency を考慮する
- Kestra 実行 ID と task ID の紐付けを保存する
- 投稿失敗時に未通知状態を残す
- timeout と retry 上限を明示する
- ログに `trace_id` を必ず出す

## 8. Phase 1 完了の確認方法

1. ローカルまたは検証環境で Misskey mention payload を送る
2. bridge が secret を通し、EventEnvelope を生成する
3. taskstate に `queued` task が作られる
4. Kestra mention flow が起動する
5. adapter が worker を実行する
6. taskstate が `done` か `needs_review` に更新される
7. Misskey へ返信が返る
8. ログ上で同一 `trace_id` を end-to-end に追える

## 9. 未確定事項

実装着手前に次を確認すると手戻りが減る。

- bridge 実装言語と runtime
- `agent-taskstate` 連携方式
- 初期 worker にどれを選ぶか
- Misskey 側 webhook secret/header の具体仕様
- Kestra 側の trigger 認証方式

この 5 点が固まれば、Phase 1 の実装へすぐ入れる状態です。
