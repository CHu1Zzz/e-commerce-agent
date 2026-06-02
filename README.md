# 电商客服 Agent — E-commerce Customer Service Agent

> 基于 LangChain + MiniMax 的生产级智能客服系统，支持多 Agent 路由、RAG 商品知识库、全链路安全护栏。

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![LangChain](https://img.shields.io/badge/LangChain-1.3+-red.svg)](https://www.langchain.com/)
[![MiniMax](https://img.shields.io/badge/MiniMax-M3/M2.7-green.svg)](https://platform.minimaxi.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🎯 产品定位

面向电商场景的 AI 客服 Agent，自动处理订单查询、物流追踪、退换货申请、商品知识咨询，**生产级可商用架构**。

## ✨ 核心能力

| 能力 | 说明 |
|------|------|
| 📦 **订单查询** | 通过订单号查询订单状态、商品明细、金额、地址 |
| 🚚 **物流追踪** | 实时物流轨迹时间线 + 预计送达时间 |
| 🔄 **退换货申请** | 完整退换货流程（校验时效/状态 → 生成工单 → 返回地址） |
| 📚 **商品知识库（RAG）** | ChromaDB 向量检索，回答尺码/洗涤/退换货政策等 FAQ |
| 🛡️ **安全护栏** | PII 脱敏 + Prompt Injection 检测 + 幻觉检测 |
| 💾 **状态持久化** | LangGraph MemorySaver，断线重连会话不丢失 |
| 👤 **人工转交** | 低置信度 / 高风险场景自动转人工 |
| 🔍 **可观测性** | LangSmith tracing 支持（可选） |

## 🏗️ 技术架构

```
用户输入
    │
    ▼
┌──────────────────────────────────────────────┐
│              输入安全层                       │
│  ├── PII Scrubber（手机号/银行卡/邮箱脱敏）    │
│  └── Prompt Injection Detector                │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│           LangGraph ReAct Agent              │
│  ├── MemorySaver（状态持久化）               │
│  ├── 5 个 Tool（订单/物流/退换货/知识库/转人工）│
│  └── MiniMax LLM（OpenAI 兼容接口）          │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│           ChromaDB 向量数据库                 │
│  └── 商品知识库（RAG）13 条测试文档           │
└──────────────────────────────────────────────┘
```

## 📁 项目结构

```
ecommerce-cs-agent/
├── .env.example                # 环境变量模板
├── .gitignore                  # Git 忽略配置
├── requirements.txt            # Python 依赖
├── PRD.md                      # 产品需求文档
├── CLAUDE.md                   # Claude Code 项目说明（本文件）
├── README.md                   # 项目说明文档
│
├── app/
│   ├── main.py                 # 入口：启动 Streamlit
│   │
│   ├── agent/
│   │   ├── agent.py            # Agent 核心（LangGraph + MiniMax）
│   │   ├── prompts.py          # System Prompt 模板
│   │   └── tools/
│   │       ├── order_query.py       # 订单查询 Tool
│   │       ├── logistics.py         # 物流追踪 Tool
│   │       ├── return_request.py   # 退换货申请 Tool
│   │       ├── human_handoff.py     # 人工转交 Tool
│   │       └── product_kb.py        # 商品知识库 RAG Tool
│   │
│   ├── data/
│   │   ├── mock_orders.json         # 模拟订单数据（5 条）
│   │   ├── mock_logistics.json      # 模拟物流数据（5 条）
│   │   ├── faq.json                 # FAQ 知识（已迁移至 ChromaDB）
│   │   ├── chroma_db/               # ChromaDB 向量库（初始化后生成）
│   │   └── return_tickets.json     # 退换货工单记录
│   │
│   ├── security/
│   │   ├── pii_scrubber.py          # PII 脱敏
│   │   ├── prompt_injection_detector.py  # Injection 检测
│   │   └── hallucination_detector.py     # 幻觉检测
│   │
│   └── ui/
│       └── streamlit_app.py        # Streamlit Web 界面
│
├── scripts/
│   └── init_vector_db.py             # 向量数据库初始化脚本
│
└── tests/                           # 测试套件（待补充）
```

## 🚀 快速开始

### 前置要求

- Python 3.12+
- MiniMax API Key ([申请地址](https://platform.minimaxi.com/))

### 1. 克隆项目

```bash
git clone https://github.com/CHu1Zzz/e-commerce-agent.git
cd e-commerce-agent
```

### 2. 创建虚拟环境

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

```bash
cp .env.example .env
# 用文本编辑器打开 .env，填入你的 MiniMax API Key
```

```env
# .env 文件内容示例
MINIMAX_API_KEY=your-api-key-here
MINIMAX_BASE_URL=https://api.minimax.chat/v1
MINIMAX_MODEL=MiniMax-Text-01
```

### 5. 初始化向量数据库（首次运行）

在 Streamlit 侧边栏点击 **「📦 初始化知识库」**，或手动运行：

```bash
python scripts/init_vector_db.py
```

### 6. 启动应用

```bash
streamlit run app/ui/streamlit_app.py
```

访问 **http://localhost:8501** 即可使用。

---

## 🧪 测试订单号

| 订单号 | 状态 | 备注 |
|--------|------|------|
| `ORD-20260530-001` | 已发货 | 可查物流 |
| `ORD-20260528-002` | 已签收 | 可办退货 |
| `ORD-20260601-003` | 待发货 | 不可退换 |
| `ORD-20260531-005` | 已发货 | 可查物流 |

---

## 🛡️ 安全功能

| 功能 | 状态 | 说明 |
|------|------|------|
| PII 脱敏 | ✅ 已启用 | 手机号/银行卡/邮箱/身份证/地址自动脱敏 |
| Prompt Injection 检测 | ✅ 已启用 | 拦截角色逃逸、指令注入等攻击模式 |
| 幻觉检测 | ✅ 已启用 | 关键字段（订单号/金额）一致性校验 |
| 状态持久化 | ✅ 已启用 | MemorySaver，断线重连不丢失会话 |

---

## 🔧 配置说明

### 侧边栏配置面板

| 配置项 | 说明 |
|--------|------|
| `MINIMAX_API_KEY` | MiniMax 平台 API Key |
| `API Base URL` | 默认 `https://api.minimax.chat/v1` |
| `模型` | MiniMax-Text-01 / M3 / M2.7 / abab6.5s-chat |
| `启用 LangSmith tracing` | 开启完整 trace 记录（需配置 `LANGSMITH_API_KEY`） |
| `初始化知识库` | 首次使用前需点击，初始化 ChromaDB 向量库 |

---

## 📦 Tool 清单

| Tool | 功能 | 调用方式 |
|------|------|----------|
| `query_order` | 查询订单详情 | 输入订单号 |
| `track_logistics` | 查询物流轨迹 | 输入订单号 |
| `submit_return_request` | 提交退换货 | 订单号 + 类型 + 原因 |
| `transfer_to_human` | 转交人工 | 摘要信息 |
| `product_kb_search` | RAG 商品知识库 | 自然语言问题 |

---

## 🔄 从 MVP 演进到生产级

当前代码为 **Phase 1（基础建设）**，已实现：

- [x] 向量数据库（ChromaDB）引入
- [x] PII 脱敏 + Injection 检测 + 幻觉检测
- [x] LangGraph 状态持久化（MemorySaver）
- [x] 5 Tool 完整调用链
- [x] Streamlit 生产级配置面板

**Phase 2 计划**（多 Agent 路由）：
- LangGraph StateGraph 替代 create_react_agent
- Supervisor Router → 专家子 Agent
- OTEL 可观测性
- Playwright E2E 测试

**Phase 3 计划**（规模化）：
- Docker Compose 部署
- Redis 限流 + Semantic Cache
- 多 Region Active-Active

---

## 📄 许可证

本项目仅供学习和研究使用。MIT License。

---

## 👤 作者

[CHu1_Zzz](https://github.com/CHu1Zzz)