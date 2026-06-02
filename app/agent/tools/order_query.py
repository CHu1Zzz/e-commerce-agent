"""订单查询 Tool"""

import json
import sys
from pathlib import Path

from langchain_core.tools import tool


# 定位项目根目录（ecommerce-cs-agent/app/）
_APP_DIR = Path(sys.modules["app"].__file__).parent
DATA_DIR = _APP_DIR / "data"
ORDERS_FILE = DATA_DIR / "mock_orders.json"


def _load_orders() -> list[dict]:
    """加载模拟订单数据"""
    with open(ORDERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# 订单状态中文映射
STATUS_MAP = {
    "pending": "待发货",
    "shipped": "已发货",
    "delivered": "已签收",
    "cancelled": "已取消",
    "returning": "退换货中",
}


@tool
def query_order(order_id: str) -> str:
    """根据订单号查询订单详情，包括商品信息、订单状态、金额等。

    Args:
        order_id: 订单号，格式如 ORD-20260530-001
    """
    orders = _load_orders()

    for order in orders:
        if order["order_id"] == order_id:
            status_cn = STATUS_MAP.get(order["status"], order["status"])
            items_desc = "\n".join(
                f"  - {item['name']}（{item['sku']}）× {item['quantity']}，单价 ¥{item['price']}"
                for item in order["items"]
            )
            return (
                f"订单号：{order['order_id']}\n"
                f"状态：{status_cn}\n"
                f"下单时间：{order['created_at']}\n"
                f"商品：\n{items_desc}\n"
                f"总金额：¥{order['total_amount']}\n"
                f"收货地址：{order['shipping_address']}"
            )

    return f"未找到订单 {order_id}，请核实订单号是否正确。"
