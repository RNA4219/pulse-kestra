# pulse-kestra イベント・データ schema

本書は `pulse-kestra` が各コンポーネント間で共有する最小データ契約を定義します。Phase 1 では schema を増やしすぎず、まず EventEnvelope、TaskRecord、WorkerAdapter request/response の 3 本柱を固定します。

## 1. EventEnvelope

### 1.1 役割

すべての入口イベントを共通形式へ正規化し、trigger の差異を吸収する。

### 1.2 フィールド定義

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `event_id` | string | 必須 | 入口イベント単位の識別子。webhook 再送の重複検知に使う |
| `event_type` | string | 必須 | `misskey.mention` `manual` `schedule` `heartbeat` など |
| `source` | string | 必須 | `misskey` `kestra` `manual` などの起点 |
| `timestamp` | string | 必須 | ISO8601 形式 |
| `actor` | object | 条件付き | ユーザー起点イベント時の送信者情報 |
| `payload` | object | 必須 | 元イベントの必要最小限の内容 |
| `trace_id` | string | 必須 | 構成要素を横断追跡する識別子 |
| `idempotency_key` | string | 推奨 | event 単位の二重起票防止用 |

### 1.3 例

```json
{
  "event_id": "evt_misskey_01JQ123ABC",
  "event_type": "misskey.mention",
  "source": "misskey",
  "timestamp": "2026-03-14T10:00:00Z",
  "actor": {
    "id": "9mk2abc",
    "username": "operator"
  },
  "payload": {
    "note_id": "9xyz",
    "text": "@pulse status を確認して",
    "visibility": "home"
  },
  "trace_id": "trace_01JQ999XYZ",
  "idempotency_key": "misskey:9xyz"
}
```

## 2. TaskRecord

### 2.1 役割

`agent-taskstate` へ保存される業務状態の最小表現。Kestra 実行履歴とは分離して扱う。

### 2.2 フィールド定義

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `task_id` | string | 必須 | taskstate 上の識別子 |
| `status` | string | 必須 | `queued` `running` `waiting` `needs_review` `done` `failed` `cancelled` |
| `trigger` | string | 必須 | `misskey.mention` `heartbeat` `schedule` `manual` など |
| `worker` | string | 任意 | 主たる worker 名 |
| `retry_count` | integer | 必須 | 再試行回数（初期値 0、上限 3） |
| `created_at` | string | 必須 | ISO8601 形式 |
| `updated_at` | string | 必須 | ISO8601 形式 |
| `trace_id` | string | 必須 | 対応する trace |
| `idempotency_key` | string | 必須 | 二重起票防止用（形式: `misskey:{note_id}`） |
| `kestra_execution_id` | string | 推奨 | Kestra 実行との紐付け（trigger 成功時に保存） |
| `reply_state` | string | 推奨 | 通知状態（詳細は 2.4 を参照） |
| `original_task_id` | string | 任意 | manual replay 元の task ID |
| `note_id` | string | 条件付き | Misskey mention の元 note ID |
| `reply_target` | string | 条件付き | Misskey 返信先 note ID |
| `reply_text` | string | 推奨 | 再送や replay で再利用する返信本文 |
| `roadmap_request_json` | string | 推奨 | replay 用に保持する worker 入力 JSON |
| `duplicate_suppression_count` | integer | 推奨 | note / reply / replay の重複抑止回数 |
| `last_duplicate_scope` | string | 推奨 | `note` `reply` `replay` のどれを抑止したか |
| `last_duplicate_key` | string | 推奨 | 最後に抑止した dedupe key |

### 2.3 例

```json
{
  "task_id": "tsk_01JQ321DEF",
  "status": "queued",
  "trigger": "misskey.mention",
  "worker": "memx-resolver",
  "retry_count": 0,
  "created_at": "2026-03-14T10:00:01Z",
  "updated_at": "2026-03-14T10:00:01Z",
  "trace_id": "trace_01JQ999XYZ",
  "idempotency_key": "misskey:9xyz123abc",
  "kestra_execution_id": "kestra_exec_12345",
  "reply_state": "pending",
  "note_id": "9xyz123abc",
  "reply_target": "9xyz123abc"
}
```

### 2.4 reply_state 詳細

Phase 2 で導入する Misskey 投稿状態の管理値。

| 値 | 説明 |
|---|---|
| `pending` | 初期状態。Misskey 投稿待ち |
| `sent` | Misskey 投稿成功 |
| `failed` | Misskey 投稿失敗（再送可能） |
| `skipped` | 投稿スキップ（guard 拒否など） |

詳細な状態遷移は [phase2-state-contract.md](./phase2-state-contract.md) を参照。

### 2.5 retry_count 運用

- 初期値: 0
- インクリメント条件: worker 失敗、Misskey 投稿失敗、manual replay
- 上限: 3（環境変数 `PULSE_MAX_RETRY_COUNT` で変更可）
- 上限超過時: 自動 retry 停止、status を `review` へ

## 3. WorkerAdapterRequest

### 3.1 目的

CLI、HTTP API、script など実行手段が違っても共通 contract で worker を呼び出せるようにする。

### 3.2 フィールド定義

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `task_id` | string | 必須 | 実行対象 task |
| `worker` | string | 必須 | adapter が解決する worker 名 |
| `input` | object | 必須 | worker に渡す主入力 |
| `context` | object | 任意 | resolve 結果、会話履歴、制約条件など |
| `constraints` | array | 任意 | timeout、token 制約、policy など |
| `trace_id` | string | 必須 | 実行追跡子 |

### 3.3 例

```json
{
  "task_id": "tsk_01JQ321DEF",
  "worker": "memx-resolver",
  "input": {
    "query": "status を確認して",
    "note_id": "9xyz"
  },
  "context": {
    "actor": "operator"
  },
  "constraints": [
    "timeout:30s"
  ],
  "trace_id": "trace_01JQ999XYZ"
}
```

## 4. WorkerAdapterResponse

### 4.1 フィールド定義

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `status` | string | 必須 | `success` `failed` `needs_review` |
| `summary` | string | 必須 | 人間向け要約 |
| `artifacts` | array | 任意 | ファイル、URL、ログ参照など |
| `structured_output` | object | 任意 | 後続処理用の構造化結果 |
| `confidence` | number | 任意 | 0.0 から 1.0 |
| `next_action` | string | 任意 | 次に取るべき行動 |

### 4.2 例

```json
{
  "status": "success",
  "summary": "対象タスクの現在状態を取得し、返信用サマリを生成しました。",
  "artifacts": [],
  "structured_output": {
    "reply_text": "現在の状態は running です。"
  },
  "confidence": 0.82,
  "next_action": "reply"
}
```

## 5. 状態遷移の最小ルール

| 現在状態 | 遷移先 | 条件 |
|---|---|---|
| `queued` | `running` | Kestra flow が worker 実行を開始した |
| `running` | `done` | worker 成功、通知も完了した |
| `running` | `needs_review` | guard、worker、返信内容のいずれかで人手確認が必要 |
| `running` | `failed` | retry 不可または retry 上限超過 |
| `failed` | `queued` | manual replay または retry 許可で再起票した |
| `waiting` | `queued` | 期限到来または外部入力が揃った |

## 6. 実装上の注意

- schema はまず bridge と adapter の境界でバリデーションする
- field 名は Phase 1 で固定し、Phase 2 以降の追加は後方互換を意識する
- `payload` の生データを抱え込みすぎず、必要最小限へ正規化する
- `trace_id` は request、log、taskstate、reply の全経路に必ず通す


## 7. Dedupe Key 契約

- note 起票: `misskey:{note_id}`
- reply 送信: `reply:{task_id}:{reply_target}`
- replay 実行: `replay:{original_task_id}:{replay_type}:{bucket}`

これらの key は flow、bridge、runbook で同じ名前を使う。
