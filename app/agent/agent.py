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


# 强制工具调用的触发关键词（命中则必须调用工具）
# 每个条目: (regex_pattern, tool_name) — tool_name 供 _force_tool_call 直接路由
_FORCE_TOOL_PATTERNS = [
    (re.compile(r"(推荐|有什么.*商品|跑步|健身|通勤|送礼|保暖|夏季)"), "product_recommend"),
    (re.compile(r"(身高|买.*码|穿.*码|选.*码|T恤|裤子|鞋子)"), "size_recommend"),
    (re.compile(r"(有没有|帮我找|搜索|找.*(商品|衣服|鞋|裤))"), "product_search"),
]


def _should_force_tool_call(message: str) -> bool:
    """检查用户消息是否命中强制工具调用模式"""
    msg_lower = message.lower()
    for pattern, _ in _FORCE_TOOL_PATTERNS:
        if pattern.search(msg_lower):
            return True
    return False




def _force_tool_call(agent, message: str, config: dict) -> Optional[str]:
    """当 Agent 跳过工具调用时，强制调用对应工具并返回结果"""
    msg_lower = message.lower()

    # 用预编译正则匹配，从 tuple 直接获取 tool_name，消灭重复 if/elif
    for pattern, tool_name in _FORCE_TOOL_PATTERNS:
        if pattern.search(msg_lower):
            return _dispatch_forced_tool(tool_name, message, msg_lower)

    return None


def _dispatch_forced_tool(tool_name: str, message: str, msg_lower: str) -> Optional[str]:
    """根据 tool_name 分发到对应工具的强制调用逻辑"""
    if tool_name == "product_recommend":
        from app.agent.tools.product_recommend import product_recommend

        scene = next((kw for kw in ("跑步", "健身", "通勤", "送礼", "保暖", "夏季") if kw in msg_lower), None)
        kwargs = {"scene": scene} if scene else {}
        try:
            return _format_tool_result(product_recommend.invoke(kwargs), "商品推荐")
        except Exception:
            return None

    if tool_name == "size_recommend":
        from app.agent.tools.size_recommendation import size_recommend

        product_type = "T恤"
        if "裤" in msg_lower:
            product_type = "裤子"
        elif "鞋" in msg_lower:
            product_type = "运动鞋"
        height_match = re.search(r"(\d+)\s*(cm|厘米)?", message)
        height = float(height_match.group(1)) if height_match else None
        kwargs = {"product_type": product_type}
        if height:
            kwargs["height_cm"] = height
        try:
            return _format_tool_result(size_recommend.invoke(kwargs), "尺码推荐")
        except Exception:
            return None

    if tool_name == "product_search":
        from app.agent.tools.product_search import product_search

        keywords = re.sub(r"(有没有|帮我找|搜索|找|的 商品|衣服|鞋|裤子)", "", message).strip()
        try:
            return _format_tool_result(product_search.invoke({"query": keywords or "衣服", "top_k": 5}), "商品搜索")
        except Exception:
            return None

    return None

def _format_tool_result(result: str, label: str) -> str:
    """格式化工具返回结果，确保通过幻觉检测"""
    return f"【{label}结果】\n{result}"


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
    from datetime import datetime as _datetime
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
        prompt=get_system_prompt(_datetime.now()),
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
            rejected_id = thread_id  # 保留原始值用于安全审计
            thread_id = "invalid"
            _security_logger.warning("Invalid thread_id rejected: %s", _sanitize_log_string(rejected_id))

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

    # ===== Step 3: 提取回复（去掉 thinking 标签）+ 检查是否跳过了工具调用 =====
    response = ""
    tool_result_for_check = None
    tool_called = False

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
    # 同时检查是否有工具被调用
    for msg in result["messages"]:
        if msg.type == "tool":
            tool_result_for_check = msg.content
            tool_called = True
            break

    # ===== Step 5: 强制工具调用兜底 =====
    # 如果用户请求了推荐类内容，但 Agent 跳过了工具调用（生成了幻觉内容），
    # 则直接调用对应工具并将结果返回给用户
    if not tool_called and _should_force_tool_call(safe_message):
        _security_logger.warning(
            "Tool bypass detected for query '%s' — forcing tool call",
            _sanitize_log_string(safe_message[:50]),
        )
        forced_result = _force_tool_call(agent, safe_message, config)
        if forced_result:
            return forced_result

    # ===== Step 5: 输出安全处理 =====
    if enable_safety:
        response = postprocess_output(response, tool_result_for_check)

    return response