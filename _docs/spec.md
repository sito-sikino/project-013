# Supervisorベース Discord マルチエージェントシステム 要件定義（完全版 / spec.md）

## 1. 概要
- Discord上で動作するマルチエージェントAIシステム。  
- **Supervisorパターン**に基づき、**Spectra**が中枢を担う（受信ゲートウェイ）。  
- 生成は **LLM（Gemini 2.0 Flash）を1イベント=1回**。  
- 送信は **選定されたBot名義（Spectra/LynQ/Paz）**で **Typing → 本文（REST）**。  
- **06:00に日報（Spectra固定・500字以内・投稿先=command-center）**を生成し、投稿後に**Redis全文脈を全リセット**。  
- **Fail-Fast原則／フォールバック禁止原則**を徹底し、**JSONL 1ファイル**にシステム＋会話ログを一元管理。  
- **active_channel は常に1つ**。`/task commit` で即上書き（移動）。

---

## 2. 用語
- **Supervisor**: LLMプロンプト組立と生成の方針決定（人格・文字数・出力形式）。`_docs/langgraph_supervisor_pattern_complete_guide`参照。  
- **受信ゲートウェイ**: SpectraのみがDiscordイベントを受信する入口。  
- **選定Bot**: 生成結果で決まる送信名義（spectra｜lynq｜paz）。  
- **active_channel**: その時点で自発・タスク作業の対象となる唯一のチャンネル。  
- **全文脈**: 当日分のすべての発話（user/agents）を1つのセッションに時系列保存したもの。

---

## 3. 時間割（モード制御 / JST固定）
| モード        | 時間帯           | 動作 |
|--------------|------------------|------|
| **STANDBY**  | 00:00–05:59      | すべてのイベントを破棄（ログのみ記録） |
| **PROCESSING** | 06:00             | **日報処理のみ**（Spectra固定・500字・投稿先=command-center）。完了後 **ACTIVE** へ遷移 |
| **ACTIVE**   | 06:01–19:59      | 基準の `active_channel=command-center`。`/task commit` で `creation`／`development` に即移動 |
| **FREE**     | 20:00–23:59      | `active_channel=lounge` 固定 |

- モード遷移時の **active_channel 初期値**: ACTIVE→`command-center`、FREE→`lounge`。  
- **06:00を逃した場合のバックフィルは行わない**（Fail-Fast方針に従いスキップ）。

---

## 4. イベントと優先順位（直列実行）
- **優先順位**: `Slash → ユーザー発言 → 自発（tick）`。  
- **直列実行**: 常に1件ずつ処理（同時実行なし）。  
- **受信はSpectraのみ**。送信は選定Bot名義で行う。  
- **1イベント=LLM1回**（reply/auto/report いずれも）。

---

## 5. チャンネル仕様
- **command-center**: 会議・指揮（最大**100字**）  
- **creation**: 創作・アイデア（最大**200字**）  
- **development**: 実装・技術（最大**200字**）  
- **lounge**: 雑談（最大**30字**）

**文字数制御**: プロンプトで上限内に**途中で切らず収める**ことを明示（**最終ハードカット実装なし**）。

---

## 6. LLM仕様
- **モデル**: Gemini 2.0 Flash（無料枠）。  
- **入力（Supervisor → LLM）**:
```json
{
  "kind": "reply" | "auto" | "report",
  "channel": "command-center" | "creation" | "development" | "lounge",
  "task": {"content": "<str|null>", "channel": "creation|development|null"},
  "context": "<当日全文脈（Redisから読み出したテキスト/構造化内容）>",
  "limits": {"cc":100,"cr":200,"dev":200,"lo":30},
  "persona": "fixed", 
  "report_config": {"speaker":"spectra","max_chars":500}
}
````

* **出力（LLM → Supervisor）**:

```json
{"speaker":"spectra|lynq|paz","text":"..."}
```

* **人格**:

  * Spectra=司会・要点整理・結論先
  * LynQ=実装・技術具体化・手順化
  * Paz=発想・着想・拡張
* **禁止事項/比率/誘導/監視**はプロンプトに書かない。
* **report**時は `speaker="spectra"` 固定、**500字以内**。

---

## 7. データと状態

### 7.1 State（プロセス内）

* `mode: STANDBY|PROCESSING|ACTIVE|FREE`
* `active_channel: "command-center"|"creation"|"development"|"lounge"`（**常に1つ**）
* `task: { content: str|null, channel: "creation"|"development"|null }`（**常に1件**）

### 7.2 Redis（当日全文脈 / セッションID: `discord_unified`）

* レコード構造:
  `agent: "spectra"|"lynq"|"paz"|"user"`, `channel`, `timestamp(ISO8601)`, `text`
* **保存順序**:
  **生成前に必ず全文読み込み** → 送信成功後に追記。
* **リセット**: 日報（06:00）投稿直後に**全削除**。
* **短縮／要約／チャンネル別分割**: 実装しない（単一ストリームで一体管理）。

---

## 8. Slashコマンド（最優先）

### 8.1 仕様

* コマンド: `/task commit <channel> "<内容>"`

  * `<channel>`: `creation` または `development`
  * `<内容>`: タスク説明（文字列）

### 8.2 動作

1. **LLM不要で即処理**。
2. `task.content` と `task.channel` を更新。
3. **`active_channel = <channel>` に即上書き**（唯一のアクティブとして移動）。
4. **command-center に Spectra名義で短い決定通知を1本だけ投稿**（Typing→REST）。
5. Slash入力と決定通知を**Redis全文脈に追記**。

### 8.3 バリデーション

* `<channel>` と `<内容>` の**少なくとも一方**を指定。
* 未知の `<channel>`、両方欠落、空文字 `<内容>` は**Fail-Fast**でエラー記録のみ（返信・代替生成は行わない）。

---

## 9. ユーザー発言（次優先 / 即応答）

1. **Redis全文脈を読み込み**＋`active_channel`＋`task` をSupervisorへ。
2. **LLM 1回**で `{speaker,text}` を決定（**途中で切らず上限内**）。
3. **Typing（選定Bot名義）→ REST送信**で**受信チャンネルにそのまま返答**。
4. ユーザー発言とBot応答を**Redisに追記**。

---

## 10. 自発発言（低優先 / tickトリガ）

* **テスト**: `15秒ごと / 実行確率100% / 実行は5分以内で停止`
* **本番**: `5分ごと / 実行確率33%`

抽選ヒット時のみ:

1. **Redis全文脈を読み込み**＋`active_channel`＋`task` をSupervisorへ。
2. **LLM 1回**で `{speaker,text}`。
3. **Typing（選定Bot名義）→ REST送信**で `active_channel` に投稿。
4. 投稿を**Redisに追記**。

* 直列処理のため、Slash／ユーザー発言が到着していれば**そちらが先に処理**される。

---

## 11. 日報（06:00 / PROCESSING）

1. **Redis全文脈を読み込み**。
2. **Spectra固定・500字以内**で**LLM 1回**により本文生成（**途中で切らず上限内**）。
3. **Typing（Spectra）→ REST送信**で **command-center** に投稿。
4. **Redisを全リセット**（当日分ゼロから再開）。
5. `mode=ACTIVE` に遷移し、`active_channel=command-center` に再設定。
6. 06:00を過ぎて起動した場合は**実行しない**（バックフィルなし）。

---

## 12. Discord送信仕様

* **REST送信のみ**（DM・編集・Webhookは**未採用**）。
* **Typingは必ず選定Bot名義**で送信直前に1回。
* **返信先**: ユーザー応答は**受信チャンネル**、自発は**active\_channel**。
* **別チャンネル誘導はしない**。

---

## 13. ログ仕様（JSONL 1ファイル / 一元管理）

* **Fail-Fast**: 例外検知時は**即中断**し、該当ステージとエラー要約を記録。**再試行・代替生成・フォールバックは禁止**。
* **ファイル**: `logs/run.log`（必要なら日次ローテ: `run-YYYYMMDD.log`、フォーマット不変）

**各行の必須キー**:

```json
{
  "ts": "2025-08-12T12:34:56+09:00",
  "event_type": "slash|user_msg|auto_tick|report",
  "channel": "command-center|creation|development|lounge",
  "actor": "user|spectra|lynq|paz|system",
  "payload_summary": "先頭80字など",
  "result": "ok|error",
  "error_stage": "settings|slash|plan|typing|send|report|memory|null",
  "error_detail": "例外要約 or null"
}
```

**エラーステージ定義**:

* `settings`: 設定欠落・無効値
* `slash`: Slash解析/状態更新失敗
* `plan`: LLM呼び出し（生成）失敗
* `typing`: Typing送信失敗
* `send`: 本文送信失敗
* `report`: 日報処理失敗
* `memory`: Redis 読込/追記/リセット失敗

---

## 14. セキュリティ・運用

* **Secrets**: `.env` で管理し、**settings経由で注入**（ハードコード禁止）。
* **権限**: 3Bot（Spectra/LynQ/Paz）はサーバー参加済みで、4チャンネルへの送信権限を付与（受信はSpectraのみ）。
* **時刻**: 常に `Asia/Tokyo`。
* **起動時チェック**: `settings` → `Redis` → `Discord` の順に**Fail-Fast**で検証し、失敗時はエラーログを出して終了。

---

## 15. 非採用事項（明示）

* フォールバック／再試行／自動要約／短縮
* 発言比率制御／クールダウン／監視
* DM／編集／Webhook
* 日次上限制御／トークンバケット／複雑な並列化／イベントバス

---

## 16. 受け入れ基準（DoD）

1. **Slash**: `active_channel` が即時切替され、**command-center にSpectra名義の決定通知1本**を投稿。以後の応答/自発は新チャンネルで実行。
2. **ユーザー応答**: 受信直後に**Typing（選定Bot）**、数秒以内に**上限内の本文**を**受信チャンネル**へ返信。Redisに発言・応答を追記。
3. **自発（dev/prod）**: dev=15s/100%（≤5分で複数回）、prod=5min/33%で `active_channel` に投稿。
4. **日報（06:00）**: **Spectra固定・500字以内**で **command-center** に投稿後、**Redis全リセット**。`mode=ACTIVE / active_channel=command-center` に遷移。
5. **ログ**: すべてのイベントで JSONL に `result` と（エラー時は）`error_stage` が記録される。
6. **例外時**: **Fail-Fast**でそのイベント処理のみ中断し、フォールバックは行わない。

---

## 17. 参考・設定値（目安）

* **Tick**: dev=`15s/100%/≤5min`、prod=`300s/33%`
* **Channel Limits**: `cc=100 / cr=200 / dev=200 / lo=30`
* **ENV**: `ENV=dev|prod`, `TZ=Asia/Tokyo`
* **Tokens/IDs**: `SPECTRA_TOKEN / LYNQ_TOKEN / PAZ_TOKEN`、`CHAN_COMMAND_CENTER / CHAN_CREATION / CHAN_DEVELOPMENT / CHAN_LOUNGE`
* **Redis**: `REDIS_URL`（セッションIDは固定 `"discord_unified"`）
* **Gemini**: `GEMINI_API_KEY`

---
