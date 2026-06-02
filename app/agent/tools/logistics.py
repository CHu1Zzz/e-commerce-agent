"""物流追踪 Tool"""

import json
import sys
from pathlib import Path

from langchain_core.tools import tool


_APP_DIR = Path(sys.modules["app"].__file__).parent
DATA_DIR = _APP_DIR / "data"
LOGISTICS_FILE = DATA_DIR / "mock_logistics.json"


def _load_logistics() -> list[dict]:
    """加载模拟物流数据"""
    with open(LOGISTICS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@tool
def track_logistics(order_id: str) -> str:
    """根据订单号查询物流轨迹和配送进度。

    Args:
        order_id: 订单号，格式如 ORD-20260530-001
    """
    logistics_list = _load_logistics()

    for logistics in logistics_list:
        if logistics["order_id"] == order_id:
            timeline_desc = "\n".join(
                f"  {node['time']}  {node['status']}（{node['location']}）"
                for node in logistics["timeline"]
            )
            tracking_info = (
                f"承运商：{logistics['carrier']}\n"
                f"运单号：{logistics['tracking_number'] or '暂无'}\n"
                f"预计送达：{logistics['estimated_delivery']}\n"
                f"物流轨迹：\n{timeline_desc}"
            )
            return tracking_info

    return f"未找到订单 {order_id} 的物流信息，请核实订单号是否正确。"
