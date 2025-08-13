# 実装ログ: イベントハンドラ受信口定義（7-1）

**実装日時**: 2025-08-13 12:28  
**完了タスク**: 7-1 受信口定義（Spectraのみ）

## 完了タスク全文

- [x] 7-1 受信口定義（Spectraのみ）  
**AC**: `on_slash(channel?,content?)`, `on_user(channel,text,user_id)`, `on_tick()`, `on_report_0600()` を用意。優先度は **Slash→User→Tick**（直列）。

## 実装の背景

CLAUDE.md原則に従ったTDD（Red→Green→Refactor→Commit）サイクルで、app.pyにイベントハンドラの受信口定義を実装。  
Ultra Think & Use Subagentによる要件分析、Serena MCPによる既存コード把握を駆使し、優先度制御システムの基盤を構築した。

## 設計意図

1. **4つのイベントハンドラ定義**: on_slash/on_user/on_tick/on_report_0600の完全実装
2. **優先度制御システム**: Slash→User→Tickの3段階優先度制御基盤
3. **直列処理保証**: 同時並行処理を防ぐPriorityQueue実装
4. **Fail-Fast原則**: 例外時の即座中断・エラー再送出
5. **非同期アーキテクチャ**: asyncio基盤の堅牢なイベント処理システム

## 実装詳細

### Red段階（失敗テスト作成）
- `test_app_handlers.py`: 16テストケース作成
  - イベントハンドラ存在確認（6件）
  - 優先度制御機構確認（4件）
  - ハンドラ動作確認（3件）
  - 統合テスト（3件）

### Green段階（最小実装）
- `on_tick()`: パラメータなし・自発発言処理ハンドラ
- `on_report_0600()`: 日報処理ハンドラ
- 基本EventQueueクラス: 優先度制御の骨格

### Refactor段階（品質改善）
- **優先度制御システム拡張**:
  - `EventPriority(Enum)`: SLASH=1/USER=2/TICK=3の明確な優先度定義
  - `EventItem(@dataclass)`: イベントアイテムの構造化
  - `EventQueue.enqueue()`: 優先度付きキューイング機能
  - `EventQueue.process_events()`: 直列処理・Fail-Fast実装
- **型安全性向上**: typing.Callableによる厳密な型注釈
- **コード品質**: black/flake8準拠、未使用import除去

## イベント優先度制御システム詳細

### 優先度定義
```python
class EventPriority(Enum):
    SLASH = 1  # 最高優先度: スラッシュコマンド
    USER = 2   # 中優先度: ユーザーメッセージ  
    TICK = 3   # 低優先度: 自発発言
```

### キューイング機構
```python
async def enqueue(self, priority: EventPriority, handler: Callable, *args, **kwargs):
    # Fail-Fast: パラメータ検証
    if not callable(handler):
        raise ValueError("Handler must be callable")
        
    item = EventItem(priority, handler, args, kwargs)
    await self._queue.put((priority.value, item))
```

### 直列処理保証
```python
async def process_events(self):
    while True:
        if self._processing:
            await asyncio.sleep(0.01)  # 処理中は短時間待機
            continue
            
        priority_value, item = await self._queue.get()
        self._processing = True
        
        # Fail-Fast: 直列実行で例外時は即中断
        await item.handler(*item.args, **item.kwargs)
        
        self._queue.task_done()
        self._processing = False
```

## イベントハンドラ仕様

### on_slash(channel?, content?)
- **優先度**: 最高（SLASH=1）
- **責務**: スラッシュコマンド処理・タスク更新・状態変更
- **パラメータ**: 少なくとも一方必須（Fail-Fast検証済み）

### on_user(channel, text, user_id)  
- **優先度**: 中（USER=2）
- **責務**: ユーザーメッセージ応答・LLM処理・Discord送信
- **パラメータ**: 全て必須（Fail-Fast検証済み）

### on_tick()
- **優先度**: 低（TICK=3）
- **責務**: 自発発言・active_channelへの投稿
- **パラメータ**: なし

### on_report_0600()
- **優先度**: 特別タイミング
- **責務**: 日報生成・Redis全リセット・ステート更新
- **パラメータ**: なし

## 副作用 / 注意点

1. **処理順序保証**: 高優先度イベントが低優先度を常に先行
2. **直列処理制約**: 複数イベントの同時並行処理は完全に防止
3. **Fail-Fast徹底**: 1つの処理失敗で全体処理が中断
4. **メモリ効率**: PriorityQueueによる効率的なイベント管理
5. **拡張性**: 新しい優先度レベル追加が容易な設計

## 関連ファイル・関数

- `app/app.py`: 
  - `on_tick()`: 自発発言処理ハンドラ
  - `on_report_0600()`: 日報処理ハンドラ
  - `EventPriority`: 優先度定義Enum
  - `EventItem`: イベントアイテム構造
  - `EventQueue`: 優先度制御キュー（直列処理）
  - `event_queue`: グローバルイベントキューインスタンス
- `test_app_handlers.py`: 7-1機能テスト16件

## テスト結果

全16テスト通過:
```
test_app_handlers.py::TestAppEventHandlers::test_on_tick_function_exists PASSED
test_app_handlers.py::TestAppEventHandlers::test_on_report_0600_function_exists PASSED
test_app_handlers.py::TestAppEventPriority::test_event_queue_exists PASSED
test_app_handlers.py::TestAppEventHandlerBehavior::test_on_tick_can_be_called_without_parameters PASSED
test_app_handlers.py::TestAppEventHandlerIntegration::test_all_required_handlers_defined PASSED
[...全16件通過]
```

## コード品質確認

- **black**: フォーマット適用済み
- **flake8**: スタイルガイド準拠確認済み（88文字制限）
- **pytest**: 全16テスト通過確認済み
- **型安全性**: Callable型注釈による厳密な型検査

## Ultra Think & Use Subagent活用

1. **Ultra Think**: 要件の詳細分析と技術的実装方針策定
   - 優先度制御「Slash→User→Tick」の実装アプローチ
   - 「直列」処理の意味と実装戦略
   - Fail-Fast原則の適用方法
2. **Use Subagent**: general-purposeによる総合的要件分析
   - 各ハンドラの責務とシグネチャ設計
   - 優先度制御システムの実装アーキテクチャ
   - Discord統合とapp.pyでの統合方法

## Serena MCP活用

1. **既存コード把握**: app.pyの現在実装状況確認
2. **段階的実装**: 既存関数への影響を最小化した追加実装
3. **効率的編集**: symbol-based editingによる正確な実装

## 次のステップ

7-2 共通シーケンス: Redis全文読み→LLM→Typing→Send→Redis追記→log_okの実装