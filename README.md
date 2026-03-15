# pulse-kestra

`pulse-kestra` は、Misskey を会話・通知の表層、Kestra をイベント駆動の制御基盤として利用し、既存ワーカー OSS を疎結合で接続するための薄いオーケストレーション層です。

Phase 1 の bridge 実装に加えて、heartbeat / manual replay / notifier resend を含む Phase 2 の制御面が動作可能です。通常運転の正規チェーンは `research -> insight -> gate -> sync -> notify` を前提とし、`pulse-kestra` はその入口・再送・再実行・重複抑止を担います。

## 目的

- Misskey mention と定期実行を単一のイベントモデルで扱う
- `agent-taskstate` を正本とした状態管理を維持する
- `memx-resolver` など既存ワーカーを差し替え可能な形で接続する
- デスクトップ検証から N100 クラス環境への移植まで見据えて軽量に保つ

## ドキュメント入口

- [要件定義](./docs/requirements.md)
- [仕様書](./docs/specification.md)
- [アーキテクチャ方針](./docs/architecture.md)
- [主要フロー](./docs/flows.md)
- [イベントとインターフェースの schema](./docs/event-schema.md)
- [実装準備計画](./docs/implementation-plan.md)
- [原案メモ](./docs/requirements.txt)
- [Phase 1 検収メモ](./docs/acceptance-note-phase1.md)
- [Phase 1 完了リリースノート](./docs/releases/phase1.md)

## Phase 1 実装状況

### 完了

- [x] Misskey webhook 受信 bridge (`bridge/`)
- [x] secret 検証、mention 判定、コマンド抽出
- [x] 入力ガード (FR-010, FR-011, FR-012)
- [x] EventEnvelope 生成、`trace_id` / `idempotency_key` 付与
- [x] `agent-taskstate` への task 起票・状態初期化
- [x] Kestra webhook trigger 呼び出し
- [x] Misskey 返信 notifier サービス
- [x] Kestra flow 定義 (mention 処理)
- [x] 環境変数サンプル・起動スクリプト
- [x] テストフィクスチャ
- [x] E2E 統合テスト

### テスト状況

- **133 tests passed**
- カバレッジ: 入力ガード、パーサー、ゲートウェイ、クライアント、エンドポイント

### Phase 2 運転面

- [x] durable dedupe の正本キー定義 (`note` / `reply` / `replay`)
- [x] heartbeat flow 本体
- [x] manual replay と未通知再送導線
- [x] stuck task 回復を含む retry 制御
- [x] `research -> insight -> gate -> sync -> notify` を崩さない制御面ドキュメント
- [ ] 複数 worker chaining の本実装

## ディレクトリ構成

```
pulse-kestra/
├── bridge/                    # FastAPI ベースの HTTP サービス
│   ├── src/bridge/
│   │   ├── config.py          # 環境変数・設定
│   │   ├── main.py            # FastAPI アプリケーション
│   │   ├── models/            # Pydantic モデル
│   │   ├── services/          # ビジネスロジック (入力ガード含む)
│   │   └── routers/           # HTTP エンドポイント
│   ├── tests/                 # 自動テスト (133 tests)
│   ├── .env.example           # 環境変数テンプレート
│   └── start.sh / start.bat   # 起動スクリプト
├── kestra/
│   └── flows/
│       └── mention.yaml       # Misskey mention 処理 flow
├── adapters/
│   └── roadmap-design-skill/  # Roadmap Design Skill adapter
├── fixtures/                  # テストフィクスチャ
│   ├── webhook_*.json         # Webhook ペイロードサンプル
│   ├── worker_*.json          # Worker レスポンスサンプル
│   └── misskey_*.json         # Misskey API レスポンスサンプル
└── docs/                      # 設計ドキュメント
```

## クイックスタート

```bash
cd bridge

# 1. 環境変数を設定
cp .env.example .env
# .env を編集して必要な値を設定

# 2. 依存関係をインストール
pip install -e ".[dev]"

# 3. サーバーを起動
./start.sh  # Linux/macOS
# または
start.bat   # Windows

# 4. ヘルスチェック
curl http://localhost:8000/health
```

## 想定コンポーネント

- `bridge`: Misskey webhook 受信、secret 検証、入力ガード、EventEnvelope 化
- `kestra flows`: mention、heartbeat、manual replay、notifier resend などの flow 定義
- `taskstate gateway`: `agent-taskstate` への起票と状態更新
- `worker adapters`: 既存ワーカーの呼び出し吸収層
- `reply notifier`: Misskey 返信と通知

## 関連システム

- `agent-taskstate`: task state の正本
- `memx-resolver`: 文脈解決と knowledge 参照
- `insight-agent`: 洞察抽出
- `experiment-gate`: 実験実行可否判定
- `Roadmap-Design-Skill`: 設計支援


## 運用上の正規チェーン

`pulse-kestra` は重い worker の代わりではなく、`research -> insight -> gate -> sync -> notify` の制御面です。heartbeat は軽量巡回に限定し、必要時のみ replay / resend を起動します。

## 最小観測点

- 日次 run 数
- `ok / degraded / failed` 件数
- replay 実行件数
- 未通知再送件数
- notification failure 件数
- tracker sync failure 件数
- duplicate suppression 件数

これらは taskstate の `retry_count`, `reply_state`, `duplicate_suppression_count` と Kestra flow output を集計元にします。
