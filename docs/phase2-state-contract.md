# Phase 2 状態契約

本書は Phase 2 で導入する heartbeat、retry、manual replay に必要な状態項目と更新契約を定義する。Phase 1 の基本スキーマを拡張し、運用回復導線を支える。

## 1. reply_state 詳細定義

### 1.1 可能値

| 値 | 説明 | 遷移元 |
|---|---|---|
| `pending` | 初期状態。Misskey 投稿待ち | task 作成時 |
| `sent` | Misskey 投稿成功 | `pending` |
| `failed` | Misskey 投稿失敗 | `pending` |
| `skipped` | 投稿をスキップ（guard 拒否など） | `pending` |

### 1.2 状態遷移

```text
pending ──[投稿成功]──> sent
   │
   ├──[投稿失敗]──> failed ──[再送成功]──> sent
   │                    │
   │                    └──[再送失敗]──> failed (retry_count++)
   │
   └──[スキップ判定]──> skipped
```

### 1.3 更新タイミング

| タイミング | 更新者 | 更新値 |
|---|---|---|
| task 作成直後 | bridge | `pending` |
| post-reply 成功 | Kestra flow | `sent` |
| post-reply 失敗 | Kestra flow | `failed` |
| guard 拒否 | bridge | `skipped` |
| notifier 再送成功 | notifier replay flow | `sent` |
| notifier 再送失敗 | notifier replay flow | `failed` |

## 2. retry_count 更新契約

### 2.1 初期値

新規 task 作成時は `retry_count = 0`。

### 2.2 更新条件

| 条件 | 更新 | 上限 |
|---|---|---|
| worker 実行失敗（retry 可） | インクリメント | 3 回 |
| Misskey 投稿失敗 | インクリメント | 3 回 |
| manual replay 実行 | インクリメント | なし（運用者判断） |

### 2.3 リセット条件

- なし（累積カウントとして保持）

### 2.4 上限超過時の動作

```
retry_count >= MAX_RETRY_COUNT (3)
    ↓
自動 retry を停止
    ↓
status = review または failed
```

## 3. kestra_execution_id 保存契約

### 3.1 保存タイミング

Kestra flow trigger 成功直後に bridge が taskstate へ保存する。

### 3.2 保存場所

- `agent-taskstate` の task レコードに `kestra_execution_id` フィールドとして保存
- または context bundle に `kestra_execution` として保存

### 3.3 用途

- flow 実行状態の照会
- manual trigger との紐付け
- 障害調査時のログ突き合わせ

### 3.4 更新ルール

| 状況 | 更新 |
|---|---|
| 初回 Kestra trigger 成功 | 新規保存 |
| retry による再 trigger | 新しい execution_id で更新 |
| manual replay | 新しい execution_id で更新 |

## 4. stuck 判定基準

### 4.1 定義

task が一定時間以上進捗なしで滞留している状態。

### 4.2 判定条件

| 条件 | 閾値 | 対象 status |
|---|---|---|
| `in_progress` 継続 | 15 分超過 | `in_progress` |
| `pending` reply 未送信 | 10 分超過 | status に関わらず `reply_state=pending` |

### 4.3 判定実施者

- heartbeat flow（定期的に巡回）

### 4.4 判定後の動作

```text
stuck 検出
    ↓
heartbeat が判定
    ↓
├── kestra_execution_id あり
│       └── Kestra 実行状態を確認
│               ├── 実行中 → 待機継続
│               ├── 終了（成功） → reply_state 確認、再送へ
│               └── 終了（失敗） → retry 判定へ
│
└── kestra_execution_id なし
        └── status = review または failed
```

## 5. manual replay 引継ぎ項目

### 5.1 必須引継ぎ

manual replay 実行時に元 task から引き継ぐ項目：

| 項目 | 用途 |
|---|---|
| `trace_id` | 追跡の一貫性 |
| `idempotency_key` | 二重起票防止 |
| `note_id` | Misskey 返信先特定 |
| `reply_target` | Misskey 返信先 note ID |
| `roadmap_request` | worker 入力の再利用 |
| `original_task_id` | 元 task への参照 |

### 5.2 初期化項目

replay で新規に初期化する項目：

| 項目 | 初期値 |
|---|---|
| `task_id` | 新規発行 |
| `status` | `ready` |
| `retry_count` | 元 task から引き継ぎ + 1 |
| `reply_state` | `pending` |
| `kestra_execution_id` | 新規発行 |
| `created_at` | 現在時刻 |
| `updated_at` | 現在時刻 |

### 5.3 引き継がない項目

| 項目 | 理由 |
|---|---|
| `run_id` | 新規 run として開始 |
| `kestra_execution_id` | 新規実行として開始 |

## 6. 状態更新の整合性保証

### 6.1 更新順序

1. Kestra flow 内で taskstate を更新
2. 失敗時は flow エラーハンドラで status を review へ
3. bridge は初期起票後、状態変更は Kestra flow に委譲

### 6.2 競合回避

- `agent-taskstate` の optimistic lock 機能を使用
- 更新失敗時は再取得後に再試行

### 6.3 トランザクション境界

- task status 更新と run status 更新は別トランザクション
- 順序: run status → task status

## 7. 設定可能パラメータ

| パラメータ | デフォルト値 | 環境変数 |
|---|---|---|
| `MAX_RETRY_COUNT` | 3 | `PULSE_MAX_RETRY_COUNT` |
| `STUCK_IN_PROGRESS_MINUTES` | 15 | `PULSE_STUCK_IN_PROGRESS_MINUTES` |
| `STUCK_PENDING_REPLY_MINUTES` | 10 | `PULSE_STUCK_PENDING_REPLY_MINUTES` |
| `HEARTBEAT_INTERVAL_MINUTES` | 5 | `PULSE_HEARTBEAT_INTERVAL_MINUTES` |