# Phase 1 検収メモ

作成日: 2026-03-15

## 1. 対象

- Misskey webhook 受信 bridge
- EventEnvelope 正規化
- taskstate 起票と初期状態設定
- Kestra mention flow の task / run 状態遷移
- Misskey 返信 payload 契約

## 2. 検収観点

- secret 検証、mention 判定、roadmap JSON 検証が仕様どおりであること
- `trace_id` と `idempotency_key` が生成され、Kestra payload へ伝播すること
- `agent-taskstate` への task 起票、state put、status ready が bridge で成立すること
- Kestra flow が `run start` / `run finish` を `agent-taskstate` CLI 契約どおりに呼ぶこと
- task / run 状態遷移が Phase 1 で定義した流れに沿うこと
- Misskey 返信本文と payload 契約が保持されること
- guard 拒否入力が taskstate に記録されること

## 3. 今回追加した確認

- `EventEnvelope` の必須項目を直接検証する acceptance テストを追加
- bridge ログに `trace_id` が乗ることを確認するテストを追加
- Misskey reply payload の `replyId` `text` `visibility` を確認するテストを追加
- Kestra flow の task 間ファイル受け渡しと taskstate CLI 契約を確認するテストを補強

## 4. 実施コマンド

```bash
cd bridge
python -m pytest -q
```

## 5. 結果

- 133 passed
- `pytest-asyncio` の deprecation warning が 1 件あるが、Phase 1 検収を止める内容ではない

## 6. 判定

- repo 内の Phase 1 実装検収は完了
- ただし実 Kestra / Misskey 環境を使った運用検証は別途必要
