# pulse-kestra フロー定義

本書は Phase 1 から Phase 2 にかけて必要になる主要フローを、実装順に合わせて整理したものです。

## 1. Misskey mention フロー

### 1.1 正常系

1. Misskey が mention イベントを webhook で送信する
2. bridge が HTTP POST を受信し、secret を検証する
3. bridge が event type を判定し、`mention` 以外を早期 return する
4. bridge が入力本文に軽量 guard を適用する
5. bridge が `EventEnvelope` を生成する
6. bridge が `agent-taskstate` に task/run を `queued` で起票する
7. bridge が Kestra mention flow を起動する
8. Kestra が task を `running` に更新し、対象 worker adapter を呼び出す
9. worker adapter が実行結果を正規化して返す
10. Kestra が taskstate を `done` `needs_review` `failed` のいずれかに更新する
11. notifier が Misskey API へ返信を投稿する
12. 投稿結果をログへ残して flow を終了する

### 1.2 例外系

- secret 不一致: `401` 相当で reject し、task は起票しない
- guard 拒否: task を `needs_review` または専用拒否状態で記録し、必要なら固定文を返す
- taskstate 起票失敗: Kestra 起動前に失敗を返し、再送可能な監視ログを残す
- worker timeout: task を `failed` に更新し、retry 判定へ送る
- Misskey 投稿失敗: worker 結果は保持したまま、未通知フラグまたは retry 対象として扱う

## 2. heartbeat フロー

### 2.1 目的

Phase 2 の heartbeat は新しい業務処理を増やすためではなく、Phase 1 で起票済みの task/run を回復運用へつなぐために使う。主対象は `retry_count`、`reply_state`、stuck な `in_progress` task、worker 完了済みだが未通知の task とする。

### 2.2 正常系

1. Kestra の schedule trigger が heartbeat flow を起動する
2. flow が `agent-taskstate` から retry 対象、stuck task、未通知結果、手動回復待ち task を探索する
3. `reply_state=pending|failed` の task は notifier 再送候補として抽出する
4. heartbeat は Misskey へ直接投稿せず、`notifier-resend` flow を起動して再送を委譲する
5. `in_progress` のまま閾値超過した task は stuck 候補として抽出する
6. retry 可能な task は `manual-replay` flow を起動して replay を委譲する
7. 重い worker 処理が必要なものは別 flow へ委譲する
8. 結果を taskstate、reply 状態、ログへ反映する

### 2.3 制約

- heartbeat 自体は軽量に保つ
- worker 本体処理を heartbeat flow に直接埋め込まない
- 巡回数よりも idempotency、未通知回復、異常検知を優先する
- Phase 1 で導入済みの `trace_id` を利用し、heartbeat で新たな追跡子を乱立させない

## 3. manual replay フロー

### 3.1 用途

- webhook 再送や一時障害の復旧
- `needs_review` task の再試行
- 投稿だけ失敗した task の通知再実行

### 3.2 手順

1. オペレータが task ID または trace ID を指定して再実行要求を出す
2. bridge または Kestra manual trigger が `manual` EventEnvelope を生成する
3. 元 task との関連、`retry_count`、`idempotency_key` を保持したまま新規 run を起票する
4. `roadmap_request_json` と `reply_text` を task 正本から引き継ぐ
5. 指定 worker または notifier を再実行する
6. replay 対象が通知だけの場合は worker を再実行せず、保存済み `reply_text` をそのまま再送する

## 4. retry フロー

### 4.1 判定方針

- 一時的な HTTP 失敗や Misskey 投稿失敗は retry 候補
- secret 不一致、入力拒否、schema 不整合は retry 不可
- worker 固有の失敗は adapter が `failed` と `needs_review` を分ける
- retry 判定には `retry_count`、`reply_state`、最終 run 状態を使う

### 4.2 状態遷移

1. 実行失敗を検知する
2. retry 可否を判定する
3. retry 可なら task または child run を再起票する
4. retry 不可なら `failed` または `needs_review` に確定する

## 5. 重複防止

重複起票と二重返信を防ぐため、少なくとも次を実装対象とする。

- webhook event ID または `note_id` ベースの durable idempotency
- `trace_id` 単位の関連づけ
- Misskey reply 投稿前の未投稿確認
- 同一 task に対する concurrent run 制御
- manual replay 時の二重通知防止
