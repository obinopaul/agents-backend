# Agentic AI System - Complete Reference

This document provides comprehensive documentation for the LangGraph-based multi-agent orchestration system.

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         LangGraph State Machine                             │
│                        (Directed Acyclic Graph)                             │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│     ┌─────────┐      ┌─────────────┐      ┌────────────┐                   │
│     │  START  │ ───► │ Coordinator │ ───► │ Background │                   │
│     └─────────┘      │             │      │Investigator│                   │
│                      └─────────────┘      └────────────┘                   │
│                                                  │                          │
│                                                  ▼                          │
│                                          ┌────────────┐                    │
│                                          │  Planner   │◄──────┐            │
│                                          └────────────┘       │            │
│                                                  │            │            │
│                                                  ▼            │            │
│                                         ┌─────────────┐       │            │
│                                         │Research Team│───────┘            │
│                                         └─────────────┘                    │
│                            ┌─────────────────┼─────────────────┐           │
│                            ▼                 ▼                 ▼           │
│                     ┌──────────┐      ┌──────────┐      ┌──────────┐      │
│                     │Researcher│      │ Analyst  │      │  Coder   │      │
│                     └──────────┘      └──────────┘      └──────────┘      │
│                                              │                             │
│                                              ▼                             │
│                                       ┌──────────┐                        │
│                                       │ Reporter │ ───► END               │
│                                       └──────────┘                        │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Graph Components

| Component | Description | Size | Code Path |
|-----------|-------------|------|-----------|
| **Graph Builder** | Constructs the agent workflow DAG | 2.7KB | [`backend/src/graph/builder.py`](../../backend/src/graph/builder.py) |
| **Node Definitions** | All agent nodes (research, code, content, tools) | **56.8KB** | [`backend/src/graph/nodes.py`](../../backend/src/graph/nodes.py) |
| **Checkpointing** | State persistence for long-running workflows | 15.5KB | [`backend/src/graph/checkpoint.py`](../../backend/src/graph/checkpoint.py) |
| **Type Definitions** | State schemas and message types | 1.3KB | [`backend/src/graph/types.py`](../../backend/src/graph/types.py) |
| **Graph Utilities** | Helper functions for graph operations | 3.6KB | [`backend/src/graph/utils.py`](../../backend/src/graph/utils.py) |

---

## Agent Nodes

### Coordinator Node
- **Purpose**: Entry point, language detection, clarification handling
- **Inputs**: User message, locale
- **Outputs**: Detected language, clarification questions (if enabled)

### Background Investigator Node
- **Purpose**: Initial web search for context before planning
- **Inputs**: Research topic
- **Outputs**: Background context, relevant sources

### Planner Node
- **Purpose**: Creates multi-step research plans
- **Inputs**: Research topic, background context
- **Outputs**: Structured plan with steps (research, analysis, code)

### Research Team Node
- **Purpose**: Routes to appropriate worker nodes
- **Routes to**: Researcher, Analyst, or Coder based on step type

### Researcher Node
- **Purpose**: Web search and data gathering
- **Tools**: Tavily search, web scraping
- **Outputs**: Research findings, sources

### Analyst Node
- **Purpose**: Data analysis and synthesis
- **Inputs**: Research findings
- **Outputs**: Analyzed insights

### Coder Node
- **Purpose**: Code execution in sandbox
- **Tools**: Sandbox shell, file operations
- **Outputs**: Code results, visualizations

### Reporter Node
- **Purpose**: Generates final comprehensive report
- **Inputs**: All research, analysis, and code results
- **Outputs**: Markdown report

---

## Agent Modules

| Agent | Purpose | Key Capabilities | Code Path |
|-------|---------|------------------|-----------|
| **Research Agent** | Information gathering | Web search, RAG retrieval, synthesis | [`backend/src/agents/`](../../backend/src/agents/) |
| **Code Agent** | Code writing & execution | Python, Bash, sandbox integration | [`backend/src/agents/`](../../backend/src/agents/) |
| **Content Agent** | Content generation | Podcasts, PPT, prose | [`backend/src/agents/`](../../backend/src/agents/) |
| **Crawler Agent** | Web scraping | BeautifulSoup, Firecrawl, Jina | [`backend/src/crawler/`](../../backend/src/crawler/) |
| **Prompt Enhancer** | Prompt improvement | Expand, clarify, optimize prompts | [`backend/src/module/prompt_enhancer/`](../../backend/src/module/prompt_enhancer/) |

---

## Content Generators

| Module | Output Format | Description | Code Path |
|--------|---------------|-------------|-----------|
| **Podcast** | Audio (MP3) | Multi-voice dialogue from content | [`backend/src/module/podcast/`](../../backend/src/module/podcast/) |
| **PPT Generator** | PowerPoint (.pptx) | AI-generated presentations | [`backend/src/module/ppt/`](../../backend/src/module/ppt/) |
| **Prose Generator** | Long-form text | Continue, improve, shorten, fix | [`backend/src/module/prose/`](../../backend/src/module/prose/) |
| **Prompt Enhancer** | Enhanced prompt | Optimize prompts for better results | [`backend/src/module/prompt_enhancer/`](../../backend/src/module/prompt_enhancer/) |

### Usage Examples

```python
# Prose Module
from backend.src.module.prose import run_prose_workflow_sync
result = run_prose_workflow_sync("AI is transforming.", "continue")
print(result["output"])

# Prompt Enhancer
from backend.src.module.prompt_enhancer import run_prompt_enhancer_workflow_sync
result = run_prompt_enhancer_workflow_sync("Write about AI", "For beginners", "en-US")
print(result["output"])
```

---

## RAG Pipeline

Production-grade Retrieval-Augmented Generation with support for **6 vector databases**.

| Vector Store | Type | Features | Code Path |
|--------------|------|----------|-----------|
| **Milvus** | Self-hosted / Zilliz Cloud | High-performance, scalable | [`backend/src/rag/milvus.py`](../../backend/src/rag/milvus.py) |
| **Qdrant** | Self-hosted / Cloud | Fast, efficient | [`backend/src/rag/qdrant.py`](../../backend/src/rag/qdrant.py) |
| **Dify** | Managed platform | Easy integration | [`backend/src/rag/dify.py`](../../backend/src/rag/dify.py) |
| **RagFlow** | Open-source | Document processing | [`backend/src/rag/ragflow.py`](../../backend/src/rag/ragflow.py) |
| **VikingDB** | ByteDance | Enterprise-grade | [`backend/src/rag/vikingdb_knowledge_base.py`](../../backend/src/rag/vikingdb_knowledge_base.py) |
| **Moi** | Custom | Flexible implementation | [`backend/src/rag/moi.py`](../../backend/src/rag/moi.py) |

---

## LLM Providers

| Provider | Models | Use Cases | Code Path |
|----------|--------|-----------|-----------|
| **OpenAI** | GPT-4o, GPT-4o-mini, o1, o3-mini | General chat, code, reasoning | [`backend/src/llms/llm.py`](../../backend/src/llms/llm.py) |
| **Anthropic** | Claude 3.5 Sonnet, Claude 3 Opus | Long-context, analysis | [`backend/src/llms/llm.py`](../../backend/src/llms/llm.py) |
| **Google** | Gemini 2.0, Gemini 1.5 Pro | Multimodal, long-context | [`backend/src/llms/llm.py`](../../backend/src/llms/llm.py) |
| **Ollama** | Llama 3, Mistral, etc. | Local/self-hosted | [`backend/src/llms/llm.py`](../../backend/src/llms/llm.py) |
| **OpenAI-Compatible** | Any OpenAI API compatible | Custom endpoints | [`backend/src/llms/llm.py`](../../backend/src/llms/llm.py) |

### Configuration

```python
# Environment variables
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...

# Or via LiteLLM proxy
OPENAI_BASE_URL=http://localhost:4000
```

---

## Checkpointing System

Two checkpointing systems for different purposes:

### 1. LangGraph Checkpointer
- **Purpose**: Save graph state for resumable conversations
- **Storage**: PostgreSQL or MongoDB
- **Config**: `LANGGRAPH_CHECKPOINT_ENABLED=true`

### 2. ChatStreamManager
- **Purpose**: Save all streaming messages for audit/history
- **Storage**: PostgreSQL or MongoDB
- **Config**: `LANGGRAPH_CHECKPOINT_SAVER=true`

```python
# Checkpoint configuration
LANGGRAPH_CHECKPOINT_ENABLED=true
LANGGRAPH_CHECKPOINT_SAVER=true
LANGGRAPH_CHECKPOINT_DB_URL=postgresql://user:pass@localhost/db
```

---

## Workflow Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_plan_iterations` | 1 | How many times planner can revise |
| `max_step_num` | 3 | Maximum steps per plan |
| `max_search_results` | 3 | Results per web search |
| `enable_background_investigation` | true | Web search before planning |
| `enable_clarification` | false | Multi-turn Q&A mode |
| `max_clarification_rounds` | 3 | Max clarification questions |
| `locale` | "en-US" | Language/locale |

---

## Related Documentation

- [FastAPI Backend](fastapi-backend.md) - API endpoints
- [PTC Module](ptc-module.md) - Programmatic Tool Calling
- [Sandbox Guide](sandbox-guide.md) - Execution environments
- [Main README](../../README.md) - Project overview
