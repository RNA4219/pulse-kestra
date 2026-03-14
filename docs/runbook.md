# pulse-kestra 運用 Runbook

## 1. 障害調査の基本手順

### trace_id で追跡する

1. **bridge ログから `trace_id` を検索**
   ```bash
   # 例: grep で trace_id を検索
   grep "trace_id=abc123" /var/log/bridge/app.log
   ```

2. **taskstate で task を確認**
   ```bash
   python agent-taskstate_cli.py task show --task <task_id>
   ```

3. **Kestra 実行を確認**
   ```bash
   kestra execution get <execution_id>
   # または Web UI で確認
   ```

### ログの必須項目

Phase 2 以降、以下の項目がログに含まれます：

| 項目 | 説明 | 例 |
|------|------|-----|
| `trace_id` | リクエスト全体のトレースID | `abc123-def456` |
| `task_id` | taskstate のタスクID | `ts_001` |
| `note_id` | Misskey のノートID | `9abc123` |
| `kestra_execution_id` | Kestra 実行ID | `5XyZ123` |
| `reply_state` | 返信状態 | `pending`, `sent`, `failed` |
| `retry_count` | 再試行回数 | `0`, `1`, `2` |

---

## 2. Stuck Task 回復

### 症状
- task が `in_progress` のまま 15 分以上停滞
- heartbeat が自動検出（5分間隔でパトロール）

### 自動回復
heartbeat flow が以下を自動実行：
1. `in_progress` かつ 15 分以上更新がない task を検出
2. 該当 task を `review` status に変更
3. 運用者による確認を促す

### 手動確認と回復

1. **stuck task の一覧確認**
   ```bash
   python agent-taskstate_cli.py task list --status in_progress
   ```

2. **特定 task の詳細確認**
   ```bash
   python agent-taskstate_cli.py task show --task <task_id>
   ```

3. **回復方法の選択**

   **方法A: manual-replay flow で再実行**
   ```bash
   # Webhook 経由で実行
   POST /api/v1/main/executions/webhook/pulse/manual-replay/<key>
   {
     "event": "manual.replay",
     "task_id": "<task_id>",
     "replay_type": "full"
   }
   ```

   **方法B: taskstatus を `review` に変更**
   ```bash
   python agent-taskstate_cli.py task set-status \
     --task <task_id> \
     --to review \
     --reason "Manually marked for review"
   ```

---

## 3. Misskey 投稿失敗時の再送

### 症状
- `reply_state=failed` の task
- `reply_state=pending` のまま長時間更新なし

### 自動回復
heartbeat flow が以下を自動実行：
1. `pending` または `failed` の返信状態を持つ task を検出
2. 自動的に再送を試行
3. 成功時は `reply_state=sent` に更新

### 手動再送

**notifier-resend flow を実行**
```bash
POST /api/v1/main/executions/webhook/pulse/notifier-resend/<key>
{
  "event": "notifier.resend",
  "task_id": "<task_id>"
}
```

### 再送結果の確認

```bash
python agent-taskstate_cli.py task show --task <task_id>
# reply_state を確認: sent なら成功、failed なら失敗
```

---

## 4. Manual Replay 実行

### 実行タイミング
- 元の実行が失敗した場合
- 結果を再生成したい場合
- 一部のみ再実行したい場合

### 実行方法

**Kestra Web UI から実行**
1. Kestra UI を開く
2. `pulse/manual-replay` flow を選択
3. Trigger タブから "New execution"
4. パラメータを入力

**Webhook から実行**
```json
POST /api/v1/main/executions/webhook/pulse/manual-replay/<key>
{
  "event": "manual.replay",
  "task_id": "<original_task_id>",
  "replay_type": "full"
}
```

### replay_type の選択

| 値 | 説明 |
|----|------|
| `full` | worker 実行 + 通知再送（デフォルト） |
| `worker_only` | worker 実行のみ（通知なし） |
| `notifier_only` | 通知再送のみ（worker 実行なし） |

### 実行後の確認

1. **新規 task が作成される**
   - `original_task_id` で元の task と紐付け
   - `retry_count` がインクリメント

2. **確認コマンド**
   ```bash
   python agent-taskstate_cli.py task show --task <new_task_id>
   ```

---

## 5. 状態遷移確認

### taskstate status の一覧

| Status | 説明 |
|--------|------|
| `draft` | 初期状態 |
| `ready` | 実行待ち（キューイング） |
| `in_progress` | 実行中 |
| `review` | 手動確認待ち |
| `done` | 完了 |

### reply_state の一覧

| State | 説明 |
|-------|------|
| `pending` | 返信待ち |
| `sent` | 返信済み |
| `failed` | 返信失敗 |

### taskstate と Kestra の差分確認

1. **taskstate で task status を確認**
   ```bash
   python agent-taskstate_cli.py task show --task <task_id>
   ```

2. **Kestra execution status を確認**
   ```bash
   kestra execution get <execution_id>
   ```

3. **一致しない場合の対処**
   - task が `in_progress` だが Kestra が `FAILED` → stuck 判定
   - task が `done` だが Kestra が `RUNNING` → 状態不整合
   - 対処: task を `review` に変更し、manual intervention で解決

---

## 6. 定期ジョブ (heartbeat)

### スケジュール
- 5分間隔で自動実行

### 処理内容
1. **stuck task 検出**: `in_progress` かつ 15分以上更新なし
2. **pending reply 処理**: `pending`/`failed` の返信を再送
3. **retry candidate 検出**: `review` かつ `retry_count < 3` の task

### 設定変更

環境変数または Kestra globals で調整可能：

| 設定 | デフォルト | 説明 |
|------|-----------|------|
| `stuck_in_progress_minutes` | 15 | stuck 判定の閾値（分） |
| `stuck_pending_reply_minutes` | 10 | pending reply 判定の閾値（分） |
| `max_retry_count` | 3 | 自動リトライの最大回数 |

---

## 7. トラブルシューティング

### bridge が起動しない
1. 環境変数を確認: `MISSKEY_HOOK_SECRET`, `MISSKEY_HOOK_SECRET_HEADER`
2. ポートが使用されていないか確認
3. ログを確認: `journalctl -u pulse-bridge`

### Kestra flow が失敗する
1. Kestra UI で execution logs を確認
2. taskstate CLI のパスが正しいか確認
3. Python 環境が正しいか確認

### Misskey 投稿が失敗する
1. `MISSKEY_API_TOKEN` が有効か確認
2. Misskey API の rate limit を確認
3. ネットワーク接続を確認

### ログが見つからない
1. ログ出力先を確認
2. ログレベルを確認: `LOG_LEVEL=DEBUG`
3. trace_id が正しいか確認

---

## 8. 緊急時の連絡先とエスカレーション

### 優先度の判断

| 優先度 | 状況 | 対応時間 |
|--------|------|----------|
| P1 | サービス全体停止 | 即時 |
| P2 | 一部機能停止 | 1時間以内 |
| P3 | パフォーマンス低下 | 4時間以内 |
| P4 | 軽微な問題 | 翌営業日 |

### 復旧手順の優先順位

1. **安全確認**: データ損失のリスクを評価
2. **影響範囲特定**: trace_id で影響範囲を特定
3. **一時対処**: manual-replay または task の status 変更
4. **根本対処**: 原因調査と修正
5. **事後検証**: 再発防止策の実施