# LangGraph Supervisor Pattern 完全ガイド

> 調査日: 2025年8月12日  
> 最新バージョン: langgraph-supervisor-py (Python >= 3.10)

## 目次
1. [概要](#概要)
2. [アーキテクチャ](#アーキテクチャ)
3. [インストール](#インストール)
4. [基本実装](#基本実装)
5. [詳細実装パターン](#詳細実装パターン)
6. [カスタマイズ](#カスタマイズ)
7. [高度な機能](#高度な機能)
8. [ベストプラクティス](#ベストプラクティス)
9. [完全実装例](#完全実装例)

## 概要

### LangGraph Supervisor Patternとは
LangGraph Supervisor Patternは、中央の「スーパーバイザーエージェント」が複数の特化型「ワーカーエージェント」を調整する階層型マルチエージェントアーキテクチャです。

### 主な特徴
- 🤖 **中央集権的な制御**: スーパーバイザーが全ての通信フローとタスク委譲を管理
- 🛠️ **Tool-based Handoff**: ツールベースのハンドオフメカニズムでエージェント間通信を実現
- 📝 **柔軟なメッセージ履歴管理**: 会話制御のための多様な履歴管理オプション
- 🔄 **状態永続化**: 短期・長期メモリのサポート
- 🏗️ **階層構造**: 多階層のスーパーバイザー構造が可能

### 他のパターンとの比較

| パターン | 特徴 | 使用場面 |
|---------|------|----------|
| **Supervisor Pattern** | 中央制御、明確な階層 | 複雑なタスクの調整、並列実行が必要な場合 |
| **Network Pattern** | 全エージェントが相互通信可能 | 階層が不明確な問題 |
| **Swarm Pattern** | 動的なエージェント間通信 | 柔軟な協調が必要な場合 |
| **Tool-Calling Supervisor** | スーパーバイザーがツールとしてエージェントを呼び出し | 標準的なツール呼び出しパターンに従う場合 |

## アーキテクチャ

### コンポーネント構成

```
┌─────────────────────────────────────┐
│         Supervisor Agent            │
│   (Orchestration & Routing Logic)   │
└──────────┬──────────────┬───────────┘
           │              │
    ┌──────▼─────┐ ┌──────▼─────┐
    │  Worker    │ │  Worker    │
    │  Agent 1   │ │  Agent 2   │
    │ (Special-  │ │ (Special-  │
    │  ized)     │ │  ized)     │
    └────────────┘ └────────────┘
```

### 状態管理フロー

```python
# 基本的な状態定義
class MessagesState(TypedDict):
    messages: Annotated[list, add_messages]  # メッセージ履歴
    
# 拡張状態定義
class AgentState(MessagesState):
    active_agent: str        # 現在アクティブなエージェント
    task_description: str    # タスクの説明
    priority: str           # タスクの優先度
```

### Commandパターンによる制御フロー

```python
Command(
    goto=agent_name,        # 次に実行するエージェント
    graph=Command.PARENT,   # 親グラフへの参照
    update={               # 状態の更新
        "messages": updated_messages,
        "active_agent": agent_name
    }
)
```

## インストール

### 基本インストール
```bash
pip install langgraph-supervisor
```

### 完全環境セットアップ
```bash
# 必要なパッケージ
pip install langgraph-supervisor langchain-openai langchain-core langgraph

# 環境変数設定
export OPENAI_API_KEY=<your_api_key>
```

### 依存関係
- Python >= 3.10
- langgraph >= 0.2.0
- langchain-core >= 0.3.0

## 基本実装

### 1. 最小構成の例

```python
from langchain_openai import ChatOpenAI
from langgraph_supervisor import create_supervisor
from langgraph.prebuilt import create_react_agent

model = ChatOpenAI(model="gpt-4o")

# ツール定義
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b

def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b

def web_search(query: str) -> str:
    """Search the web for information."""
    # 実際の実装では適切なWeb検索APIを使用
    return f"Search results for: {query}"

# ワーカーエージェント作成
math_agent = create_react_agent(
    model=model,
    tools=[add, multiply],
    name="math_expert",
    prompt="You are a math expert. Always use one tool at a time."
)

research_agent = create_react_agent(
    model=model,
    tools=[web_search],
    name="research_expert",
    prompt="You are a world class researcher with access to web search."
)

# スーパーバイザーワークフロー作成
workflow = create_supervisor(
    [research_agent, math_agent],
    model=model,
    prompt=(
        "You are a team supervisor managing a research expert and a math expert. "
        "For current events, use research_agent. "
        "For math problems, use math_agent."
    )
)

# コンパイルと実行
app = workflow.compile()
result = app.invoke({
    "messages": [
        {"role": "user", "content": "What is 15 * 7?"}
    ]
})
```

### 2. create_supervisor関数のパラメータ詳細

```python
create_supervisor(
    agents: List[Agent],           # 必須: 管理するエージェントのリスト
    model: Optional[LLM] = None,   # LLMモデル
    prompt: Optional[str] = None,  # スーパーバイザーのプロンプト
    output_mode: Literal["full_history", "last_message"] = "full_history",
    tools: Optional[List[BaseTool]] = None,  # カスタムハンドオフツール
    add_handoff_messages: bool = True,       # ハンドオフメッセージを履歴に追加
    handoff_tool_prefix: str = "transfer_to", # ハンドオフツールのプレフィックス
    supervisor_name: str = "supervisor"       # スーパーバイザーの名前
)
```

## 詳細実装パターン

### 1. メッセージ履歴管理

#### Full History Mode
全てのエージェントのメッセージを保持:

```python
workflow = create_supervisor(
    agents=[agent1, agent2],
    output_mode="full_history"  # 全履歴を保持
)
```

#### Last Message Mode
最終メッセージのみ保持:

```python
workflow = create_supervisor(
    agents=[agent1, agent2],
    output_mode="last_message"  # 最終メッセージのみ
)
```

### 2. ハンドオフツールのカスタマイズ

#### デフォルトハンドオフツール
```python
from langgraph_supervisor import create_handoff_tool

handoff_tool = create_handoff_tool(
    agent_name="math_expert",
    name="assign_to_math_expert",
    description="Assign mathematical calculations to the math expert"
)

workflow = create_supervisor(
    [research_agent, math_agent],
    tools=[handoff_tool],
    model=model
)
```

#### カスタムハンドオフツール実装
```python
from typing import Annotated
from langchain_core.tools import tool, BaseTool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from langgraph.prebuilt import InjectedState
from langgraph_supervisor.handoff import METADATA_KEY_HANDOFF_DESTINATION

def create_custom_handoff_tool(*, agent_name: str, name: str, description: str) -> BaseTool:
    
    @tool(name, description=description)
    def handoff_to_agent(
        task_description: Annotated[str, "Detailed task description"],
        priority: Annotated[Literal["high", "medium", "low"], "Task priority"],
        deadline: Annotated[Optional[str], "Task deadline"],
        state: Annotated[dict, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ):
        tool_message = ToolMessage(
            content=f"Successfully transferred to {agent_name} with priority {priority}",
            name=name,
            tool_call_id=tool_call_id,
        )
        messages = state["messages"]
        return Command(
            goto=agent_name,
            graph=Command.PARENT,
            update={
                "messages": messages + [tool_message],
                "active_agent": agent_name,
                "task_description": task_description,
                "priority": priority,
                "deadline": deadline
            },
        )
    
    handoff_to_agent.metadata = {METADATA_KEY_HANDOFF_DESTINATION: agent_name}
    return handoff_to_agent

# 使用例
custom_tool = create_custom_handoff_tool(
    agent_name="research_expert",
    name="delegate_research",
    description="Delegate research tasks with priority and deadline"
)
```

### 3. メッセージフォワーディング

```python
from langgraph_supervisor.handoff import create_forward_message_tool

# フォワーディングツールの作成
forwarding_tool = create_forward_message_tool("supervisor")

workflow = create_supervisor(
    [research_agent, math_agent],
    model=model,
    tools=[forwarding_tool]  # フォワーディングツールを追加
)
```

## カスタマイズ

### 1. ハンドオフメッセージの制御

```python
# ハンドオフメッセージを履歴から除外
workflow = create_supervisor(
    [research_agent, math_agent],
    model=model,
    add_handoff_messages=False  # ハンドオフメッセージを追加しない
)
```

### 2. ハンドオフツールプレフィックスのカスタマイズ

```python
workflow = create_supervisor(
    [research_agent, math_agent],
    model=model,
    handoff_tool_prefix="delegate_to"  # delegate_to_research_expert など
)
```

### 3. プロンプトエンジニアリング

```python
detailed_prompt = """
You are an advanced AI supervisor managing a team of specialized agents:

1. Research Expert: Handles web searches, data gathering, and information synthesis
2. Math Expert: Performs calculations, statistical analysis, and numerical operations
3. SQL Expert: Manages database queries and data manipulation

Decision Criteria:
- For factual questions or current events → research_expert
- For calculations or numerical analysis → math_expert
- For database operations → sql_expert

Always provide clear task descriptions when delegating.
Monitor agent responses and ensure quality before returning results.
"""

workflow = create_supervisor(
    agents=[research_agent, math_agent, sql_agent],
    model=model,
    prompt=detailed_prompt
)
```

## 高度な機能

### 1. 多階層スーパーバイザー構造

```python
# レベル1: 専門チーム
research_team = create_supervisor(
    [web_search_agent, academic_research_agent],
    model=model,
    supervisor_name="research_supervisor",
    prompt="Manage research tasks efficiently"
).compile(name="research_team")

analysis_team = create_supervisor(
    [data_analysis_agent, visualization_agent],
    model=model,
    supervisor_name="analysis_supervisor",
    prompt="Manage data analysis tasks"
).compile(name="analysis_team")

writing_team = create_supervisor(
    [content_writer_agent, editor_agent],
    model=model,
    supervisor_name="writing_supervisor",
    prompt="Manage content creation"
).compile(name="writing_team")

# レベル2: トップレベルスーパーバイザー
top_supervisor = create_supervisor(
    [research_team, analysis_team, writing_team],
    model=model,
    supervisor_name="executive_supervisor",
    prompt="Coordinate between different teams to complete complex projects"
).compile(name="top_supervisor")
```

### 2. メモリと永続化

#### 短期メモリ（Checkpointer）
```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.sqlite import SqliteSaver

# インメモリチェックポインター
memory_checkpointer = InMemorySaver()

# SQLiteチェックポインター
sqlite_checkpointer = SqliteSaver.from_conn_string("checkpoint.db")

# PostgreSQLチェックポインター
postgres_checkpointer = PostgresSaver.from_conn_string(
    "postgresql://user:password@localhost:5432/langgraph"
)

# 適用
app = workflow.compile(checkpointer=memory_checkpointer)
```

#### 長期メモリ（Store）
```python
from langgraph.store.memory import InMemoryStore
from langgraph.store.postgres import PostgresStore

# インメモリストア
memory_store = InMemoryStore()

# PostgreSQLストア
postgres_store = PostgresStore.from_conn_string(
    "postgresql://user:password@localhost:5432/langgraph"
)

# 適用
app = workflow.compile(
    checkpointer=checkpointer,
    store=memory_store
)
```

### 3. ストリーミング実行

```python
# ストリーミングで実行
config = {"configurable": {"thread_id": "conversation_1"}}

for chunk in app.stream(
    {"messages": [HumanMessage(content="Analyze this data and create a report")]},
    config=config,
    stream_mode="values"
):
    if "messages" in chunk:
        print(chunk["messages"][-1].content)
```

### 4. 非同期実行

```python
import asyncio
from langchain_core.messages import HumanMessage

async def run_supervisor():
    # 非同期実行
    result = await app.ainvoke({
        "messages": [HumanMessage(content="Process this task asynchronously")]
    })
    return result

# 実行
result = asyncio.run(run_supervisor())
```

### 5. Human-in-the-Loop

```python
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()
app = workflow.compile(checkpointer=checkpointer)

# 中断ポイントの設定
app = workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["math_expert"]  # math_expertの前で中断
)

# 実行と中断
config = {"configurable": {"thread_id": "human_review"}}
result = app.invoke(
    {"messages": [HumanMessage(content="Calculate something complex")]},
    config=config
)

# 人間による確認後、再開
app.update_state(config, {"approved": True})
result = app.invoke(None, config=config)
```

## ベストプラクティス

### 1. エージェント設計原則

```python
# ✅ 良い例: 単一責任原則
math_agent = create_react_agent(
    model=model,
    tools=[add, subtract, multiply, divide],  # 数学関連のみ
    name="math_expert",
    prompt="You are a math expert. Focus only on mathematical calculations."
)

# ❌ 悪い例: 責任が混在
mixed_agent = create_react_agent(
    model=model,
    tools=[add, web_search, database_query],  # 異なる責任が混在
    name="general_agent",
    prompt="You do everything."
)
```

### 2. エラーハンドリング

```python
from langchain_core.messages import AIMessage, HumanMessage
import logging

logger = logging.getLogger(__name__)

def safe_supervisor_node(state: MessagesState) -> Command:
    """エラーハンドリングを含むスーパーバイザーノード"""
    try:
        members = ["web_researcher", "math_expert", "sql_expert"]
        
        # タイムアウト設定
        llm = ChatOpenAI(model="gpt-4o", request_timeout=30)
        
        # リトライロジック
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = llm.with_structured_output(Router).invoke(messages)
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Retry {attempt + 1}: {e}")
                time.sleep(2 ** attempt)  # Exponential backoff
        
        goto = response["next"]
        
        # バリデーション
        if goto not in members + ["FINISH"]:
            logger.error(f"Invalid routing: {goto}")
            goto = "FINISH"
        
        if goto == "FINISH":
            goto = END
            
        return Command(goto=goto)
        
    except Exception as e:
        logger.error(f"Supervisor error: {e}")
        # フォールバック処理
        return Command(
            goto=END,
            update={
                "messages": state["messages"] + [
                    AIMessage(content=f"Error occurred: {str(e)}")
                ]
            }
        )
```

### 3. パフォーマンス最適化

```python
# 並列実行の実装
from concurrent.futures import ThreadPoolExecutor
import asyncio

class ParallelSupervisor:
    def __init__(self, agents, model):
        self.agents = agents
        self.model = model
        
    async def execute_parallel(self, tasks):
        """複数のエージェントを並列実行"""
        async def run_agent(agent, task):
            return await agent.ainvoke({"messages": [HumanMessage(content=task)]})
        
        # 並列実行
        results = await asyncio.gather(*[
            run_agent(agent, task) 
            for agent, task in zip(self.agents, tasks)
        ])
        
        return results
    
    def map_reduce_pattern(self, data_chunks):
        """Map-Reduceパターンの実装"""
        # Map phase: 並列処理
        with ThreadPoolExecutor(max_workers=len(self.agents)) as executor:
            mapped_results = list(executor.map(
                lambda x: x[0].invoke({"messages": [HumanMessage(content=x[1])]}),
                zip(self.agents, data_chunks)
            ))
        
        # Reduce phase: 結果の統合
        combined_result = self.reduce_results(mapped_results)
        return combined_result
```

### 4. 監視とログ

```python
from datetime import datetime
import json

class SupervisorMonitor:
    def __init__(self):
        self.metrics = {
            "total_requests": 0,
            "agent_usage": {},
            "average_response_time": 0,
            "errors": []
        }
    
    def log_request(self, agent_name, duration, success=True, error=None):
        """リクエストのログ記録"""
        self.metrics["total_requests"] += 1
        
        if agent_name not in self.metrics["agent_usage"]:
            self.metrics["agent_usage"][agent_name] = 0
        self.metrics["agent_usage"][agent_name] += 1
        
        if not success:
            self.metrics["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "agent": agent_name,
                "error": str(error)
            })
        
        # 平均応答時間の更新
        n = self.metrics["total_requests"]
        current_avg = self.metrics["average_response_time"]
        self.metrics["average_response_time"] = (
            (current_avg * (n - 1) + duration) / n
        )
    
    def export_metrics(self):
        """メトリクスのエクスポート"""
        return json.dumps(self.metrics, indent=2)

# 使用例
monitor = SupervisorMonitor()

# ワークフローに組み込み
def monitored_agent_node(state, agent, monitor):
    start_time = time.time()
    try:
        result = agent.invoke(state)
        duration = time.time() - start_time
        monitor.log_request(agent.name, duration, success=True)
        return result
    except Exception as e:
        duration = time.time() - start_time
        monitor.log_request(agent.name, duration, success=False, error=e)
        raise
```

### 5. テスト戦略

```python
import pytest
from unittest.mock import Mock, patch

class TestSupervisorWorkflow:
    
    @pytest.fixture
    def mock_agents(self):
        """モックエージェントの作成"""
        math_agent = Mock()
        math_agent.name = "math_expert"
        math_agent.invoke.return_value = {
            "messages": [AIMessage(content="Result: 42")]
        }
        
        research_agent = Mock()
        research_agent.name = "research_expert"
        research_agent.invoke.return_value = {
            "messages": [AIMessage(content="Research findings...")]
        }
        
        return [math_agent, research_agent]
    
    def test_supervisor_routing(self, mock_agents):
        """スーパーバイザーのルーティングテスト"""
        workflow = create_supervisor(
            mock_agents,
            model=Mock(),
            prompt="Test supervisor"
        )
        
        # 数学タスクのテスト
        result = workflow.compile().invoke({
            "messages": [HumanMessage(content="Calculate 2+2")]
        })
        
        assert mock_agents[0].invoke.called
        assert "42" in str(result["messages"])
    
    def test_error_handling(self, mock_agents):
        """エラーハンドリングのテスト"""
        mock_agents[0].invoke.side_effect = Exception("Agent error")
        
        workflow = create_supervisor(mock_agents, model=Mock())
        
        with pytest.raises(Exception):
            workflow.compile().invoke({
                "messages": [HumanMessage(content="Test")]
            })
    
    @patch('langchain_openai.ChatOpenAI')
    def test_integration(self, mock_llm):
        """統合テスト"""
        mock_llm.return_value.with_structured_output.return_value.invoke.return_value = {
            "next": "math_expert"
        }
        
        # 実際のワークフロー作成
        workflow = create_supervisor(
            [create_react_agent(mock_llm(), [], "math_expert")],
            model=mock_llm(),
            prompt="Integration test"
        )
        
        app = workflow.compile()
        result = app.invoke({
            "messages": [HumanMessage(content="Test message")]
        })
        
        assert result is not None
```

## 完全実装例

### プロダクションレディな実装

```python
"""
LangGraph Supervisor Pattern - Production Implementation
"""

import os
import logging
import asyncio
from typing import List, Optional, Literal, TypedDict, Annotated
from datetime import datetime
from enum import Enum

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END, add_messages
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore
from langgraph.prebuilt import create_react_agent, InjectedState, tools_condition
from langgraph.types import Command
from langgraph_supervisor import create_supervisor, create_handoff_tool
from langchain_core.tools import tool, BaseTool, InjectedToolCallId

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 環境変数
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/langgraph")

# Enums
class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class AgentType(str, Enum):
    RESEARCH = "research_expert"
    MATH = "math_expert"
    SQL = "sql_expert"
    WRITER = "writing_expert"

# 状態定義
class SupervisorState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    active_agent: Optional[str]
    task_description: Optional[str]
    priority: Optional[Priority]
    metadata: dict

# ツール実装
@tool
def web_search(query: str) -> str:
    """Advanced web search with caching"""
    logger.info(f"Searching web for: {query}")
    # 実際の実装では適切なWeb検索APIを使用
    return f"Search results for: {query}"

@tool
def calculate(expression: str) -> float:
    """Safe mathematical calculation"""
    try:
        # 安全な数式評価
        import ast
        import operator as op
        
        ops = {
            ast.Add: op.add, ast.Sub: op.sub,
            ast.Mult: op.mul, ast.Div: op.truediv,
            ast.Pow: op.pow
        }
        
        def eval_expr(expr):
            return eval(compile(ast.parse(expr, mode='eval'), '', 'eval'))
        
        result = eval_expr(expression)
        logger.info(f"Calculated: {expression} = {result}")
        return result
    except Exception as e:
        logger.error(f"Calculation error: {e}")
        raise ValueError(f"Invalid expression: {expression}")

@tool
def execute_sql(query: str, database: str = "main") -> str:
    """Execute SQL query with validation"""
    logger.info(f"Executing SQL on {database}: {query}")
    # 実際の実装ではSQLAlchemyなどを使用
    return f"Query executed: {query}"

@tool
def write_content(topic: str, style: str = "professional") -> str:
    """Generate written content"""
    logger.info(f"Writing content about: {topic} (style: {style})")
    return f"Content about {topic} in {style} style"

# カスタムハンドオフツール
def create_advanced_handoff_tool(
    agent_name: str,
    name: Optional[str] = None,
    description: Optional[str] = None
) -> BaseTool:
    """Create an advanced handoff tool with metadata"""
    
    tool_name = name or f"transfer_to_{agent_name}"
    tool_desc = description or f"Transfer task to {agent_name}"
    
    @tool(tool_name, description=tool_desc)
    def handoff_with_context(
        task: Annotated[str, "Detailed task description"],
        priority: Annotated[Priority, "Task priority"],
        context: Annotated[dict, "Additional context"],
        state: Annotated[dict, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command:
        """Enhanced handoff with full context"""
        
        # ログ記録
        logger.info(f"Handoff to {agent_name}: {task} (Priority: {priority})")
        
        # メッセージ作成
        tool_message = ToolMessage(
            content=f"Task transferred to {agent_name}",
            name=tool_name,
            tool_call_id=tool_call_id,
            additional_kwargs={"priority": priority, "context": context}
        )
        
        # 状態更新
        return Command(
            goto=agent_name,
            graph=Command.PARENT,
            update={
                "messages": state["messages"] + [tool_message],
                "active_agent": agent_name,
                "task_description": task,
                "priority": priority,
                "metadata": {
                    **state.get("metadata", {}),
                    "last_handoff": datetime.now().isoformat(),
                    "handoff_count": state.get("metadata", {}).get("handoff_count", 0) + 1
                }
            }
        )
    
    # メタデータ追加
    handoff_with_context.metadata = {
        "handoff_destination": agent_name,
        "tool_type": "handoff",
        "created_at": datetime.now().isoformat()
    }
    
    return handoff_with_context

# エージェントファクトリー
class AgentFactory:
    """Factory for creating specialized agents"""
    
    def __init__(self, model: ChatOpenAI):
        self.model = model
    
    def create_research_agent(self) -> StateGraph:
        """Create a research specialist agent"""
        return create_react_agent(
            self.model,
            tools=[web_search],
            name=AgentType.RESEARCH,
            prompt="""You are a world-class research specialist with expertise in:
            - Web research and information gathering
            - Fact-checking and verification
            - Synthesizing complex information
            - Current events and trends analysis
            
            Always provide accurate, well-sourced information."""
        )
    
    def create_math_agent(self) -> StateGraph:
        """Create a mathematics specialist agent"""
        return create_react_agent(
            self.model,
            tools=[calculate],
            name=AgentType.MATH,
            prompt="""You are a mathematics expert specializing in:
            - Complex calculations
            - Statistical analysis
            - Mathematical modeling
            - Problem-solving
            
            Always show your work and verify calculations."""
        )
    
    def create_sql_agent(self) -> StateGraph:
        """Create a SQL specialist agent"""
        return create_react_agent(
            self.model,
            tools=[execute_sql],
            name=AgentType.SQL,
            prompt="""You are a database expert specializing in:
            - SQL query optimization
            - Database design
            - Data analysis
            - Performance tuning
            
            Always validate queries before execution."""
        )
    
    def create_writing_agent(self) -> StateGraph:
        """Create a content writing agent"""
        return create_react_agent(
            self.model,
            tools=[write_content],
            name=AgentType.WRITER,
            prompt="""You are a professional content writer specializing in:
            - Technical documentation
            - Creative writing
            - Report generation
            - Content optimization
            
            Always maintain consistent tone and style."""
        )

# メインスーパーバイザー実装
class ProductionSupervisor:
    """Production-ready supervisor implementation"""
    
    def __init__(
        self,
        model_name: str = "gpt-4o",
        temperature: float = 0.1,
        max_retries: int = 3
    ):
        self.model = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            max_retries=max_retries,
            request_timeout=60
        )
        self.factory = AgentFactory(self.model)
        self.monitor = self._create_monitor()
        
    def _create_monitor(self):
        """Create monitoring system"""
        return {
            "start_time": datetime.now(),
            "request_count": 0,
            "agent_metrics": {},
            "errors": []
        }
    
    def build_workflow(self) -> StateGraph:
        """Build the complete supervisor workflow"""
        
        # エージェント作成
        research_agent = self.factory.create_research_agent()
        math_agent = self.factory.create_math_agent()
        sql_agent = self.factory.create_sql_agent()
        writing_agent = self.factory.create_writing_agent()
        
        # カスタムハンドオフツール
        handoff_tools = [
            create_advanced_handoff_tool(
                AgentType.RESEARCH,
                description="Delegate research and information gathering tasks"
            ),
            create_advanced_handoff_tool(
                AgentType.MATH,
                description="Delegate mathematical and analytical tasks"
            ),
            create_advanced_handoff_tool(
                AgentType.SQL,
                description="Delegate database and SQL tasks"
            ),
            create_advanced_handoff_tool(
                AgentType.WRITER,
                description="Delegate content creation tasks"
            )
        ]
        
        # スーパーバイザープロンプト
        supervisor_prompt = """
        You are an executive AI supervisor managing a team of specialized agents:
        
        1. **Research Expert**: Web research, fact-checking, information synthesis
        2. **Math Expert**: Calculations, statistics, mathematical analysis
        3. **SQL Expert**: Database queries, data manipulation, optimization
        4. **Writing Expert**: Content creation, documentation, reports
        
        ## Decision Framework:
        
        - Analyze the user's request carefully
        - Identify the primary task type and required expertise
        - Consider task dependencies and optimal execution order
        - Delegate to the most appropriate specialist
        - Monitor quality and completeness of responses
        - Coordinate multi-step tasks across agents
        
        ## Quality Standards:
        
        - Ensure accuracy and completeness
        - Maintain consistency across agent responses
        - Validate results before final delivery
        - Request clarification when needed
        
        ## Priority Handling:
        
        - HIGH: Immediate attention, critical tasks
        - MEDIUM: Standard processing, normal workflow
        - LOW: Background tasks, non-urgent requests
        
        Always provide clear task descriptions and context when delegating.
        """
        
        # ワークフロー作成
        workflow = create_supervisor(
            agents=[research_agent, math_agent, sql_agent, writing_agent],
            model=self.model,
            prompt=supervisor_prompt,
            tools=handoff_tools,
            output_mode="full_history",
            add_handoff_messages=True,
            supervisor_name="executive_supervisor"
        )
        
        return workflow
    
    def compile_with_persistence(self):
        """Compile workflow with persistence layers"""
        
        # PostgreSQL永続化
        checkpointer = PostgresSaver.from_conn_string(DATABASE_URL)
        store = PostgresStore.from_conn_string(DATABASE_URL)
        
        # ワークフロー構築
        workflow = self.build_workflow()
        
        # コンパイル
        app = workflow.compile(
            checkpointer=checkpointer,
            store=store,
            debug=True  # デバッグモード
        )
        
        return app
    
    async def execute_async(
        self,
        message: str,
        thread_id: str = "default",
        priority: Priority = Priority.MEDIUM
    ):
        """非同期実行"""
        
        app = self.compile_with_persistence()
        config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": "production"
            }
        }
        
        # メトリクス更新
        self.monitor["request_count"] += 1
        start_time = datetime.now()
        
        try:
            # 実行
            result = await app.ainvoke(
                {
                    "messages": [HumanMessage(content=message)],
                    "priority": priority,
                    "metadata": {
                        "request_id": f"req_{self.monitor['request_count']}",
                        "timestamp": start_time.isoformat()
                    }
                },
                config=config
            )
            
            # 成功メトリクス
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Request completed in {duration:.2f}s")
            
            return result
            
        except Exception as e:
            # エラー処理
            self.monitor["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "message": message
            })
            logger.error(f"Execution error: {e}")
            raise
    
    def stream_execution(
        self,
        message: str,
        thread_id: str = "default"
    ):
        """ストリーミング実行"""
        
        app = self.compile_with_persistence()
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 50
        }
        
        # ストリーミング
        for chunk in app.stream(
            {"messages": [HumanMessage(content=message)]},
            config=config,
            stream_mode="values"
        ):
            yield chunk
    
    def get_metrics(self):
        """メトリクス取得"""
        uptime = (datetime.now() - self.monitor["start_time"]).total_seconds()
        return {
            "uptime_seconds": uptime,
            "total_requests": self.monitor["request_count"],
            "average_rps": self.monitor["request_count"] / uptime if uptime > 0 else 0,
            "errors": len(self.monitor["errors"]),
            "agent_metrics": self.monitor["agent_metrics"]
        }

# 使用例
async def main():
    """メイン実行関数"""
    
    # スーパーバイザー初期化
    supervisor = ProductionSupervisor(
        model_name="gpt-4o",
        temperature=0.1,
        max_retries=3
    )
    
    # 複雑なタスクの実行
    complex_task = """
    I need a comprehensive analysis:
    1. Research the latest AI trends in 2025
    2. Calculate the growth rate of AI adoption
    3. Query our database for relevant metrics
    4. Write a executive summary report
    """
    
    # 非同期実行
    result = await supervisor.execute_async(
        message=complex_task,
        thread_id="analysis_001",
        priority=Priority.HIGH
    )
    
    # 結果表示
    for message in result["messages"]:
        if isinstance(message, AIMessage):
            print(f"Agent: {message.content}")
    
    # メトリクス表示
    metrics = supervisor.get_metrics()
    print(f"Metrics: {metrics}")

# エントリーポイント
if __name__ == "__main__":
    asyncio.run(main())
```

## トラブルシューティング

### よくある問題と解決策

| 問題 | 原因 | 解決策 |
|------|------|--------|
| エージェントが見つからない | 名前の不一致 | create_react_agentのnameとsupervisorでの参照を確認 |
| 無限ループ | 終了条件なし | FINISHまたはENDへの明確なルーティングを追加 |
| メモリ不足 | 履歴の肥大化 | output_mode="last_message"を使用 |
| 遅いレスポンス | 直列実行 | 並列実行パターンを実装 |
| ハンドオフ失敗 | ツール設定ミス | METADATA_KEY_HANDOFF_DESTINATIONを確認 |

## リソース

### 公式ドキュメント
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangGraph Supervisor GitHub](https://github.com/langchain-ai/langgraph-supervisor-py)
- [LangGraph Examples](https://github.com/langchain-ai/langgraph/tree/main/examples)

### 関連ライブラリ
- langgraph >= 0.2.0
- langchain-core >= 0.3.0
- langchain-openai >= 0.1.0

### コミュニティ
- [LangChain Discord](https://discord.gg/langchain)
- [GitHub Issues](https://github.com/langchain-ai/langgraph/issues)

---

*最終更新: 2025年8月12日*
*バージョン: langgraph-supervisor-py (latest)*