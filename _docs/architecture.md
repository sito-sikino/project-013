# アーキテクチャ設計

## 1) ディレクトリ構成

```

app/
app.py          # 入口／イベントディスパッチ（直列・優先度制御・スケジューラ）
settings.py     # .env読込・定数一元管理
state.py        # mode / active\_channel / task
store.py        # Redis全文脈: read\_all / append / reset
discord.py      # Typing / REST送信（Botトークン切替）
supervisor.py   # prompt() / generate() ＊LLM 1回→{speaker,text}
logger.py       # JSONL一元ログ（system+conversation）
docs/
spec.md         # 要件定義
logs/
run.log         # JSONL（1ファイル一元管理）
.env

````

---

## 2) 設定（settings.py / .env）

```ini
ENV=prod                     # dev|prod
TZ=Asia/Tokyo

# Discord Bot tokens
SPECTRA_TOKEN=...
LYNQ_TOKEN=...
PAZ_TOKEN=...

# Discord Channel IDs
CHAN_COMMAND_CENTER=...
CHAN_CREATION=...
CHAN_DEVELOPMENT=...
CHAN_LOUNGE=...

# Redis
REDIS_URL=redis://...

# Gemini
GEMINI_API_KEY=...

# Tick
TICK_INTERVAL_SEC_DEV=15
TICK_PROB_DEV=1.0
MAX_TEST_MINUTES=5
TICK_INTERVAL_SEC_PROD=300
TICK_PROB_PROD=0.33

# Mode schedule (JST)
STANDBY_START=00:00
PROCESSING_AT=06:00
FREE_START=20:00

# Channel limits（プロンプトで厳守・最終ハードカットなし）
LIMIT_CC=100
LIMIT_CR=200
LIMIT_DEV=200
LIMIT_LO=30

# Log
LOG_FILE=logs/run.log
````

> すべて **settings.py** 経由で参照。ハードコード禁止。

---

## 3) 型とステート（state.py）

### 列挙

```
Mode      = "STANDBY" | "PROCESSING" | "ACTIVE" | "FREE"
Channel   = "command-center" | "creation" | "development" | "lounge"
Agent     = "spectra" | "lynq" | "paz" | "user"
EventKind = "slash" | "user_msg" | "auto_tick" | "report_0600"
```

### 構造

```
Task {
  content: str | null
  channel: "creation" | "development" | null
}

State {
  mode: Mode
  active_channel: Channel
  task: Task
}
```

### 公開I/F

```
mode_from_time(now_jst) -> Mode
init_active_channel(mode) -> Channel  # ACTIVE→command-center, FREE→lounge
set_active_channel(ch: Channel) -> None
update_task(content: str|None, channel: "creation"|"development"|None) -> None
```

---

## 4) ストア（store.py）

### 保存

* セッションID：`"discord_unified"`
* レコード：`{agent, channel, timestamp(ISO8601), text}` を**当日分**として時系列追記
* **短縮・要約なし**（常に全文脈を使う）

### 公開I/F

```
read_all() -> list[Record]           # 当日全文
append(agent: Agent, channel: Channel, text: str) -> None
reset() -> None                      # 日報後に全削除
```

---

## 5) Discord送信（discord.py）

### 公開I/F

```
typing(bot: "spectra"|"lynq"|"paz", channel_id: str) -> None
send(bot: "spectra"|"lynq"|"paz", channel_id: str, text: str) -> MessageId
```

* **Typingは選定Bot名義**で送信直前に必ず1回
* 返信は**受信チャンネル**、自発は**active\_channel**へ
* Slashの**決定通知はSpectra名義**で `command-center` に1本だけ

---

## 6) Supervisor（supervisor.py）

### 役割

* **prompt()**：人格・上限・出力形式（JSONのみ）を含むシステムプロンプトを組み立て
* **generate()**：LLMを**1イベント=1回**呼び出し、`{"speaker","text"}` を返す

  * `kind`：`"reply" | "auto" | "report"`
  * `report`時は **speaker=Spectra 固定／500字以内**（プロンプトで明示）
  * **途中で切らずに上限に収める**指示（最終ハードカット実装なし）

### 公開I/F

```
generate(
  kind: "reply"|"auto"|"report",
  channel: Channel,
  task: Task|None,
  context_text: str,      # Redis全文脈（当日）
  limits: {cc:int, cr:int, dev:int, lo:int}
) -> {"speaker": "spectra"|"lynq"|"paz", "text": str}
```

---

## 7) ログ（logger.py）

* **JSONL 1ファイル**に**システム＋会話**を一元管理
* **Fail-Fast**：例外検知で即 `result="error"` 記録、処理中断、フォールバック禁止

### 行スキーマ

```
{
  ts: ISO8601,
  event_type: "slash"|"user_msg"|"auto_tick"|"report",
  channel: "command-center"|"creation"|"development"|"lounge",
  actor: "user"|"spectra"|"lynq"|"paz"|"system",
  payload_summary: str,                 # 先頭80字など
  result: "ok"|"error",
  error_stage?: "settings"|"slash"|"plan"|"typing"|"send"|"report"|"memory",
  error_detail?: str
}
```

### 公開I/F

```
log_ok(event_type, channel, actor, payload_summary) -> None
log_err(event_type, channel, actor, payload_summary, error_stage, error_detail) -> None
```

---

## 8) アプリ本体（app.py）

### 優先度

`Slash → User → AutoTick`（すべて**直列**）。06:00 は専用ハンドラ。

### 受信エントリ

```
on_slash(channel?: "creation"|"development", content?: str) -> None
on_user(channel: Channel, text: str, user_id: str) -> None
on_tick() -> None                         # ENVに応じて確率判定して実行
on_report_0600() -> None
```

### シーケンス

#### Slash `/task commit <channel> "<内容>"`

1. state.update\_task(content, channel)
2. state.set\_active\_channel(channel)                 # 即移動（唯一のアクティブ）
3. discord.typing("spectra", CHAN\_COMMAND\_CENTER)
4. discord.send("spectra", CHAN\_COMMAND\_CENTER, 「決定通知（短文）」)
5. store.append("user", 受信ch, 生コマンド) / store.append("spectra","command-center", 通知)
6. logger.log\_ok(...)

#### User（即応答）

1. ctx = store.read\_all()
2. out = supervisor.generate(kind="reply", channel=受信ch, task=state.task, context\_text=ctx, limits=…)
3. discord.typing(out.speaker, 受信ch)
4. discord.send(out.speaker, 受信ch, out.text)
5. store.append("user", 受信ch, ユーザー発言); store.append(out.speaker, 受信ch, out.text)
6. logger.log\_ok(...)

#### Auto（tick命中時のみ）

1. ch = state.active\_channel
2. ctx = store.read\_all()
3. out = supervisor.generate(kind="auto", channel=ch, task=state.task, context\_text=ctx, limits=…)
4. discord.typing(out.speaker, ch)
5. discord.send(out.speaker, ch, out.text)
6. store.append(out.speaker, ch, out.text)
7. logger.log\_ok(...)

#### Report 06:00

1. ctx = store.read\_all()
2. out = supervisor.generate(kind="report", channel="command-center", task=state.task, context\_text=ctx, limits=…)
3. discord.typing("spectra", CHAN\_COMMAND\_CENTER)
4. discord.send("spectra", CHAN\_COMMAND\_CENTER, out.text)   # 500字以内
5. store.reset()                                            # 当日分クリア
6. state.mode = "ACTIVE"; state.set\_active\_channel("command-center")
7. logger.log\_ok(...)

> **Fail-Fast**：各段で例外発生→logger.log\_err(…error\_stage=…)→処理中断→次イベントへ。
> 再試行・代替生成・フォールバックは行わない。

---

## 9) スケジューラ（app.py 内）

* **dev**：`every 15s`、命中確率 `1.0`、最大5分で停止
* **prod**：`every 300s`、命中確率 `0.33`
* 06:00（JST）に `on_report_0600()` を1回実行
* `mode_from_time(now)` で `state.mode` を随時更新

  * ACTIVEで `active_channel=command-center`（Slashで上書き可）
  * FREEで `active_channel=lounge`

---

## 10) セキュリティ／運用

* Secretsは `.env` にのみ配置、リポジトリ外部に置く
* Bot権限は対象4チャンネルの最小権限
* 起動時チェック：`settings`→`Redis`→`Discord` の順で **Fail-Fast**

  * 失敗時 `error_stage="settings"` 等でログ

---

## 11) 非採用事項（明示）

* フォールバック／再試行／自動要約／短縮
* 比率制御／監視／クールダウン
* DM／編集／Webhook
* 日次上限制御・トークンバケット・複雑な並列／イベントバス

---

## 12) 受け入れ条件（E2E）

* Slashで `active_channel` が即切替され、**command-center にSpectra名義の決定通知1本**が出る
* User発言に **Typing即（選定Bot）→ 数秒で応答** が返る（受信chにそのまま）
* dev：15s/100%（≤5分）で自発が複数回、prod：5min/33% で自発が出る
* 06:00：**Spectra・500字以内**の日報→**Redis reset**→ `mode=ACTIVE / active_channel=command-center`
* すべてのイベントが **logs/run.log**（JSONL）に `result` と `error_stage`（エラー時）が残る

---
