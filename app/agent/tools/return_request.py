"""退换货申请 Tool"""

import json
import logging
import sys
import threading
from datetime import datetime
from pathlib import Path

from langchain_core.tools import tool

from app.security.pii_scrubber import PIIScrubber

_APP_DIR = Path(sys.modules["app"].__file__).parent
DATA_DIR = _APP_DIR / "data"
ORDERS_FILE = DATA_DIR / "mock_orders.json"
TICKETS_FILE = DATA_DIR / "return_tickets.json"

# 文件锁（防止 TOCTOU 竞态）
_ticket_lock = threading.Lock()

# 专用 logger
_logger = logging.getLogger("app.tools.return_request")


def _load_orders() -> list[dict]:
    """加载模拟订单数据"""
    with open(ORDERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_ticket(ticket: dict) -> None:
    """保存退换货工单（线程安全 + PII 脱敏）"""
    # 先对 reason 做 PII 脱敏再存储
    scrubber = PIIScrubber()
    if ticket.get("reason"):
        ticket["reason"] = scrubber.redact(ticket["reason"])

    with _ticket_lock:
        tickets = []
        if TICKETS_FILE.exists():
            with open(TICKETS_FILE, "r", encoding="utf-8") as f:
                tickets = json.load(f)
        tickets.append(ticket)
        with open(TICKETS_FILE, "w", encoding="utf-8") as f:
            json.dump(tickets, f, ensure_ascii=False, indent=2)
    _logger.info("Ticket saved: %s for order %s", ticket["ticket_id"], ticket["order_id"])


# 退换货时限（天）
RETURN_WINDOW_DAYS = 7


@tool
def submit_return_request(
    order_id: str,
    return_type: str,
    reason: str,
) -> str:
    """提交退换货申请。会自动校验订单是否在退换货时效内，并生成工单。

    Args:
        order_id: 订单号，格式如 ORD-20260530-001
        return_type: 退换货类型，"return" 表示退货，"exchange" 表示换货
        reason: 退换货原因，如"尺码不合适"、"质量问题"、"不想要了"等
    """
    orders = _load_orders()

    # 查找订单
    order = None
    for o in orders:
        if o["order_id"] == order_id:
            order = o
            break

    if not order:
        return f"未找到订单 {order_id}，请核实订单号是否正确。"

    # 校验订单状态：只有已签收的订单可以退换
    if order["status"] != "delivered":
        status_map = {
            "pending": "待发货",
            "shipped": "已发货",
            "returning": "退货中",
            "cancelled": "已取消",
        }
        status_cn = status_map.get(order["status"], order["status"])
        return f"订单 {order_id} 当前状态为「{status_cn}」，仅已签收的订单可申请退换货。"

    # 校验退换货时效
    order_time = datetime.fromisoformat(order["created_at"])
    now = datetime.now()
    days_passed = (now - order_time).days

    if days_passed > RETURN_WINDOW_DAYS:
        return f"订单 {order_id} 已签收超过 {RETURN_WINDOW_DAYS} 天，超出退换货时效，无法申请。"

    # 生成工单（整个ID生成+写入在锁内完成，防止并发碰撞）
    with _ticket_lock:
        existing_tickets = []
        if TICKETS_FILE.exists():
            with open(TICKETS_FILE, "r", encoding="utf-8") as f:
                existing_tickets = json.load(f)
        ticket_seq = len(existing_tickets) + 1
        ticket_id = f"RTN-{datetime.now().strftime('%Y%m%d')}-{ticket_seq:03d}"

        ticket = {
            "ticket_id": ticket_id,
            "order_id": order_id,
            "type": return_type,
            "reason": reason,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "return_address": "上海市闵行区退货仓（七宝镇xx路xx号）",
        }
        # PII脱敏在锁内完成，确保reason写入前已处理
        scrubber = PIIScrubber()
        if ticket.get("reason"):
            ticket["reason"] = scrubber.redact(ticket["reason"])
        existing_tickets.append(ticket)
        with open(TICKETS_FILE, "w", encoding="utf-8") as f:
            json.dump(existing_tickets, f, ensure_ascii=False, indent=2)
        _logger.info("Ticket saved: %s for order %s", ticket_id, order_id)

    type_cn = "退货" if return_type == "return" else "换货"
    items_desc = "、".join(item["name"] for item in order["items"])

    return (
        f"✅ {type_cn}申请已提交！\n"
        f"工单号：{ticket_id}\n"
        f"订单号：{order_id}\n"
        f"商品：{items_desc}\n"
        f"原因：{reason}\n"
        f"状态：待审核\n\n"
        f"📦 退货地址：{ticket['return_address']}\n"
        f"📌 注意事项：\n"
        f"  1. 请保持商品原包装、吊牌完好\n"
        f"  2. 请在7天内将商品寄回\n"
        f"  3. 退款将在仓库签收并检验后3个工作日内原路退回"
    )


def _load_tickets() -> list[dict]:
    """加载已有工单"""
    if not TICKETS_FILE.exists():
        return []
    with open(TICKETS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
