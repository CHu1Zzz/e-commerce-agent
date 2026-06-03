"""向量数据库初始化脚本 — 向 ChromaDB 写入商品知识库测试数据"""

import os
import sys
from pathlib import Path

# 将项目根目录加入 Python 路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import chromadb
from dotenv import load_dotenv

load_dotenv()

COLLECTION_NAME = "ecommerce_products"


def get_product_docs() -> list[dict]:
    """生成商品知识库文档（13 条测试数据）"""
    return [
        # ===== 商品描述 =====
        {
            "id": "prod_001",
            "content": (
                "纯棉短袖T恤｜产品名称：纯棉短袖T恤｜"
                "面料：100%棉｜厚度：适中｜适合季节：春夏秋｜"
                "洗涤建议：30°C温水手洗，不可漂白，不可滚筒烘干｜"
                "尺码偏大一码，建议选小一码｜"
                "颜色：白/黑/灰/藏青可选｜"
                "版型：标准版型，适合日常休闲穿着"
            ),
            "metadata": {"category": "clothing", "product_id": "PRD-101", "doc_type": "product_desc"},
        },
        {
            "id": "prod_002",
            "content": (
                "运动休闲裤｜面料：聚酯纤维92%+氨纶8%｜"
                "特点：弹性好、透气、吸湿排汗、速干｜"
                "尺码：正常尺码，按身高体重对照尺码表选择｜"
                "适合场景：运动健身、日常休闲、户外徒步｜"
                "洗涤：可机洗，水温不超过40°C"
            ),
            "metadata": {"category": "clothing", "product_id": "PRD-202", "doc_type": "product_desc"},
        },
        {
            "id": "prod_003",
            "content": (
                "轻薄羽绒服｜品牌：时尚优品｜"
                "填充物：90%白鸭绒｜充绒量：150g（175/96A）｜"
                "特点：轻便保暖，可收纳成口袋｜适合温度：0°C至-10°C｜"
                "洗涤：不可水洗，建议专业干洗｜"
                "颜色：藏青/黑/白｜尺码：S/M/L/XL/XXL可选"
            ),
            "metadata": {"category": "clothing", "product_id": "PRD-404", "doc_type": "product_desc"},
        },
        {
            "id": "prod_004",
            "content": (
                "真丝连衣裙｜面料：100%桑蚕丝｜"
                "特点：柔软光滑、透气、优雅飘逸｜"
                "洗涤：冷水手洗、反面晾晒、不可机洗、不可漂白｜"
                "尺码：正常尺码，建议按身高选择｜"
                "适合场景：职场、商务、约会、正式场合"
            ),
            "metadata": {"category": "clothing", "product_id": "PRD-505", "doc_type": "product_desc"},
        },
        {
            "id": "prod_005",
            "content": (
                "儿童运动鞋｜材质：网面+合成革｜"
                "鞋底：EVA缓震鞋底，防滑耐磨｜"
                "尺码：标准童码，参考尺码表按脚长选择（脚长+0.5cm）｜"
                "适合：日常运动、跑步、户外活动｜"
                "洗涤：温水手洗，忌长时间浸泡"
            ),
            "metadata": {"category": "shoes", "product_id": "PRD-606", "doc_type": "product_desc"},
        },
        # ===== 尺码指南 =====
        {
            "id": "size_001",
            "content": (
                "T恤尺码指南｜"
                "S=165/84A（适合身高165cm左右，胸围84cm左右）｜"
                "M=170/88A（适合身高170cm左右，胸围88cm左右）｜"
                "L=175/92A（适合身高175cm左右，胸围92cm左右）｜"
                "XL=180/96A（适合身高180cm左右，胸围96cm左右）｜"
                "XXL=185/100A（适合身高185cm左右，胸围100cm左右）｜"
                "注意：T恤版型偏大，M码适合标准体型170cm男性"
            ),
            "metadata": {"category": "clothing", "doc_type": "size_guide"},
        },
        {
            "id": "size_002",
            "content": (
                "裤子/运动裤尺码指南｜"
                "L=175/82A（腰围82cm，臀围100cm）｜"
                "XL=180/86A（腰围86cm，臀围104cm）｜"
                "XXL=185/90A（腰围90cm，臀围108cm）｜"
                "运动裤弹性好，可选正常尺码｜"
                "如介于两个尺码之间，建议选大码"
            ),
            "metadata": {"category": "clothing", "doc_type": "size_guide"},
        },
        # ===== 退换货政策 =====
        {
            "id": "policy_001",
            "content": (
                "退换货政策（签收后7天）｜"
                "签收后7天内可申请退换货，超出7天不予处理｜"
                "商品需保持原包装、吊牌完好，不影响二次销售｜"
                "贴身衣物（内衣、内裤、泳衣、丝袜等）不支持7天无理由退换｜"
                "因质量问题退换货，运费由商家承担｜"
                "请在退换货申请通过后7天内将商品寄回"
            ),
            "metadata": {"category": "policy", "doc_type": "return_policy"},
        },
        {
            "id": "policy_002",
            "content": (
                "退款到账时间｜"
                "仓库签收并检验确认后3个工作日内原路退回｜"
                "支付方式为银行卡退至银行卡，微信退至微信零钱，支付宝退至余额｜"
                "如超过7个工作日未到账，请联系人工客服查询"
            ),
            "metadata": {"category": "policy", "doc_type": "refund_policy"},
        },
        # ===== 发货与物流 =====
        {
            "id": "logistics_001",
            "content": (
                "发货时间规则｜"
                "下单后24小时内发货，节假日（春节、国庆等）期间可能顺延1-2天｜"
                "预售商品以商品详情页标注的发货时间为准，预售结束后3-7个工作日发货｜"
                "当天15:00前的订单当日发出，15:00后的订单次日发出｜"
                "可进入「我的订单」查看实时发货状态"
            ),
            "metadata": {"category": "logistics", "doc_type": "shipping_policy"},
        },
        {
            "id": "logistics_002",
            "content": (
                "运费政策｜"
                "单笔订单满99元免运费（新疆、西藏、宁夏、青海、内蒙古加收15元）｜"
                "未满99元收取8元运费｜"
                "港澳台地区按实际运费收取，海外暂不支持发货｜"
                "部分大件商品（如羽绒服、行李箱）可能收取额外运费，详情见商品页"
            ),
            "metadata": {"category": "logistics", "doc_type": "shipping_fee"},
        },
        # ===== 支付与会员 =====
        {
            "id": "payment_001",
            "content": (
                "支付方式｜"
                "支持微信支付、支付宝、信用卡（Visa/MasterCard）、花呗分期（3/6/12期）｜"
                "不支持货到付款｜"
                "企业用户可申请对公转账（需联系客服开通）｜"
                "如支付失败，请检查账户余额或绑定银行卡是否有效"
            ),
            "metadata": {"category": "payment", "doc_type": "payment_methods"},
        },
        {
            "id": "member_001",
            "content": (
                "会员权益体系｜"
                "银卡会员（注册即享）：全场9.5折｜"
                "金卡会员（累计消费满500元）：全场9折，生日当月双倍积分｜"
                "钻石卡会员（累计消费满2000元）：全场8.5折，生日当月双倍积分，专属客服｜"
                "积分可兑换优惠券（100积分=1元）｜"
                "会员升级后权益立即生效，终身有效"
            ),
            "metadata": {"category": "member", "doc_type": "membership"},
        },
        {
            "id": "coupon_001",
            "content": (
                "优惠券使用规则｜"
                "每笔订单限用1张优惠券，不可叠加使用｜"
                "优惠券需在有效期内使用，过期自动失效｜"
                "部分特价商品、秒杀商品不参与任何优惠｜"
                "优惠券一旦使用不支持退回，如取消订单优惠券不返还｜"
                "新人专享券仅限注册7天内未下单用户使用"
            ),
            "metadata": {"category": "payment", "doc_type": "coupon_policy"},
        },
    ]


def init_chroma(persist_dir: str = None):
    """初始化 ChromaDB 向量数据库"""
    if persist_dir is None:
        # 项目根目录下的 app/data/chroma_db
        app_dir = PROJECT_ROOT / "app"
        persist_dir = str(app_dir / "data" / "chroma_db")

    persist_path = Path(persist_dir)
    persist_path.mkdir(parents=True, exist_ok=True)

    print(f"ChromaDB 持久化路径: {persist_path}")

    # 创建客户端
    client = chromadb.PersistentClient(path=str(persist_path))

    # 删除旧 collection（如果存在）以确保干净初始化
    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"✓ 已删除旧 collection: {COLLECTION_NAME}")
    except Exception:
        pass

    # 创建新 collection
    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "电商商品知识库"},
    )
    print(f"✓ 已创建 collection: {COLLECTION_NAME}")

    # 初始化 embedding 模型
    # 使用本地 sentence-transformers 模型（all-MiniLM-L6-v2）
    # 避免依赖 MiniMax embedding API（需要 GROUP_ID）
    try:
        from langchain_core.embeddings import Embeddings

        class LocalEmbeddings(Embeddings):
            """本地 sentence-transformers embeddings"""

            def __init__(self):
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer("all-MiniLM-L6-v2")

            def embed_documents(self, texts: list[str], **kwargs) -> list[list[float]]:
                return self.model.encode(texts, normalize_embeddings=True).tolist()

            def embed_query(self, text: str) -> list[float]:
                return self.model.encode([text], normalize_embeddings=True)[0].tolist()

        embeddings = LocalEmbeddings()
    except Exception as e:
        print(f"Embedding 模型初始化失败: {e}")
        return

    docs = get_product_docs()
    print(f"开始为 {len(docs)} 条文档生成向量...")

    # 批量生成 embedding 并写入
    for i, doc in enumerate(docs):
        vec = embeddings.embed_query(doc["content"])
        collection.add(
            ids=[doc["id"]],
            documents=[doc["content"]],
            metadatas=[doc["metadata"]],
            embeddings=[vec],
        )
        print(f"  [{i+1}/{len(docs)}] {doc['id']} — {doc['metadata']['doc_type']}")

    print(f"\n✅ 向量数据库初始化完成！")
    print(f"   Collection: {COLLECTION_NAME}")
    print(f"   文档数量: {len(docs)} 条")
    print(f"   路径: {persist_path}")
    print(f"\n文档类型分布:")
    doc_types = {}
    for d in docs:
        dt = d["metadata"]["doc_type"]
        doc_types[dt] = doc_types.get(dt, 0) + 1
    for dt, cnt in doc_types.items():
        print(f"  - {dt}: {cnt} 条")


if __name__ == "__main__":
    init_chroma()