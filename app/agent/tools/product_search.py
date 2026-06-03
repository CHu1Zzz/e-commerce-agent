"""商品搜索 Tool — 支持按名称/类别/标签/价格区间搜索商品"""

import json
import sys
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field


# 定位项目根目录
_APP_DIR = Path(sys.modules["app"].__file__).parent
DATA_DIR = _APP_DIR / "data"
PRODUCTS_FILE = DATA_DIR / "mock_products.json"


def _load_products() -> list[dict]:
    """加载商品目录数据"""
    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


class ProductSearchInput(BaseModel):
    """商品搜索输入参数"""

    query: str = Field(
        description="搜索关键词，可输入商品名称、类别、标签（如'T恤'、'运动鞋'、'保暖'）",
        min_length=1,
        max_length=100,
    )
    category: Optional[str] = Field(
        default=None,
        description="限定商品类别，如 'clothing'、'shoes'、'accessories'、'electronics'、'sports'、'home'",
    )
    max_price: Optional[float] = Field(
        default=None,
        ge=0,
        description="最高价格筛选（单位：元），不填则不限",
    )
    on_sale_only: bool = Field(
        default=False,
        description="是否仅显示特价商品，默认 False",
    )
    sort_by: str = Field(
        default="relevance",
        description="排序方式：relevance（相关性）、price_asc（价格升序）、price_desc（价格降序）、sales（销量）、rating（评分）",
    )
    top_k: int = Field(
        default=6,
        ge=1,
        le=20,
        description="返回商品数量，默认6条",
    )


def _score_product(product: dict, query: str) -> float:
    """计算商品与搜索词的相关性分数（0-1）"""
    query_lower = query.lower()
    score = 0.0

    # 商品名称完全匹配
    if query_lower in product["name"].lower():
        score += 0.5
    # 商品名称包含搜索词
    for word in query_lower.split():
        if word in product["name"].lower():
            score += 0.2
        # 类别匹配
        if word in product.get("category", "").lower():
            score += 0.1
        # 子类别匹配
        if word in product.get("subcategory", "").lower():
            score += 0.15
        # 标签匹配
        for tag in product.get("tags", []):
            if word in tag.lower():
                score += 0.1
        # 描述匹配
        if word in product.get("description", "").lower():
            score += 0.05

    return min(score, 1.0)


@tool(args_schema=ProductSearchInput)
def product_search(
    query: str,
    category: Optional[str] = None,
    max_price: Optional[float] = None,
    on_sale_only: bool = False,
    sort_by: str = "relevance",
    top_k: int = 6,
) -> str:
    """搜索商品目录，返回匹配的商品列表。

    适用于：
    - 用户想找特定类型商品（"有没有跑步鞋"、"我要买T恤"）
    - 用户想按价格筛选（"200块以内的"）
    - 用户想找特价商品（"打折的商品有哪些"）
    - 用户想按销量/评分排序（"销量最好的"）

    返回格式：商品名称、价格、标签、评分、销量、是否特价等信息。

    Args:
        query: 搜索关键词（商品名称/类别/标签）
        category: 限定商品类别（可选）
        max_price: 最高价格筛选（可选）
        on_sale_only: 是否仅显示特价商品，默认 False
        sort_by: 排序方式（relevance/price_asc/price_desc/sales/rating）
        top_k: 返回商品数量，默认6条
    """
    products = _load_products()

    # ===== 1. 过滤 =====
    results = []
    for p in products:
        # 按类别过滤
        if category and p.get("category") != category:
            continue
        # 按最高价格过滤
        if max_price is not None and p.get("price", 0) > max_price:
            continue
        # 按特价过滤
        if on_sale_only and not p.get("is_on_sale", False):
            continue

        # 计算相关性分数
        relevance = _score_product(p, query)
        if relevance > 0:
            p["_relevance"] = relevance
            results.append(p)

    # ===== 2. 排序 =====
    if sort_by == "relevance":
        results.sort(key=lambda x: x["_relevance"], reverse=True)
    elif sort_by == "price_asc":
        results.sort(key=lambda x: x["price"])
    elif sort_by == "price_desc":
        results.sort(key=lambda x: x["price"], reverse=True)
    elif sort_by == "sales":
        results.sort(key=lambda x: x.get("sales_count", 0), reverse=True)
    elif sort_by == "rating":
        results.sort(key=lambda x: x.get("rating", 0), reverse=True)

    # ===== 3. 截取 top_k =====
    results = results[:top_k]

    if not results:
        return "未找到匹配的商品，请尝试其他关键词或调整筛选条件。"

    # ===== 4. 格式化输出 =====
    lines = []
    for i, p in enumerate(results, 1):
        price_str = f"¥{p['price']:.1f}"
        sale_tag = " [特价]" if p.get("is_on_sale") else ""
        rating_star = "⭐" * int(p.get("rating", 0))
        tags_str = "、".join(p.get("tags", [])[:3])
        sizes_str = "/".join(p.get("sizes", []))
        colors_str = "、".join(p.get("colors", []))

        lines.append(
            f"{i}. {p['name']} {price_str}{sale_tag}\n"
            f"   类别：{p.get('subcategory', '-')}｜评分：{rating_star} {p.get('rating', 0)}｜"
            f"销量：{p.get('sales_count', 0)}\n"
            f"   标签：{tags_str}\n"
            f"   尺码：{sizes_str}｜颜色：{colors_str}\n"
            f"   商品ID：{p['product_id']}"
        )

    header = f"共找到 {len(results)} 件相关商品：\n"
    return header + "\n\n".join(lines)