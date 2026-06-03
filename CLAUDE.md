# 项目上下文 — 供 Claude Code 使用

## 项目概述

**名称**: E-commerce Customer Service Agent（电商客服 Agent）
**类型**: Python + LangChain + MiniMax 的生产级 AI 客服系统
**仓库**: https://github.com/CHu1Zzz/e-commerce-agent
**Python 版本**: 3.12+
**虚拟环境**: `.venv`（项目根目录下）

---

## 技术栈

| 组件 | 选型 |
|------|------|
| LLM | MiniMax（M3/M2.7/Text-01），通过 OpenAI 兼容接口（`base_url=https://api.minimax.chat/v1`） |
| Agent 框架 | LangChain `create_react_agent` + LangGraph MemorySaver |
| 向量数据库 | ChromaDB（本地文件持久化） |
| Web UI | Streamlit |
| 安全 | PII Scrubber + Prompt Injection Detector + Hallucination Detector |
| 可观测性 | LangSmith（可选，需配置 `LANGSMITH_API_KEY`） |

---

## 项目结构

```
ecommerce-cs-agent/
├── .env / .env.example          # 环境变量配置
├── requirements.txt             # Python 依赖
├── PRD.md                       # 产品需求文档
├── CLAUDE.md                    # 本文件
│
├── app/
│   ├── main.py                 # 入口脚本
│   ├── agent/
│   │   ├── agent.py            # Agent 核心（create_agent + chat）
│   │   ├── prompts.py          # System Prompt
│   │   └── tools/
│   │       ├── order_query.py       # query_order Tool
│   │       ├── logistics.py         # track_logistics Tool
│   │       ├── return_request.py    # submit_return_request Tool
│   │       ├── human_handoff.py     # transfer_to_human Tool
│   │       ├── product_kb.py        # product_kb_search（RAG 知识库）
│   │       ├── product_search.py    # product_search Tool（商品搜索）
│   │       ├── size_recommendation.py  # size_recommend Tool（尺码推荐）
│   │       └── product_recommend.py  # product_recommend Tool（商品推荐）
│   ├── data/
│   │   ├── mock_orders.json         # 模拟订单（5 条）
│   │   ├── mock_logistics.json      # 模拟物流（5 条）
│   │   ├── mock_products.json      # 商品目录（20+ 条）
│   │   ├── faq.json                 # FAQ（已迁移至向量库）
│   │   ├── chroma_db/               # 向量库目录（初始化后生成）
│   │   └── return_tickets.json       # 退换货工单（运行时生成）
│   ├── security/
│   │   ├── pii_scrubber.py           # PII 脱敏
│   │   ├── prompt_injection_detector.py  # Injection 检测
│   │   └── hallucination_detector.py # 幻觉检测
│   └── ui/
│       └── streamlit_app.py          # Streamlit Web 界面
│
├── scripts/
│   └── init_vector_db.py             # 向量库初始化脚本
│
└── tests/                            # 测试套件（Phase 2 添加）
```

---

## 依赖安装

```bash
# 创建并激活虚拟环境
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

---

## 环境变量配置

复制 `.env.example` 为 `.env`，填入以下变量：

```env
MINIMAX_API_KEY=your-minimax-api-key
MINIMAX_BASE_URL=https://api.minimax.chat/v1
MINIMAX_MODEL=MiniMax-Text-01
# LANGSMITH_API_KEY=your-langsmith-key  # 可选
```

---

## 启动应用

```bash
# 方式一：直接启动
d:/e-commerce-agent/.venv/Scripts/streamlit.exe run d:/e-commerce-agent/app/ui/streamlit_app.py --server.headless true

# 方式二：通过入口脚本
python app/main.py
```

访问 http://localhost:8501

---

## 测试订单号

| 订单号 | 状态 | 用途 |
|--------|------|------|
| `ORD-20260530-001` | 已发货 | 可查物流 |
| `ORD-20260528-002` | 已签收 | 可办退货 |
| `ORD-20260601-003` | 待发货 | 不可退换 |
| `ORD-20260531-005` | 已发货 | 可查物流 |

---

## 核心 API

### 创建 Agent

```python
from app.agent.agent import create_agent

agent = create_agent(
    api_key="your-minimax-api-key",
    base_url="https://api.minimax.chat/v1",
    model="MiniMax-Text-01",
    enable_checkpointer=True,   # 状态持久化
    enable_langsmith=False,     # LangSmith tracing
)
```

### 对话

```python
from app.agent.agent import chat

reply = chat(agent, "帮我查一下订单 ORD-20260530-001", thread_id="user-123")
```

### 预处理（安全层）

```python
from app.agent.agent import preprocess_input, postprocess_output

safe_input, warning = preprocess_input("我的手机是13812345678")
response = postprocess_output(response, tool_result)
```

### RAG Tool 直接调用

```python
from app.agent.tools.product_kb import product_kb_search

result = product_kb_search.invoke({"query": "T恤可以机洗吗？", "top_k": 3})
```

---

## 安全模块

| 模块 | 文件 | 功能 |
|------|------|------|
| PII Scrubber | `app/security/pii_scrubber.py` | 手机号/银行卡/邮箱/身份证/地址脱敏 |
| Injection Detector | `app/security/prompt_injection_detector.py` | 角色逃逸、指令注入检测 |
| Hallucination Detector | `app/security/hallucination_detector.py` | 订单号/金额一致性校验 |

---

## 重要设计决策

1. **MiniMax 通过 OpenAI 兼容接口**：使用 `langchain-openai` 的 `ChatOpenAI`，`base_url` 指向 `api.minimax.chat/v1`，无需 `langchain-minimax` 包
2. **向量库路径**：`app/data/chroma_db/`（初始化后自动创建），通过 `sys.modules["app"].__file__` 动态定位
3. **状态持久化**：开发环境用 `MemorySaver`（内存），生产环境换 `PostgresSaver`
4. **FAQ 迁移**：FAQ 已从 Prompt 硬编码迁移至 ChromaDB 向量库，Prompt 中仅保留工具调用说明

---

## 完整功能矩阵（生产级电商客服）

| 类别 | 功能 | 工具文件 | 状态 |
|------|------|---------|------|
| **售后** | 订单查询 | `order_query.py` | ✅ 已完成 |
| | 物流追踪 | `logistics.py` | ✅ 已完成 |
| | 退换货申请 | `return_request.py` | ✅ 已完成 |
| | 转人工 | `human_handoff.py` | ✅ 已完成 |
| **售前** | 商品知识库（RAG） | `product_kb.py` | ✅ 已完成 |
| | 商品搜索 | `product_search.py` | ✅ 已完成 |
| | 尺码推荐 | `size_recommendation.py` | ✅ 已完成 |
| | 商品推荐 | `product_recommend.py` | ✅ 已完成 |
| **安全** | PII 脱敏 | `pii_scrubber.py` | ✅ 已完成 |
| | Prompt 注入检测 | `prompt_injection_detector.py` | ✅ 已完成 |
| | 幻觉检测 | `hallucination_detector.py` | ✅ 已完成 |

---

## 后续计划（Phase 2/3）

- LangGraph StateGraph 多 Agent 路由（Supervisor → 专家子 Agent）
- OTEL + Grafana 可观测性
- Playwright E2E 测试套件
- Docker Compose 部署（Agent + ChromaDB + Redis）
- Redis 语义缓存 + 限流

---

## 工作流程（Claude Code 必须遵循）

每次修改代码后，必须执行以下步骤：

### 1. 安全审查
- 检查新增代码是否存在安全漏洞（SQL注入、路径遍历、PII泄露、Prompt注入等）
- 审查所有用户输入的验证和清理
- 确认没有硬编码敏感信息

### 2. 测试验证
- 启动 Streamlit 应用进行功能测试
- 验证新增功能是否正常工作
- 确认已有功能未被破坏

### 3. GitHub 提交
- 完成测试后，将代码 commit 到 GitHub 远程仓库
- 使用清晰的 commit message 描述修改内容
- 格式：`feat: add [功能名称]` 或 `fix: fix [问题描述]`