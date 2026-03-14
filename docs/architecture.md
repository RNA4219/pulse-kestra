# pulse-kestra アーキテクチャ方針

## 1. 設計方針

`pulse-kestra` は、Misskey と worker 群の間に業務ロジックを大量に抱え込むのではなく、イベント受信、正規化、起票、flow 制御、結果通知という最小限の責務に限定する。要件上の主眼は「安定した handoff」と「状態の見失い防止」にあり、実際の専門処理は外部 worker 側へ委譲する。

設計原則は次の 5 点に集約する。

- state の正本は `agent-taskstate` に置く
- Misskey 依存は bridge 層に閉じ込める
- Kestra は trigger と orchestration に専念させる
- worker 呼び出しは adapter で統一する
- 重い処理は非同期化し、bridge では持たない

## 2. 論理構成

```text
Misskey
  ├─ Webhook (mention / reply / etc.)
  └─ API (notes/create)

        ↓

Bridge
  ├─ SecretValidator
  ├─ InputGuard
  ├─ EventNormalizer
  ├─ TaskstateGateway
  └─ KestraTriggerClient

        ↓

Kestra
  ├─ mention flow
  ├─ heartbeat flow
  ├─ manual replay flow
  └─ retry / schedule trigger

        ↓

Worker Adapter Layer
  ├─ memx-resolver adapter
  ├─ insight-agent adapter
  ├─ experiment-gate adapter
  └─ roadmap adapter

        ↓

External Systems
  ├─ agent-taskstate
  ├─ worker processes / APIs
  └─ observability sink
```

## 3. コンポーネント責務

### 3.1 Bridge

- Misskey webhook を受信する
- secret を検証する
- 受信イベントを `EventEnvelope` に正規化する
- 初期入力ガードを実施する
- `agent-taskstate` に task/run を起票する
- Kestra webhook trigger を呼び出す
- 可能な限り短時間で応答し、長時間処理を避ける

### 3.2 Kestra

- trigger ごとの flow を分離する
- retry と schedule を扱う
- worker 実行順序と timeout を制御する
- 実行メタデータを保持する
- taskstate の業務状態とは別に、flow 実行状態を記録する

### 3.3 Taskstate Gateway

- task/run 起票 API の薄い wrapper
- task 状態遷移の統一窓口
- `trace_id` と task ID の対応管理
- Kestra 実行 ID と task ID の関連づけ

### 3.4 Worker Adapter

- worker ごとの差異を request/response 契約へ吸収する
- CLI / HTTP / script 実行の違いを隠蔽する
- timeout、標準出力、終了コード、structured output を正規化する
- 失敗時に `failed` と `needs_review` を判別しやすくする

### 3.5 Reply Notifier

- 固定文、worker 結果、エラー通知を Misskey API へ投稿する
- 投稿失敗時に retry 対象へ切り分ける
- 二重投稿防止のため reply idempotency key を扱えるようにする

## 4. 境界の置き方

### 4.1 Bridge に持たせるもの

- HTTP 受信
- 署名または secret 検証
- 軽量入力ガード
- EventEnvelope 生成
- task 起票と flow 起動

### 4.2 Bridge に持たせないもの

- 文脈解決本体
- 複雑な意思決定
- 長時間 worker 実行
- 高度な返信文生成

### 4.3 Kestra に持たせるもの

- flow 分岐
- retry とスケジュール
- 実行パラメータの受け渡し
- timeout と再試行ポリシー

### 4.4 Kestra に持たせないもの

- taskstate の正本保持
- Misskey 固有 payload の深い解釈
- worker 固有ロジックの埋め込み

## 5. Phase 1 の実装単位

Phase 1 では次の 4 つを最小単位として用意する。

1. webhook 受信から EventEnvelope 生成までの bridge
2. taskstate 起票と Kestra 起動をつなぐ gateway
3. 1 worker を呼び出せる adapter
4. 固定文または worker 結果を返せる notifier

この段階では plugin 拡張や複数 worker chaining は扱わない。

## 6. デプロイと運用前提

- Misskey と `pulse-kestra` は別ホスト運用可能とする
- bridge は小さな HTTP サービスとして単体で再起動可能にする
- Kestra はローカル検証時に単独起動できるようにする
- PostgreSQL 永続化は Phase 2 で導入する
- secrets はソースコードへ埋め込まず環境変数または secret store から供給する

## 7. 初期ディレクトリ方針

詳細は [実装準備計画](./implementation-plan.md) に譲るが、責務分離のため次の粒度で開始する。

```text
bridge/
  cmd/
  internal/
kestra/
  flows/
adapters/
docs/
```

この分け方により、bridge、flow、adapter の変更を独立して進めやすくする。
