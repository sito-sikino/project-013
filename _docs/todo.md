```markdown
# Phase 2 PLAN — todo.md（最小準備を含むマイクロタスク＋受け入れ条件）

> 準拠: spec.md / architecture.md / CLAUDE.md  
> 方針: 直列実行・Fail-Fast・1イベント=LLM1回・Typingは選定Bot名義・Redisは当日全文脈  
> 目的: 過剰な下準備は省きつつ「必要十分」だけを最初に用意する

---

## 0. 初期準備（必要十分のみ）

- [x] 0-1 ディレクトリ作成  
  **AC**: 下記が存在する  
```

app/{app.py,settings.py,state.py,store.py,discord.py,supervisor.py,logger.py}
_docs/{spec.md,architecture.md,CLAUDE.md,todo.md,dev-log/}
logs/run.log（空で可）
.env.template

```
- [x] 0-2 venv 構築＆依存最小インストール  
**AC**: venv 有効化後、`pip list` に以下が入っている  
`httpx, redis, python-dotenv, orjson(または ujson), discord.py, pytest`

---

## 1. 設定と環境（settings.py / .env）

- [x] 1-1 `.env.template` 作成  
**AC**: すべてのキーを含む（ダミー値可）  
`ENV, TZ, SPECTRA_TOKEN, LYNQ_TOKEN, PAZ_TOKEN, CHAN_COMMAND_CENTER, CHAN_CREATION, CHAN_DEVELOPMENT, CHAN_LOUNGE, REDIS_URL, GEMINI_API_KEY, TICK_INTERVAL_SEC_DEV, TICK_PROB_DEV, MAX_TEST_MINUTES, TICK_INTERVAL_SEC_PROD, TICK_PROB_PROD, STANDBY_START, PROCESSING_AT, FREE_START, LIMIT_CC, LIMIT_CR, LIMIT_DEV, LIMIT_LO, LOG_FILE`
- [x] 1-2 `settings.py` 実装（Fail-Fast）  
**AC**: `.env` 読込・型変換・必須キー検証（欠落/不正値で例外→プロセス終了）。欠落テストで確実に落ちる。

---

## 2. ログ（logger.py／JSONL一元）

- [x] 2-1 JSONLロガー  
**AC**: `log_ok(event_type,channel,actor,payload_summary)` / `log_err(...,error_stage,error_detail)` を提供。  
行スキーマ固定：`ts,event_type,channel,actor,payload_summary,result,error_stage,error_detail` を `logs/run.log` に追記。ファイルが無ければ自動作成。
- [x] 2-2 スナップショットテスト  
**AC**: ok/err を各2行出力し、フォーマット一致。

---

## 3. ストア（store.py／Redis全文脈）

- [x] 3-1 接続疎通  
**AC**: `REDIS_URL` で `PING` 成功。
- [x] 3-2 API: `read_all / append / reset`  
**AC**: セッションID `"discord_unified"`、レコード `{agent,channel,timestamp(ISO8601),text}`。  
追記→読込→リセットの往復テストが通る。

---

## 4. ステート（state.py）

- [x] 4-1 型と構造  
**AC**: 列挙 `Mode(STANDBY|PROCESSING|ACTIVE|FREE), Channel, Agent` と `State{mode,active_channel,task{content,channel}}` を定義。
- [x] 4-2 ユーティリティ  
**AC**:  
`mode_from_time(now_jst) -> Mode`、  
`init_active_channel(mode) -> Channel`（ACTIVE→command-center / FREE→lounge）、  
`set_active_channel(ch)`、`update_task(content?, channel?)`。

---

## 5. Discord（受信と送信の最小実装）

- [x] 5-1 受信（Spectraのみ／discord.py）  
**AC**: メッセージ受信イベントと `/task commit` スラッシュを受け取り、app.py の `on_user` / `on_slash` を呼べる。ローカルで1回動作確認。
- [x] 5-2 送信（REST）  
**AC**: `discord.py` の送信は使わず、`httpx` で REST `typing/send` を実装（`discord.py` は受信専用）。  
`typing(bot, channel_id)` が2xx、`send(bot, channel_id, text)->message_id` が2xx。

---

## 6. Supervisor（supervisor.py）

- [x] 6-1 プロンプト  
**AC**: 入力 `{kind,channel,task,context,limits,persona,report_config}`、  
出力は厳密JSON `{"speaker":"spectra|lynq|paz","text":"..."}`（パース失敗→例外）。  
チャンネル上限（cc=100/cr=200/dev=200/lo=30）を **途中で切らず** 守る指示を含む。
- [x] 6-2 生成 `generate(...)`  
**AC**: kind=`reply|auto|report` で **LLM1回**・タイムアウト設定・リトライ無し。reportは `speaker="spectra"`・500字以内。モックで3種が所定JSONを返す。

---

## 7. イベントハンドラ骨格（app.py）

- [x] 7-1 受信口定義（Spectraのみ）  
**AC**: `on_slash(channel?,content?)`, `on_user(channel,text,user_id)`, `on_tick()`, `on_report_0600()` を用意。優先度は **Slash→User→Tick**（直列）。
- [x] 7-2 共通シーケンス  
**AC**: **Redis全文読み→LLM→Typing→Send→Redis追記→log_ok**。どこかで失敗→ **log_err** ＆中断（Fail-Fast）。

---

## 8. Slash `/task commit`（最優先）

- [x] 8-1 パース/バリデーション  
**AC**: `<channel>` ∈ {creation,development}、`<内容>` は文字列。**少なくとも一方**必須。違反は例外（Fail-Fast）。
- [x] 8-2 状態更新/決定通知  
**AC**: `task` 更新→ `active_channel=<channel>` **即上書き**。  
**command-center** に **Spectra名義で短い決定通知1本**（Typing→Send）。  
Slash入力と通知を Redis に追記。E2Eで State/Redis/Discord/Log が一貫。

---

## 9. ユーザー応答（即応答）

- [x] 9-1 応答フロー  
**AC**: 受信CHへ **選定Bot名義で Typing→Send**。LLMは1回、上限内（途中切断なし）。Redisに user発言+bot応答 を追記。
- [x] 9-2 体感速度  
**AC**: 受信→Typing 呼び出しがイベントハンドラ内で即時。

---

## 10. 自発発言（tick）

- [x] 10-1 スケジューラ  
**AC**: dev=15s/100%（**最大5分**で停止）、prod=300s/33%。外れtickは何もしない。
- [x] 10-2 投稿  
**AC**: `active_channel` に **選定Bot名義**で Typing→Send。LLM1回・Redis追記・log_ok。
- [x] 10-3 優先度  
**AC**: Slash/User が到着していれば tick は後回し（直列で保証）。

---

## 11. 日報（06:00／PROCESSING）

- [x] 11-1 トリガ  
**AC**: JSTで **1日1回 06:00** のみ。起動が6:00後ならスキップ（バックフィル無し）。
- [x] 11-2 生成/リセット  
**AC**: **Spectra固定・500字以内**・**LLM1回**・投稿先=command-center。送信成功後に `store.reset()`、`mode=ACTIVE`、`active_channel=command-center`。

---

## 12. エラーハンドリング（Fail-Fast）

- [x] 12-1 段階タグ  
**AC**: `error_stage ∈ {settings,slash,plan,typing,send,report,memory}`。例外時は `log_err` を必ず書き、中断・フォールバック無し。
- [x] 12-2 人工エラー試験  
**AC**: 各ステージで意図的に例外を起こし、正しい `error_stage` がログに残る。

---

## 13. スケジューラ結線（app.py 内）

- [x] 13-1 モード追従  
**AC**: `mode_from_time(now)` で `state.mode` を随時更新。ACTIVE初期は command-center、FREEは lounge。
- [ ] 13-2 06:00 呼び出し  
**AC**: 稼働中は 06:00 に `on_report_0600()` を1回だけ呼ぶ。

---

## 14. Discord 側準備（最小）

- [ ] 14-1 Bot/権限/Slash  
**AC**: 3Bot招待（4CHへ送信可）、Spectraにメッセージ内容 intent、`/task commit` を登録（channel:enum, content:string）。
- [ ] 14-2 ID採番  
**AC**: 4CHのIDを `.env` に記入し `settings.py` で取得できる。

---

## 15. 受け入れ試験（E2E）

- [ ] 15-1 Slash  
**AC**: 実行直後に `active_channel` 即切替、**command-center に決定通知1本（Spectra名義）**、Redis/Log更新。
- [ ] 15-2 ユーザー応答  
**AC**: Typing（選定Bot）即→数秒で本文。上限内・途中切断なし・Redis追記あり。
- [ ] 15-3 自発（dev/prod）  
**AC**: dev=15s/100%（≤5分で複数回）、prod=5min/33% で投稿。
- [ ] 15-4 日報  
**AC**: 06:00に **Spectra・500字以内**で command-center 投稿→直後に Redis 全リセット。
- [ ] 15-5 ログ一元  
**AC**: すべてのイベントで `result` が入り、エラー時は正しい `error_stage` を含む。

---

## 16. 設定値の棚卸し（最終）

- [ ] 16-1 `.env` / `settings.py` 整合  
**AC**: 0欠落・型不一致なし（時刻 `"HH:MM"`、数値はint/float、URL/Tokenは文字列）。Tick/確率/上限/ログパスが spec と一致。
- [ ] 16-2 実行モード  
**AC**: `ENV=dev|prod` で tick 間隔/確率が切り替わる。
```

この構成なら「必要十分」の準備（ディレクトリ・venv・最小依存）を済ませつつ、実装はそのまま着手できる。READMEやPreflightは後回しで問題ない。
