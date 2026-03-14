# Phase 1 完了リリースノート

日付: 2026-03-15

## 概要

Phase 1 では、Misskey mention を入口にして `pulse-kestra` がイベントを正規化し、`agent-taskstate` を正本として task を起票し、Kestra flow を通じて worker 実行へ接続する最小の運用基盤を整備しました。あわせて、Misskey 返信 payload、task / run 状態遷移、`trace_id` による横断追跡、guard 記録まで含めた repo 内検収を完了しています。

## 主要な追加内容

- FastAPI ベースの bridge を追加
- Misskey webhook secret 検証、mention 判定、`@pulse roadmap` の JSON 抽出を実装
- `EventEnvelope`、`trace_id`、`idempotency_key` の正規化を実装
- `agent-taskstate` CLI を通じた task 起票、state put、status 更新を実装
- Kestra mention flow を追加し、task / run の開始・終了契約を整理
- Roadmap Design Skill を初期 worker として接続
- Misskey reply payload 契約を追加
- guard 拒否入力の taskstate 記録を追加

## 検収結果

- `python -m pytest -q` 実行結果: 133 passed
- repo 内 Phase 1 検収: 完了
- 非 blocking: `pytest-asyncio` deprecation warning 1 件

## 今回補強した検収観点

- `EventEnvelope` 必須項目の直接検証
- `trace_id` のログ伝播確認
- Misskey reply payload の `replyId` `text` `visibility` 検証
- Kestra flow の task 間ファイル受け渡し検証
- `agent-taskstate` run CLI 契約 (`run start` / `run finish`) の検証

## 既知の残事項

- 実 Kestra / Misskey 環境での運用検証
- heartbeat flow 本体
- durable dedupe
- 高度な retry / 未通知管理

## 関連ドキュメント

- [Phase 1 検収メモ](../acceptance-note-phase1.md)
- [要件定義](../requirements.md)
- [実装準備計画](../implementation-plan.md)
