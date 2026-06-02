"""人工转交 Tool"""

from langchain_core.tools import tool


@tool
def transfer_to_human(summary: str) -> str:
    """将当前对话转交给人工客服。当无法解决用户问题、用户明确要求转人工、或涉及退款金额争议时使用。

    Args:
        summary: 当前对话的简要摘要，包含用户的核心问题和已尝试的解决方案
    """
    return (
        f"🔄 正在为您转接人工客服...\n\n"
        f"📋 对话摘要：{summary}\n\n"
        f"人工客服将基于以上信息继续为您服务，请稍候。"
    )
