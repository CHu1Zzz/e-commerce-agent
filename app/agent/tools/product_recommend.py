"""商品推荐 Tool — 基于用户偏好/场景/行为数据推荐商品"""

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


class ProductRecommendInput(BaseModel):
    """商品推荐输入参数"""

    scene: Optional[str] = Field(
        default=None,
        description="使用场景或需求，如 '跑步'、'通勤'、'送礼'、'户外运动'、'日常休闲'",
    )
    recipient: Optional[str] = Field(
        default=None,
        description="送礼对象，如 '男朋友'、'父母'、'朋友'、'孩子'",
    )
    budget: Optional[float] = Field(
        default=None,
        ge=0,
        description="预算（单位：元），如 200",
    )
    category: Optional[str] = Field(
        default=None,
        description="限定商品类别，如 'clothing'、'shoes'、'accessories'、'electronics'",
    )
    preference_tags: Optional[str] = Field(
        default=None,
        description="用户偏好标签，如 '保暖'、'透气'、'轻便'、'运动'、'商务'",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=10,
        description="返回推荐商品数量，默认5条",
    )


def _score_by_scene(product: dict, scene: str) -> float:
    """根据场景匹配度打分"""
    scene_keywords = {
        "跑步": ["跑步", "运动", "透气", "减震", "轻便", "运动鞋"],
        "健身": ["健身", "运动", "瑜伽", "吸湿", "速干", "运动鞋", "运动裤"],
        "通勤": ["商务", "通勤", "衬衫", "皮带", "手提包", "正装"],
        "户外": ["户外", "防晒", "登山", "徒步", "运动鞋", "双肩背包"],
        "休闲": ["休闲", "纯棉", "百搭", "T恤", "运动裤"],
        "运动": ["运动", "跑步", "健身", "瑜伽", "运动鞋", "运动裤"],
        "送礼": ["礼品", "礼盒", "皮带", "保温杯", "手提包"],
        "保暖": ["保暖", "羽绒服", "羊毛", "加绒", "冬装"],
        "夏季": ["透气", "冰丝", "短裤", "凉鞋", "防晒"],
        "送礼 男": ["皮带", "钱包", "手表", "男士"],
        "送礼 女": ["手提包", "丝巾", "连衣裙", "女士"],
        "送礼 父母": ["保暖", "羊毛", "保温杯", "颈椎枕"],
        "送礼 孩子": ["玩具", "童鞋", "儿童", "运动鞋"],
    }

    scene_lower = scene.lower()
    score = 0.0

    # 直接场景匹配
    if scene_lower in scene_keywords:
        for kw in scene_keywords[scene_lower]:
            if kw in product.get("name", "").lower():
                score += 0.3
            for tag in product.get("tags", []):
                if kw in tag.lower():
                    score += 0.2

    # 模糊匹配
    for kw in scene_lower.split():
        if kw in product.get("name", "").lower():
            score += 0.2
        for tag in product.get("tags", []):
            if kw in tag.lower():
                score += 0.15
        if kw in product.get("description", "").lower():
            score += 0.05

    return min(score, 1.0)


@tool(args_schema=ProductRecommendInput)
def product_recommend(
    scene: Optional[str] = None,
    recipient: Optional[str] = None,
    budget: Optional[float] = None,
    category: Optional[str] = None,
    preference_tags: Optional[str] = None,
    top_k: int = 5,
) -> str:
    """根据用户场景、预算、偏好等条件推荐商品。

    适用于：
    - 用户说"有什么适合跑步的推荐吗"
    - 用户说"我想买送父母的礼物，200块以内"
    - 用户说"最近有什么热销商品"
    - 用户说"给我推荐点保暖的东西"

    推荐逻辑：
    1. 优先按场景标签匹配（如跑步→运动鞋/运动裤）
    2. 结合预算过滤（不超出用户预算）
    3. 按销量和评分综合排序
    4. 兼顾用户偏好标签

    Args:
        scene: 使用场景（跑步/健身/通勤/户外/休闲/送礼等）
        recipient: 送礼对象（男朋友/父母/朋友/孩子）
        budget: 预算上限（单位：元）
        category: 限定商品类别
        preference_tags: 用户偏好标签（透气/保暖/轻便等）
        top_k: 返回推荐数量，默认5条
    """
    products = _load_products()

    # ===== 1. 确定推荐策略 =====
    # 场景优先标签
    effective_scene = scene or ""
    if recipient:
        # 拼接送礼场景
        effective_scene = f"{effective_scene} 送礼 {recipient}".strip()

    # ===== 2. 过滤 + 打分 =====
    scored_products = []
    has_any_filter = any([effective_scene, preference_tags, budget is not None, category])

    for p in products:
        # 预算过滤
        if budget is not None and p.get("price", 0) > budget:
            continue

        # 类别过滤
        if category and p.get("category") != category:
            continue

        # 计算匹配分数
        score = 0.0

        # 场景匹配分
        if effective_scene:
            scene_score = _score_by_scene(p, effective_scene)
            score += scene_score * 0.6  # 场景权重60%

        # 偏好标签匹配分
        if preference_tags:
            pref_lower = preference_tags.lower()
            for kw in pref_lower.split():
                if kw in p.get("name", "").lower():
                    score += 0.2
                for tag in p.get("tags", []):
                    if kw in tag.lower():
                        score += 0.15

        # 基础分（销量+评分），冷启动时加大权重
        sales_normalized = min(p.get("sales_count", 0) / 10000, 1.0)
        rating_normalized = p.get("rating", 0) / 5.0
        base_weight = 0.5 if not has_any_filter else 0.25
        base_score = sales_normalized * 0.15 + rating_normalized * base_weight
        score += base_score

        if score > 0:
            p["_score"] = score
            p["_base_score"] = base_score
            scored_products.append(p)

    if not scored_products:
        return (
            f"抱歉，根据您的条件（"
            + (f"场景：{scene}，" if scene else "")
            + (f"预算：¥{budget}以内，" if budget else "")
            + (f"类别：{category}，" if category else "")
            + "）暂未找到合适的商品，请尝试放宽条件。"
        )

    # ===== 3. 排序 + 去重 =====
    # 冷启动时（无任何筛选条件），优先按销量+评分综合排序，增加差异化
    if not has_any_filter:
        # 综合得分 = 销量排名分 + 评分分，先按综合得分排序
        scored_products.sort(key=lambda x: (x.get("sales_count", 0) * 0.01 + x.get("rating", 0) * 20), reverse=True)
        # 同类别最多2件，避免重复
        seen_subcategories = {}
        deduped = []
        for p in scored_products:
            sub = p.get("subcategory", "")
            if seen_subcategories.get(sub, 0) < 2:
                deduped.append(p)
                seen_subcategories[sub] = seen_subcategories.get(sub, 0) + 1
        scored_products = deduped
    else:
        scored_products.sort(key=lambda x: x["_score"], reverse=True)

    top_products = scored_products[:top_k]

    # ===== 4. 格式化输出 =====
    scene_desc = f"，{scene}" if scene else ""
    recipient_desc = f"送{recipient}" if recipient else ""
    budget_desc = f"，预算¥{budget}以内" if budget else ""

    header = f"为您推荐{recipient_desc}{scene_desc}{budget_desc}的商品（共{len(top_products)}件）：\n"

    lines = []
    for i, p in enumerate(top_products, 1):
        price_str = f"¥{p['price']:.1f}"
        sale_tag = " 🔥特价" if p.get("is_on_sale") else ""
        rating_star = "⭐" * int(p.get("rating", 0))
        tags_str = "、".join(p.get("tags", [])[:3])

        lines.append(
            f"{i}. {p['name']} {price_str}{sale_tag}\n"
            f"   评分：{rating_star} {p.get('rating', 0)}｜销量：{p.get('sales_count', 0)}\n"
            f"   特点：{tags_str}\n"
            f"   尺码：{'/'.join(p.get('sizes', []))}｜颜色：{'、'.join(p.get('colors', []))}"
        )

    return header + "\n\n".join(lines)