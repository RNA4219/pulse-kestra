# pulse-kestra 要件定義

本書は `docs/requirements.txt` を原案として整理した正式な要件定義です。`pulse-kestra` は会話 AI 本体ではなく、Misskey と Kestra を接続し、既存ワーカー OSS を安全に運用するためのイベントループ兼オーケストレーション層として定義します。

## 1. システム概要

### 1.1 目的

- Misskey からの会話イベントを安全に受信し、共通イベントモデルへ正規化する
- `agent-taskstate` を正本として task/run を起票し、業務状態を一元管理する
- Kestra によって webhook、schedule、heartbeat を統合制御する
- `memx-resolver` など既存ワーカーを薄い adapter 経由で呼び出す
- 軽量な環境でも継続運用できる設計を維持する

### 1.2 背景

既存 OSS 群により、文脈解決、状態管理、洞察抽出、実験判定、設計支援などの個別機能は概ね揃っている。一方で、入口の統一、発火条件、handoff 規約、状態遷移、非同期実行の交通整理、安全な Misskey 接続、軽量な heartbeat 制御といった中核的なオーケストレーション層は不足している。`pulse-kestra` はこの不足分を補う。

### 1.3 システム位置づけ

- 会話 UI と通知出口: Misskey
- trigger と flow 制御: Kestra
- 状態管理の正本: `agent-taskstate`
- 文脈・知識・判断などの専門処理: 各 worker
- これらを接続する制御面: `pulse-kestra`

## 2. スコープ

### 2.1 対象範囲

- Misskey webhook の受信
- Misskey API による返信と通知
- EventEnvelope への正規化
- 入力ガード
- `agent-taskstate` への task/run 起票と更新
- Kestra による flow 実行
- 既存 worker の呼び出し
- heartbeat と schedule による定期処理
- 実行ログ、エラー、再試行制御

### 2.2 対象外

- Misskey 本体の運用
- 重量級ローカル LLM 推論
- 長期検索インデックス基盤そのものの実装
- UI フロントエンドの全面刷新
- 自律人格の高度な会話設計そのもの

## 3. 想定ユースケース

### 3.1 会話駆動

1. Misskey で mention される
2. bridge が webhook を受信する
3. 入力検証と EventEnvelope 化を行う
4. `agent-taskstate` に task/run を起票する
5. Kestra flow から worker を実行する
6. 結果を Misskey に返信する

### 3.2 heartbeat 駆動

1. schedule trigger が一定間隔で発火する
2. 期限到来、retry 対象、stuck task、未通知結果を探索する
3. 必要な task のみ追加起票し、重い処理は別 task に委譲する

### 3.3 検索強化

1. 定期的または要求時に外部情報源を検索する
2. query rewrite、fan-out、rerank、dedup、要約を追加実行する
3. 条件を満たした結果だけを保存または通知する

## 4. 機能要件

### 4.1 イベント受信

| ID | 要件 |
|---|---|
| FR-001 | Misskey webhook を HTTP で受信できること |
| FR-002 | webhook secret を検証し、不正なリクエストを拒否できること |
| FR-003 | 受信イベントから `mention` を識別できること |
| FR-004 | 不要なイベント種別を無視できること |

### 4.2 入力ガード

| ID | 要件 |
|---|---|
| FR-010 | 入力本文に対して軽量な安全性検査を実施できること |
| FR-011 | 判定結果として `通過` `拒否` `要レビュー` `ログのみ` を扱えること |
| FR-012 | 初期段階では入力のみを対象とし、出力ガードは任意機能とすること |

### 4.3 イベント正規化

| ID | 要件 |
|---|---|
| FR-020 | すべての入口イベントを共通 EventEnvelope に変換できること |
| FR-021 | EventEnvelope は `event_id` `event_type` `source` `timestamp` `actor` `payload` `trace_id` を保持すること |
| FR-022 | manual、webhook、schedule、heartbeat が同一 envelope 形式を共有すること |

### 4.4 状態管理

| ID | 要件 |
|---|---|
| FR-030 | EventEnvelope 受信後に `agent-taskstate` へ task/run を起票できること |
| FR-031 | task 状態として `queued` `running` `waiting` `needs_review` `done` `failed` `cancelled` を扱うこと |
| FR-032 | worker 実行結果に応じて taskstate を更新できること |
| FR-033 | Kestra の実行履歴と taskstate の業務状態を分離すること |

### 4.5 worker 実行

| ID | 要件 |
|---|---|
| FR-040 | 少なくとも 1 種類の worker を外部プロセスまたは API として呼び出せること |
| FR-041 | 初期対応 worker 候補は `memx-resolver` `insight-agent` `experiment-gate` `Roadmap-Design-Skill` とすること |
| FR-042 | worker 呼び出しインターフェースを adapter 層で吸収すること |
| FR-043 | worker の追加、削除、差し替えを容易にすること |

### 4.6 Misskey 返信

| ID | 要件 |
|---|---|
| FR-050 | Misskey API を通じて返信投稿できること |
| FR-051 | 固定文返信、worker 結果返信、エラー通知の 3 種類を扱えること |
| FR-052 | 返信処理は worker 実行と疎結合であること |

### 4.7 heartbeat と schedule

| ID | 要件 |
|---|---|
| FR-060 | 定期実行 trigger を持つこと |
| FR-061 | heartbeat は期限到来確認、retry 対象確認、stuck task 確認、未通知結果確認に限定すること |
| FR-062 | heartbeat は重い worker 処理を直接持たず、必要時のみ別 task を発行すること |

### 4.8 検索強化

| ID | 要件 |
|---|---|
| FR-070 | 検索処理を独立 worker または外部 API 呼び出しとして追加できること |
| FR-071 | `query rewrite` `multi-source fan-out` `rerank` `dedup` `score normalization` `summarize-before-reply` を段階的に差し込めること |
| FR-072 | 検索強化は flow、script、plugin として後付け可能であること |

## 5. 非機能要件

### 5.1 軽量性

| ID | 要件 |
|---|---|
| NFR-001 | デスクトップ環境と N100/16GB 級の移植を前提に軽量であること |
| NFR-002 | 重い推論は外部 API または別ホストへ逃がせること |

### 5.2 可用性

| ID | 要件 |
|---|---|
| NFR-010 | Misskey 本体とは別ホストで動作可能であること |
| NFR-011 | bridge または Kestra の障害が Misskey 本体へ与える影響を最小化すること |
| NFR-012 | webhook 受信部は短時間で応答し、重処理は非同期化すること |

### 5.3 拡張性

| ID | 要件 |
|---|---|
| NFR-020 | 新規 worker 追加時に既存 flow 全体の大規模改修を避けること |
| NFR-021 | 検索、通知先、入力ガード、出力ガードを段階的に追加できること |
| NFR-022 | Misskey 依存部分を bridge 層に閉じ込めること |

### 5.4 観測性

| ID | 要件 |
|---|---|
| NFR-030 | `trace_id` により bridge、Kestra、taskstate、worker を横断追跡できること |
| NFR-031 | webhook 受信、secret 検証結果、guard 判定、task 起票、worker 実行開始/終了、Misskey 投稿結果、エラーを記録すること |

### 5.5 保守性

| ID | 要件 |
|---|---|
| NFR-040 | 初期実装では Kestra 本体 fork を行わないこと |
| NFR-041 | bridge は薄く保ち、業務ロジックを抱え込みすぎないこと |
| NFR-042 | plugin 化は反復利用が確認された処理に限定すること |

## 6. インターフェース要件

### 6.1 Misskey Webhook 入力

- 方式: HTTP POST + JSON body + secret header
- 必須処理: secret 検証、event type 判定、mention 抽出、EventEnvelope 化

### 6.2 Kestra 起動

- 候補: Webhook trigger、API trigger、schedule trigger
- 初期方針: bridge から Kestra の webhook trigger を起動する

### 6.3 Worker Adapter

最低限、以下の入出力契約を持つこと。

```json
{
  "task_id": "string",
  "worker": "string",
  "input": {},
  "context": {},
  "constraints": [],
  "trace_id": "string"
}
```

```json
{
  "status": "success|failed|needs_review",
  "summary": "string",
  "artifacts": [],
  "structured_output": {},
  "confidence": 0.0,
  "next_action": "string"
}
```

## 7. データモデル要件

### 7.1 EventEnvelope

```json
{
  "event_id": "evt_xxx",
  "event_type": "misskey.mention|manual|schedule|heartbeat",
  "source": "misskey|kestra|manual",
  "timestamp": "ISO8601",
  "actor": {
    "id": "string",
    "username": "string"
  },
  "payload": {},
  "trace_id": "trace_xxx"
}
```

### 7.2 TaskRecord

```json
{
  "task_id": "tsk_xxx",
  "status": "queued|running|waiting|needs_review|done|failed|cancelled",
  "trigger": "misskey.mention|heartbeat|schedule|manual_replay",
  "worker": "string",
  "retry_count": 0,
  "reply_state": "pending|sent|failed|skipped",
  "reply_text": "string",
  "roadmap_request_json": "string",
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "trace_id": "trace_xxx"
}
```

## 8. フェーズ要件

### 8.1 Phase 1: 最小 PoC

- Kestra ローカル起動
- bridge 構築
- Misskey webhook 受信
- 固定文返信
- taskstate 起票
- 1 worker 接続

### 8.2 Phase 2: 運用回復と再実行の整備

- heartbeat flow 本体の実装
- retry 制御と未通知結果の再送制御
- manual replay による task/run 再実行導線の整備
- durable dedupe と idempotency 永続化
- stuck task と通知失敗の回復運用
- 観測性、アラート、運用手順の整備

### 8.3 Phase 3: 拡張

- 検索強化
- rerank
- output guard
- 複数 worker chaining
- plugin 化

## 9. 受け入れ条件

Phase 1 完了条件は以下とする。

1. Misskey の mention から webhook を受信できる
2. secret 検証が通る
3. 入力ガードが動く
4. EventEnvelope が生成される
5. taskstate に task/run が保存される
6. Kestra flow が起動する
7. 1 つの worker が呼び出される
8. 結果または固定文が Misskey に返信される
9. 一連の `trace_id` をログで追跡できる

Phase 2 では次を追加の完了条件とする。

1. heartbeat が retry 対象、stuck task、未通知結果を定期検査できる
2. manual replay で task ID または trace ID から再実行できる
3. durable dedupe により同一 note の二重起票を抑止できる
4. `reply_text` と `roadmap_request_json` を task 正本に保存し、manual replay / notifier resend で再利用できる
5. Misskey 投稿失敗時に未通知状態を残し、再送導線へ引き渡せる
6. 運用手順上、taskstate と Kestra の差分を追跡して回復できる

## 10. リスク

- webhook 再送による二重起票
- 入力ガードの誤検知
- taskstate と Kestra 実行状態の乖離
- Misskey API 制限やトークン権限不足
- worker のタイムアウト設計不足
- heartbeat の肥大化
- plugin 化の早すぎる着手による保守コスト増

## 11. 設計原則

1. 薄く作る
2. 正本は taskstate
3. Misskey 依存は bridge に閉じ込める
4. heartbeat は軽く保つ
5. 重い推論は外に逃がす
6. flow は増やしても本体は太らせない
7. plugin は最後に検討する
