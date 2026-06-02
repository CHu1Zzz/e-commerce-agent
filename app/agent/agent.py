"""Agent 核心逻辑 — 基于 LangGraph 的 ReAct Agent（生产级）

功能：
- PII 脱敏（输入层）
- Prompt Injection 检测（输入层）
- LangGraph Checkpointer 状态持久化
- RAG Tool（商品知识库）
- 幻觉检测（输出层）
- LangSmith 可观测性（可选）
"""

import os
import re
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from app.agent.prompts import get_system_prompt
from app.agent.tools.order_query import query_order
from app.agent.tools.logistics import track_logistics
from app.agent.tools.return_request import submit_return_request
from app.agent.tools.human_handoff import transfer_to_human
from app.agent.tools.product_kb import product_kb_search
from app.security.pii_scrubber import redact_pii, PIIScrubber
from app.security.prompt_injection_detector import check_injection, sanitize_input


def create_agent(
    api_key: str,
    base_url: str = "https://api.minimax.chat/v1",
    model: str = "MiniMax-Text-01",
    enable_checkpointer: bool = True,
    enable_langsmith: bool = False,
):
    """创建并返回一个配置好的客服 Agent（生产级）。

    Args:
        api_key: MiniMax API Key
        base_url: MiniMax API 地址（OpenAI 兼容接口）
        model: 模型名称
        enable_checkpointer: 是否启用状态持久化（断线重连）
        enable_langsmith: 是否启用 LangSmith tracing

    Returns:
        LangGraph ReAct Agent 实例（已配置 checkpointer）
    """
    # ===== 1. LLM 初始化 =====
    llm = ChatOpenAI(
        model=model,
        base_url=base_url,
        api_key=api_key,
        temperature=0.3,
    )

    # ===== 2. LangSmith 可观测性（可选）=====
    if enable_langsmith and os.getenv("LANGSMITH_API_KEY"):
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
        os.environ["LANGCHAIN_PROJECT"] = "ecommerce-cs-agent"
        os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"

    # ===== 3. 注册所有 Tool =====
    tools = [
        query_order,
        track_logistics,
        submit_return_request,
        transfer_to_human,
        product_kb_search,  # 新增：RAG 商品知识库 Tool
    ]

    # ===== 4. 状态持久化 Checkpointer =====
    # 开发环境用 InMemory，生产环境换 PostgresSaver
    checkpointer = MemorySaver() if enable_checkpointer else None

    # ===== 5. 创建 ReAct Agent =====
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=get_system_prompt(),
        checkpointer=checkpointer,
    )

    return agent


def preprocess_input(user_input: str) -> tuple[str, Optional[str]]:
    """对用户输入进行预处理：PII 脱敏 + Injection 检测

    Returns:
        (safe_input, warning_message)
        - safe_input: 处理后的安全输入
        - warning_message: 如果检测到问题，返回警告信息（可选）
    """
    warning = None

    # Step 1: Prompt Injection 检测
    is_safe, reason = check_injection(user_input)
    if not is_safe:
        # 清洗输入，移除 injection 标记
        user_input = sanitize_input(user_input)
        warning = f"⚠️ 检测到可疑输入，已自动处理。{reason}"

    # Step 2: PII 脱敏
    scrubber = PIIScrubber()
    safe_input = scrubber.redact(user_input)

    # 如果脱敏前后不同，记录脱敏信息
    if safe_input != user_input:
        pii_found = [f["type"] for f in scrubber.check(user_input)]
        warning = (warning or "") + f"（部分敏感信息已脱敏：{', '.join(pii_found)}）"

    return safe_input, warning


def postprocess_output(
    response: str,
    tool_result: Optional[str] = None,
) -> str:
    """对 LLM 输出进行后处理：幻觉检测"""
    if not tool_result:
        return response

    from app.security.hallucination_detector import check_hallucination

    check = check_hallucination(response, tool_result)
    if not check["is_consistent"]:
        return (
            "抱歉，我在核对信息时发现了一些不一致，"
            "为了确保准确，建议您联系人工客服确认详情。"
        )

    return response


def chat(
    agent,
    message: str,
    thread_id: str = "default",
    enable_safety: bool = True,
) -> str:
    """与 Agent 进行一轮对话（含完整安全处理流程）。

    Args:
        agent: Agent 实例
        message: 用户消息
        thread_id: 会话 ID（用于 Checkpointer 持久化）
        enable_safety: 是否启用安全检查（测试时可关闭）

    Returns:
        Agent 的回复文本（已脱敏、不含 thinking 过程）
    """
    # ===== Step 1: 输入安全处理 =====
    if enable_safety:
        safe_message, warning = preprocess_input(message)
        if warning:
            # 记录警告，但不阻断流程
            print(f"[安全警告] thread={thread_id}: {warning}")
    else:
        safe_message = message

    # ===== Step 2: 调用 Agent =====
    config = {"configurable": {"thread_id": thread_id}}

    result = agent.invoke(
        {"messages": [HumanMessage(content=safe_message)]},
        config=config,
    )

    # ===== Step 3: 提取回复（去掉 thinking 标签）=====
    response = ""
    tool_result_for_check = None

    for msg in reversed(result["messages"]):
        if msg.type == "ai" and not msg.tool_calls:
            content = msg.content
            # 去掉 <think>...</think> 思考过程标签
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
            response = content.strip()
            break

    if not response:
        return "抱歉，我暂时无法回答，请稍后再试。"

    # ===== Step 4: 获取工具返回结果用于幻觉检测 =====
    for msg in result["messages"]:
        if msg.type == "tool":
            tool_result_for_check = msg.content
            break

    # ===== Step 5: 输出安全处理 =====
    if enable_safety:
        response = postprocess_output(response, tool_result_for_check)

    return response