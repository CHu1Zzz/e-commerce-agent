"""Agent 核心逻辑 — 基于 LangGraph 的 ReAct Agent（生产级）

功能：
- PII 脱敏（输入层）
- Prompt Injection 检测（输入层，检测到即阻断）
- LangGraph Checkpointer 状态持久化
- RAG Tool（商品知识库）
- 幻觉检测（输出层）
- LangSmith 可观测性（可选）
"""

import logging
import os
import re
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from app.agent.prompts import get_system_prompt
from app.agent.tools.order_query import query_order
from app.agent.tools.logistics import track_logistics
from app.agent.tools.return_request import submit_return_request
from app.agent.tools.human_handoff import transfer_to_human
from app.agent.tools.product_kb import product_kb_search
from app.agent.tools.product_search import product_search
from app.agent.tools.size_recommendation import size_recommend
from app.agent.tools.product_recommend import product_recommend
from app.security.pii_scrubber import PIIScrubber
from app.security.prompt_injection_detector import check_injection, sanitize_input

# 安全专用 logger，禁止使用 print()
_security_logger = logging.getLogger("app.security")
_security_logger.setLevel(logging.WARNING)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
_security_logger.addHandler(_handler)

# thread_id 验证：仅允许字母数字下划线，长度 1-64
_THREAD_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _sanitize_log_string(text: str) -> str:
    """移除控制字符（防日志注入）"""
    return text.replace("\n", "\\n").replace("\r", "\\r").replace("\x00", "")


def create_agent(
    api_key: str,
    base_url: Optional[str] = None,
    model: str = "MiniMax-Text-01",
    enable_checkpointer: bool = True,
    enable_langsmith: bool = False,
):
    """创建并返回一个配置好的客服 Agent（生产级）。

    Args:
        api_key: MiniMax API Key
        base_url: MiniMax API 地址，默认从环境变量 MINIMAX_BASE_URL 读取
        model: 模型名称
        enable_checkpointer: 是否启用状态持久化（断线重连）
        enable_langsmith: 是否启用 LangSmith tracing

    Returns:
        LangGraph ReAct Agent 实例（已配置 checkpointer）
    """
    if base_url is None:
        base_url = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat/v1")

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
        os.environ["LANGCHAIN_ENDPOINT"] = os.getenv(
            "LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com"
        )

    # ===== 3. 注册所有 Tool =====
    tools = [
        query_order,
        track_logistics,
        submit_return_request,
        transfer_to_human,
        product_kb_search,     # RAG 商品知识库 Tool
        product_search,        # 商品搜索 Tool
        size_recommend,        # 尺码推荐 Tool
        product_recommend,     # 商品推荐 Tool
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
    """对用户输入进行预处理：Prompt Injection 阻断 + PII 脱敏

    Returns:
        (safe_input, warning_message)
        - safe_input: 处理后的安全输入
        - warning_message: 如果检测到 PII 脱敏，返回警告信息（可选）

    Raises:
        ValueError: 当检测到 Prompt Injection 攻击时直接拒绝
    """
    warning = None

    # Step 1: Prompt Injection 检测 — 检测到即阻断，不放行
    is_safe, reason = check_injection(user_input)
    if not is_safe:
        _security_logger.warning(
            "Prompt injection detected: %s", _sanitize_log_string(reason)
        )
        raise ValueError(
            "您的输入包含可疑内容，无法处理。请切换到正常对话模式。"
        )

    # Step 2: PII 脱敏
    scrubber = PIIScrubber()
    safe_input = scrubber.redact(user_input)

    # 如果脱敏前后不同，记录脱敏类型数量（不泄露具体内容）
    if safe_input != user_input:
        pii_types = scrubber.check(user_input)
        pii_count = len(pii_types)
        warning = f"（检测到 {pii_count} 类敏感信息，已自动脱敏）"
        _security_logger.info(
            "PII redacted: %d type(s) in thread", pii_count
        )

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
        enable_safety: 是否启用安全检查（仅 DEBUG 模式可用）
        ⚠️ enable_safety=False 仅在 DEBUG=True 时生效，生产环境强制为 True

    Returns:
        Agent 的回复文本（已脱敏、不含 thinking 过程）
    """
    # 生产环境强制开启安全检查，忽略 enable_safety 参数
    _debug_mode = os.getenv("DEBUG", "").lower() in ("1", "true", "yes")
    if not _debug_mode and not enable_safety:
        _security_logger.warning("enable_safety=False called in non-DEBUG env — forcing True")
        enable_safety = True
    # ===== Step 1: 输入安全处理 =====
    if enable_safety:
        # 验证 thread_id 格式，防止日志注入
        if not _THREAD_ID_PATTERN.match(thread_id):
            thread_id = "invalid"
            _security_logger.warning("Invalid thread_id rejected: %s", thread_id)

        try:
            safe_message, warning = preprocess_input(message)
        except ValueError as ve:
            # Prompt Injection 被阻断，直接返回拒绝消息
            return str(ve)

        if warning:
            _security_logger.info(
                "thread=%s: %s", thread_id, _sanitize_log_string(warning)
            )
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