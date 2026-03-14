# Durable Dedupe 設計

本書は同一 note の二重起票、および manual replay 時の二重通知を防ぐための重複排除（dedupe）設計を定義する。

## 1. 目的

1. **二重起票防止**: 同一 Misskey mention から複数の task が作成されるのを防ぐ
2. **二重通知防止**: 同一 task から複数の Misskey 返信が送られるのを防ぐ
3. **replay 安全性**: manual replay 実行時に冪等性を保証する

## 2. Dedupe Key 設計

### 2.1 task 起票用 dedupe key

```
misskey:{note_id}
```

- **構成**: `misskey:` プレフィックス + note ID
- **例**: `misskey:9xyz123abc`
- **スコープ**: task 作成時の重複検知

### 2.2 reply 送信用 dedupe key

```
reply:{task_id}:{reply_target}
```

- **構成**: `reply:` プレフィックス + task ID + 返信先 note ID
- **例**: `reply:tsk_01JQ321DEF:9xyz123abc`
- **スコープ**: Misskey 投稿時の重複検知

### 2.3 replay 実行用 dedupe key

```
replay:{original_task_id}:{replay_type}:{timestamp_rounded}
```

- **構成**: `replay:` プレフィックス + 元 task ID + replay 種別 + タイムスタンプ（分単位で丸め）
- **例**: `replay:tsk_01JQ321DEF:full:202603141000`
- **スコープ**: 同一 replay の短時間内重複実行防止

## 3. 永続化場所

### 3.1 検討案

| 案 | メリット | デメリット |
|---|---|---|
| agent-taskstate に紐付け | 既存 DB を流用 | スキーマ拡張が必要 |
| bridge 側 SQLite | 軽量、独立 | 別管理が必要 |
| Redis | 高速、TTL サポート | インフラ追加 |

### 3.2 Phase 2 採用案

**Phase 2 では `agent-taskstate` の task レコードに埋め込む**

- `idempotency_key` フィールドを dedupe key として使用
- 既存の `idempotency_key` は `misskey:{note_id}` 形式で既に一致
- 追加テーブルなしで実現可能

### 3.3 将来拡張

Phase 3 以降で Redis 導入を検討：
- TTL による自動期限切れ
- 高頻度アクセスへの対応
- 分散環境での一意性保証

## 4. 判定タイミングと動作

### 4.1 Webhook 受信時（task 起票）

```text
webhook 受信
    ↓
idempotency_key = "misskey:{note_id}" を生成
    ↓
taskstate で同一 idempotency_key を検索
    ↓
├── 存在する
│       ├── status = done → 204 (既に処理済み、再送不要)
│       ├── status = failed → 409 (競合、retry 可能)
│       └── status = in_progress → 204 (処理中、待機)
│
└── 存在しない
        └── 新規 task 作成へ進む
```

### 4.2 Reply 送信時

```text
post-reply タスク実行前
    ↓
reply_dedupe_key = "reply:{task_id}:{reply_target}" を生成
    ↓
outputFiles['reply_sent.txt'] の存在確認
    ↓
├── 存在する → 既に送信済み、スキップ
│
└── 存在しない
        └── Misskey API 呼び出し
                ↓
                成功時: reply_sent.txt を作成
                失敗時: リトライ判定へ
```

### 4.3 Manual Replay 実行時

```text
replay リクエスト受信
    ↓
replay_key = "replay:{original_task_id}:{type}:{minute}" を生成
    ↓
直近 5 分以内の同一 replay 実行を確認
    ↓
├── 存在する → 409 (重複実行を拒否)
│
└── 存在しない
        └── replay 実行へ進む
                ↓
                元 task の idempotency_key を継承
                新 task は original_task_id で参照
```

## 5. 分岐定義

### 5.1 二重起票の扱い

| 状況 | HTTP ステータス | 動作 |
|---|---|---|
| 同一 note_id で処理済み (done) | 204 | 何もしない（冪等） |
| 同一 note_id で処理中 | 204 | 何もしない（待機） |
| 同一 note_id で失敗 | 409 | 競合エラー、manual retry 案内 |

### 5.2 Reply 再送の可否

| 状況 | 再送可否 | 理由 |
|---|---|---|
| `reply_state = pending` | 可 | まだ送信されていない |
| `reply_state = failed` | 可 | 送信失敗、再送が必要 |
| `reply_state = sent` | 不可 | 既に送信済み |
| `reply_state = skipped` | 不可 | スキップ対象 |

### 5.3 Manual Replay の二重実行

- 同一分（分単位）での同一 replay 種別は拒否
- 異なる分での再実行は許可

## 6. 実装位置

### 6.1 Task 起票重複検知

- **場所**: `bridge/src/bridge/routers/webhooks.py`
- **実装**: `TaskstateGateway.find_by_idempotency_key()` を追加

### 6.2 Reply 送信重複検知

- **場所**: `kestra/flows/mention.yaml` の `post-reply` タスク
- **実装**: outputFiles の存在確認

### 6.3 Replay 重複検知

- **場所**: 新規 `kestra/flows/replay.yaml`
- **実装**: replay 実行履歴の確認

## 7. テスト項目

### 7.1 Task 起票重複検知

- [ ] 同一 note_id で 2 回 webhook 受信 → 1 task のみ作成
- [ ] done 状態の task に再 webhook → 204 返却
- [ ] in_progress 状態の task に再 webhook → 204 返却

### 7.2 Reply 重複検知

- [ ] post-reply 成功後の再実行 → スキップ
- [ ] failed 状態からの再送 → 成功

### 7.3 Replay 重複検知

- [ ] 同一分での同一 replay → 409 返却
- [ ] 1 分後の同一 replay → 実行される

## 8. 環境変数

| 変数名 | デフォルト | 説明 |
|---|---|---|
| `PULSE_DEDUPE_ENABLED` | `true` | dedupe 機能の有効/無効 |
| `PULSE_REPLAY_DEDUPE_WINDOW_MINUTES` | `5` | replay 重複判定の時間窓 |