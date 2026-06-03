"""尺码推荐 Tool — 根据用户身高体重/尺码数据推荐合适尺码"""

import sys
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field


# 定位项目根目录
_APP_DIR = Path(sys.modules["app"].__file__).parent
DATA_DIR = _APP_DIR / "data"


# ===== 尺码表定义 =====
# T恤/衬衫尺码表：(身高下限, 胸围下限) → 尺码
TSHIRT_SIZE_CHART = [
    # (身高, 胸围, 尺码)
    (165, 84, "S"),
    (170, 88, "M"),
    (175, 92, "L"),
    (180, 96, "XL"),
    (185, 100, "XXL"),
]

# 裤子尺码表：(身高下限, 腰围下限) → 尺码
PANTS_SIZE_CHART = [
    # (身高, 腰围, 尺码)
    (165, 82, "L"),    # 175/82A
    (170, 84, "L"),
    (175, 86, "XL"),
    (180, 90, "XXL"),
    (185, 94, "XXL"),
]

# 鞋子尺码表（脚长cm → 欧码）
SHOES_SIZE_CHART = [
    # (脚长下限, 欧码)
    (22.0, 35),
    (23.0, 37),
    (24.0, 38),
    (25.0, 39),
    (26.0, 40),
    (27.0, 41),
    (28.0, 42),
    (29.0, 43),
    (30.0, 44),
    (31.0, 45),
]


def _recommend_tshirt_size(height_cm: float, chest_cm: Optional[float] = None) -> str:
    """根据身高（和胸围）推荐T恤尺码"""
    size = "M"  # 默认
    for h_min, c_min, size_label in TSHIRT_SIZE_CHART:
        if height_cm >= h_min:
            size = size_label
            # 如果提供了胸围，进一步精确匹配
            if chest_cm and chest_cm >= c_min:
                return size_label
    return size


def _recommend_pants_size(height_cm: float, waist_cm: Optional[float] = None) -> str:
    """根据身高（和腰围）推荐裤子尺码"""
    size = "L"  # 默认
    for h_min, w_min, size_label in PANTS_SIZE_CHART:
        if height_cm >= h_min:
            size = size_label
            if waist_cm and waist_cm >= w_min:
                return size_label
    return size


def _recommend_shoes_size(foot_length_cm: float) -> str:
    """根据脚长推荐鞋码（返回欧码）"""
    size = 42  # 默认
    for fl_min, size_label in SHOES_SIZE_CHART:
        if foot_length_cm >= fl_min:
            size = size_label
    return f"欧码 {size}（脚长 {foot_length_cm:.1f}cm）"


def _get_size_guide_text(product_type: str) -> str:
    """返回尺码表文本说明"""
    if product_type in ("tshirt", "shirt", "T恤", "衬衫"):
        lines = ["【T恤/衬衫尺码参考】",
                 "S=165/84A（身高165cm左右，胸围84cm）",
                 "M=170/88A（身高170cm左右，胸围88cm）",
                 "L=175/92A（身高175cm左右，胸围92cm）",
                 "XL=180/96A（身高180cm左右，胸围96cm）",
                 "XXL=185/100A（身高185cm左右，胸围100cm）",
                 "⚠️ 注意：T恤版型偏大，建议选小一码"]
    elif product_type in ("pants", "裤子", "休闲裤", "运动裤"):
        lines = ["【裤子/运动裤尺码参考】",
                 "L=175/82A（腰围82cm，臀围100cm）",
                 "XL=180/86A（腰围86cm，臀围104cm）",
                 "XXL=185/90A（腰围90cm，臀围108cm）",
                 "⚠️ 运动裤弹性好，可选正常尺码，介于两码之间建议选大码"]
    elif product_type in ("shoes", "鞋", "运动鞋", "童鞋"):
        lines = ["【鞋码参考（欧码）】",
                 "35码≈22.0cm脚长",
                 "37码≈23.0cm脚长",
                 "38码≈24.0cm脚长",
                 "39码≈25.0cm脚长",
                 "40码≈26.0cm脚长",
                 "41码≈27.0cm脚长",
                 "42码≈28.0cm脚长",
                 "43码≈29.0cm脚长",
                 "44码≈30.0cm脚长",
                 "45码≈31.0cm脚长",
                 "📏 测量方法：下午站立测量，脚后跟到最长脚趾的距离"]
    else:
        lines = ["【通用尺码参考】",
                 "请告诉我您的身高、体重、腰围或脚长，我帮您推荐"]
    return "\n".join(lines)


class SizeRecommendationInput(BaseModel):
    """尺码推荐输入参数"""

    product_type: str = Field(
        description="商品类型或用户想买的品类，如 'T恤'、'裤子'、'运动鞋'、'衬衫'",
        min_length=1,
        max_length=50,
    )
    height_cm: Optional[float] = Field(
        default=None,
        ge=50,
        le=250,
        description="身高（厘米），如 175",
    )
    weight_kg: Optional[float] = Field(
        default=None,
        ge=20,
        le=300,
        description="体重（千克），如 70",
    )
    chest_cm: Optional[float] = Field(
        default=None,
        ge=50,
        le=200,
        description="胸围（厘米），如 92",
    )
    waist_cm: Optional[float] = Field(
        default=None,
        ge=50,
        le=200,
        description="腰围（厘米），如 82",
    )
    foot_length_cm: Optional[float] = Field(
        default=None,
        ge=15,
        le=40,
        description="脚长（厘米），用于鞋码推荐，如 27.5",
    )
    user_profile: Optional[str] = Field(
        default=None,
        description="用户自述的尺码情况，如 '我平时穿M码'、'我穿42的鞋'",
    )


@tool(args_schema=SizeRecommendationInput)
def size_recommend(
    product_type: str,
    height_cm: Optional[float] = None,
    weight_kg: Optional[float] = None,
    chest_cm: Optional[float] = None,
    waist_cm: Optional[float] = None,
    foot_length_cm: Optional[float] = None,
    user_profile: Optional[str] = None,
) -> str:
    """根据用户提供的体型数据，推荐合适的尺码。

    适用于：
    - 用户问"这件衣服选什么码"、"我穿多大码"
    - 用户说"我身高175，体重70公斤" → 推荐T恤/裤子尺码
    - 用户说"我脚长27cm" → 推荐鞋码
    - 用户说"我平时穿M码" → 分析后给出建议

    测量数据越完整，推荐越准确。
    如果用户只提供身高，可以给出一个参考范围。

    Args:
        product_type: 商品类型（T恤/裤子/运动鞋/衬衫/连衣裙等）
        height_cm: 身高（厘米）
        weight_kg: 体重（千克）
        chest_cm: 胸围（厘米）
        waist_cm: 腰围（厘米）
        foot_length_cm: 脚长（厘米，用于鞋码）
        user_profile: 用户自述的尺码情况
    """
    product_type_lower = product_type.lower()

    # ===== 1. 如果用户提供了自述尺码，尝试解析 =====
    if user_profile and not height_cm:
        # 尝试从用户描述中提取尺码信息（简单关键词匹配）
        profile_lower = user_profile.lower()
        # 这里可以让 LLM 在调用工具前就解析好，tool 层做容错
        pass

    # ===== 2. 无测量数据时，返回尺码表 =====
    has_body_data = any([height_cm, chest_cm, waist_cm, foot_length_cm])
    if not has_body_data and not user_profile:
        return (
            f"要给您推荐尺码，我需要了解您的体型数据哦~\n"
            f"请告诉我：\n"
            f"  • 身高（厘米）：如 175\n"
            f"  • 体重（可选）：如 70\n"
            f"  • 腰围（可选）：如 82（买裤子时建议提供）\n"
            f"  • 脚长（可选）：如 27.5cm（买鞋时需要）\n\n"
            f"{_get_size_guide_text(product_type_lower)}"
        )

    # ===== 3. 生成推荐 =====
    # 精确匹配模式：用户指定了具体品类时，只返回该品类
    is_explicit_pants = any(w in product_type_lower for w in ["裤子", "pants", "运动裤", "休闲裤", "裙裤"])
    is_explicit_shoes = any(w in product_type_lower for w in ["鞋", "shoes", "运动鞋", "童鞋", "靴"])
    is_explicit_tshirt = any(w in product_type_lower for w in ["t恤", "t-shirt", "衬衫", "shirt", "上衣", "T恤"])
    is_explicit_dress = "连衣裙" in product_type_lower

    lines = []

    # 鞋码推荐
    if foot_length_cm and (is_explicit_shoes or not is_explicit_pants and not is_explicit_tshirt and not is_explicit_dress):
        shoes_recommendation = _recommend_shoes_size(foot_length_cm)
        lines.append(f"👟 鞋码推荐：{shoes_recommendation}")
        if foot_length_cm < 25:
            lines.append("（您测量的是童鞋尺码范围）")

    # T恤/衬衫推荐（仅当用户明确询问上衣类或未指定具体品类时）
    if height_cm and is_explicit_tshirt and not is_explicit_pants and not is_explicit_shoes and not is_explicit_dress:
        tshirt_size = _recommend_tshirt_size(height_cm, chest_cm)
        lines.append(f"👕 {product_type}尺码推荐：{tshirt_size}（基于身高{height_cm}cm）")
        lines.append("⚠️ 注意：该品类版型偏大，建议选小一码")

    # 裤子推荐（仅当用户明确询问裤子或未指定具体品类时）
    if height_cm and is_explicit_pants and not is_explicit_shoes and not is_explicit_tshirt and not is_explicit_dress:
        pants_size = _recommend_pants_size(height_cm, waist_cm)
        waist_str = f"、腰围{waist_cm}cm" if waist_cm else ""
        lines.append(f"👖 {product_type}尺码推荐：{pants_size}（基于身高{height_cm}cm{waist_str}）")
        lines.append("💡 裤子尺码建议：运动裤弹性好，可选正常尺码或选大一号")

    # 连衣裙推荐
    if height_cm and is_explicit_dress and not is_explicit_shoes:
        if height_cm < 160:
            dr_size = "S"
        elif height_cm < 165:
            dr_size = "M"
        elif height_cm < 170:
            dr_size = "L"
        elif height_cm < 175:
            dr_size = "XL"
        else:
            dr_size = "XXL"
        lines.append(f"👗 连衣裙尺码推荐：{dr_size}（基于身高{height_cm}cm）")

    # 通用（只有身高，无特定品类，或品类宽泛）
    if not lines and height_cm:
        tshirt_size = _recommend_tshirt_size(height_cm)
        pants_size = _recommend_pants_size(height_cm)
        lines.append(f"基于您的身高{height_cm}cm，建议尺码范围：")
        lines.append(f"  • T恤/衬衫：{tshirt_size}码")
        lines.append(f"  • 裤子：{pants_size}码")
        lines.append("（数据越完整，推荐越准确）")

    # 只有 user_profile 的情况
    if not lines and user_profile:
        lines.append(f"您提到您的情况：{user_profile}")
        lines.append(f"建议您参考以下尺码表：\n{_get_size_guide_text(product_type_lower)}")

    if not lines:
        return (
            f"抱歉，我暂时无法根据您提供的信息推荐{product_type}的尺码，"
            f"请提供更完整的体型数据（身高、体重、腰围等）。\n\n"
            f"{_get_size_guide_text(product_type_lower)}"
        )

    return "\n".join(lines)