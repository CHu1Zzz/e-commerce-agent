"""Streamlit 界面 — 电商客服 Agent UI（生产级配置）"""

import os
import sys
import subprocess
from pathlib import Path

# 将项目根目录加入 Python 路径，确保可以 import app 模块
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from dotenv import load_dotenv

from app.agent.agent import create_agent, chat

# 加载 .env 文件
load_dotenv()


def init_session_state():
    """初始化 Streamlit session state"""
    if "agent" not in st.session_state:
        st.session_state.agent = None
        st.session_state.chat_history = []
        st.session_state.init_error = None


def render_chat_message(role: str, content: str):
    """渲染单条聊天消息"""
    if role == "user":
        with st.chat_message("user", avatar="🧑"):
            st.markdown(content)
    else:
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(content)


def build_agent(api_key: str, base_url: str, model: str, enable_langsmith: bool):
    """根据配置构建 Agent"""
    if not api_key or api_key == "your-key-here":
        return None, "请先在左侧边栏输入你的 MiniMax API Key"
    try:
        agent = create_agent(
            api_key=api_key,
            base_url=base_url,
            model=model,
            enable_checkpointer=True,
            enable_langsmith=enable_langsmith,
        )
        return agent, None
    except Exception as e:
        return None, str(e)


def check_vector_db_status() -> tuple[bool, str]:
    """检查向量数据库是否已初始化"""
    app_dir = PROJECT_ROOT / "app"
    chroma_dir = app_dir / "data" / "chroma_db"
    if not chroma_dir.exists():
        return False, "未初始化"
    # 检查是否有 collection
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(chroma_dir))
        collection = client.get_collection("ecommerce_products")
        count = collection.count()
        return True, f"已初始化（{count} 条文档）"
    except Exception:
        return False, "未初始化"


def run_init_vector_db():
    """运行向量库初始化脚本"""
    try:
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "init_vector_db.py")],
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
        )
        if result.returncode == 0:
            return True, "初始化成功！"
        else:
            return False, f"初始化失败：{result.stderr[:200]}"
    except Exception as e:
        return False, f"执行出错：{e}"


def main():
    st.set_page_config(
        page_title="电商客服 Agent — 小帮",
        page_icon="🛒",
        layout="wide",
    )

    init_session_state()

    # ========== 侧边栏：完整配置面板 ==========
    with st.sidebar:
        st.header("⚙️ 配置面板")

        # --- 1. API 配置 ---
        st.subheader("🔑 API 配置")
        api_key = st.text_input(
            "MINIMAX_API_KEY",
            value=os.getenv("MINIMAX_API_KEY", ""),
            type="password",
            placeholder="输入 API Key",
        )

        base_url = st.text_input(
            "API Base URL",
            value=os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat/v1"),
            placeholder="https://api.minimax.chat/v1",
        )

        model = st.selectbox(
            "模型",
            options=["MiniMax-Text-01", "MiniMax-M3", "MiniMax-M2.7", "abab6.5s-chat"],
            index=0,
        )

        enable_langsmith = st.checkbox(
            "启用 LangSmith tracing",
            value=False,
            help="启用后会在 LangSmith 记录完整 trace（需配置 LANGSMITH_API_KEY）",
        )

        st.markdown("---")

        # --- 2. 向量数据库状态 ---
        st.subheader("🗃️ 向量数据库")
        is_init, db_status = check_vector_db_status()

        if is_init:
            st.success(f"✅ {db_status}")
        else:
            st.warning(f"⚠️ {db_status}")
            if st.button("📦 初始化知识库", use_container_width=True):
                with st.spinner("正在初始化向量数据库..."):
                    success, msg = run_init_vector_db()
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

        st.markdown("---")

        # --- 3. 连接按钮 ---
        if api_key and api_key != "your-key-here":
            if st.button("🚀 连接 Agent", use_container_width=True, type="primary"):
                agent, err = build_agent(api_key, base_url, model, enable_langsmith)
                if err:
                    st.error(err)
                else:
                    st.session_state.agent = agent
                    st.session_state.init_error = None
                    st.success("✅ Agent 已就绪！可以开始对话！")
                    st.rerun()

        # --- 4. 测试订单号 ---
        st.markdown("---")
        st.markdown(
            "**📋 测试订单号**：\n"
            "```\n"
            "ORD-20260530-001（已发货）\n"
            "ORD-20260528-002（已签收，可退货）\n"
            "ORD-20260601-003（待发货）\n"
            "ORD-20260531-005（已发货）\n"
            "```"
        )

        # --- 5. 安全功能状态 ---
        st.markdown("---")
        st.markdown("**🛡️ 安全功能**：")
        st.markdown("```\nPII 脱敏：✅ 已启用\n"
                    "Prompt Injection 拦截：✅ 已启用\n"
                    "幻觉检测：✅ 已启用\n"
                    "状态持久化：✅ MemorySaver\n"
                    "```")

    # ========== 主界面 ==========
    st.title("🛒 电商客服 — 小帮")
    st.caption("基于 LangChain + MiniMax 的生产级智能客服助手")

    # Agent 连接状态
    if st.session_state.agent is None:
        st.warning("⚠️ Agent 未连接。请在左侧配置并点击「连接 Agent」")
    else:
        st.success("✅ Agent 已连接")

    # 渲染历史消息
    for msg in st.session_state.chat_history:
        render_chat_message(msg["role"], msg["content"])

    # ===== 快捷按钮 =====
    st.markdown("---")
    cols = st.columns(4)
    button_disabled = st.session_state.agent is None

    btn_data = [
        ("📦 查订单", "帮我查一下订单 ORD-20260530-001 的状态"),
        ("🚚 查物流", "帮我看看订单 ORD-20260530-001 的物流到哪了"),
        ("🔄 办退货", "我要退货，订单号 ORD-20260528-002，尺码不合适"),
        ("📚 问知识", "这件T恤可以机洗吗？尺码偏大吗？"),
    ]

    for col, (label, msg) in zip(cols, btn_data):
        if col.button(label, use_container_width=True, disabled=button_disabled):
            st.session_state.pending_input = msg

    # ===== 聊天输入框 =====
    user_input = st.chat_input(
        "请输入您的问题...",
        disabled=st.session_state.agent is None,
    )

    # 处理快捷按钮的输入
    if "pending_input" in st.session_state and st.session_state.pending_input:
        user_input = st.session_state.pending_input
        st.session_state.pending_input = None

    if user_input:
        render_chat_message("user", user_input)
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        with st.spinner("小帮正在思考..."):
            try:
                reply = chat(st.session_state.agent, user_input)
            except Exception as e:
                reply = f"抱歉，出了点问题：{e}\n请稍后再试，或输入「转人工」联系客服。"

        render_chat_message("assistant", reply)
        st.session_state.chat_history.append({"role": "assistant", "content": reply})


if __name__ == "__main__":
    main()