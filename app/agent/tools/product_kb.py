"""商品知识库 RAG Tool — 基于 ChromaDB 向量检索"""

import os
import sys
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

try:
    import chromadb
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

# 定位项目根目录
_APP_DIR = Path(sys.modules["app"].__file__).parent
DATA_DIR = _APP_DIR / "data"
CHROMA_DIR = DATA_DIR / "chroma_db"


class ProductKBSearchInput(BaseModel):
    """商品知识库检索输入参数"""

    query: str = Field(
        description="用户关于商品的问题，如'这件T恤可以机洗吗'、'尺码偏大吗'、'退换货政策是什么'",
        min_length=1,
        max_length=200,
    )
    top_k: int = Field(
        default=3,
        ge=1,
        le=10,
        description="返回最相关的文档数量，默认3条",
    )


class ProductKBTool:
    """商品知识库 RAG Tool"""

    def __init__(self, persist_dir: str = None):
        self._client: Optional[chromadb.PersistentClient] = None
        self._collection = None
        self._persist_dir = persist_dir or str(CHROMA_DIR)
        self._init_client()

    def _init_client(self):
        """初始化 ChromaDB 客户端"""
        if not CHROMA_AVAILABLE:
            print("[WARN] ChromaDB 未安装，商品知识库 RAG Tool 不可用")
            return

        try:
            self._client = chromadb.PersistentClient(path=self._persist_dir)
            self._collection = self._client.get_collection("ecommerce_products")
        except Exception as e:
            print(f"[WARN] ChromaDB 初始化失败: {e}")
            self._collection = None

    def search(self, query: str, top_k: int = 3) -> dict:
        """执行向量检索

        Args:
            query: 用户查询文本
            top_k: 返回前 k 条最相关文档

        Returns:
            {
                "answer": str,       # 拼接后的上下文文本
                "sources": list,     # 文档 ID 列表
                "scores": list,      # 相似度分数
                "doc_types": list,   # 文档类型
            }
        """
        if self._collection is None:
            return {
                "answer": "知识库暂时不可用，请稍后再试。",
                "sources": [],
                "scores": [],
                "doc_types": [],
            }

        try:
            from langchain_openai import OpenAIEmbeddings

            embeddings = OpenAIEmbeddings(
                model="text-embedding-3-small",
                base_url=os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat/v1"),
                api_key=os.getenv("MINIMAX_API_KEY", ""),
            )

            query_vec = embeddings.embed_query(query)

            results = self._collection.query(
                query_embeddings=[query_vec],
                n_results=top_k,
            )

            if not results["documents"] or not results["documents"][0]:
                return {
                    "answer": "未找到相关信息，请咨询人工客服。",
                    "sources": [],
                    "scores": [],
                    "doc_types": [],
                }

            docs = results["documents"][0]
            metas = results["metadatas"][0]
            scores = results["distances"][0] if "distances" in results else []

            # 拼接上下文，不同 doc_type 可加前缀标签
            context_parts = []
            doc_types = []
            for doc, meta in zip(docs, metas):
                doc_type = meta.get("doc_type", "unknown")
                doc_types.append(doc_type)
                context_parts.append(f"[{doc_type}] {doc}")

            return {
                "answer": "\n".join(context_parts),
                "sources": results["ids"][0],
                "scores": [float(s) for s in scores] if scores else [],
                "doc_types": doc_types,
            }

        except Exception as e:
            print(f"[ERROR] RAG 检索失败: {e}")
            return {
                "answer": "知识库检索失败，请稍后再试。",
                "sources": [],
                "scores": [],
                "doc_types": [],
            }

    def is_available(self) -> bool:
        """检查知识库是否可用"""
        return self._collection is not None


# 全局单例（延迟初始化）
_kb_tool: Optional[ProductKBTool] = None


def get_kb_tool() -> ProductKBTool:
    global _kb_tool
    if _kb_tool is None:
        _kb_tool = ProductKBTool()
    return _kb_tool


@tool(args_schema=ProductKBSearchInput)
def product_kb_search(query: str, top_k: int = 3) -> str:
    """搜索商品知识库，回答关于商品属性、尺码、退换货政策、支付方式等问题。

    适用于回答以下类型的问题：
    - 商品材质、洗涤方式、尺码建议（如"这件T恤可以机洗吗？"）
    - 退换货政策细节（时效、条件、流程）（如"可以7天无理由退货吗？"）
    - 发货时间、运费计算（如"几天能到？"）
    - 会员权益、优惠券使用规则（如"金卡会员有什么权益？"）
    - 支付方式介绍（如"支持花呗吗？"）

    Args:
        query: 用户的商品相关问题（必填）
        top_k: 返回的相关文档数量，默认3条，最多10条
    """
    kb = get_kb_tool()

    if not kb.is_available():
        return "商品知识库暂时不可用，建议您联系人工客服获取帮助。"

    result = kb.search(query, top_k)

    if not result["sources"]:
        return result["answer"]

    # 拼接最终回复
    reply = (
        f"根据知识库信息：\n{result['answer']}"
    )

    if result["sources"]:
        reply += f"\n\n（参考文档 ID：{', '.join(result['sources'][:3])}）"

    return reply