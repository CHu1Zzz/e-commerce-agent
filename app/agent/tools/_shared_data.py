"""共享数据加载工具 — 带 LRU 缓存，所有 Tool 共享同一份数据"""
import json
import sys
from functools import lru_cache
from pathlib import Path


# 定位项目根目录
_APP_DIR = Path(sys.modules["app"].__file__).parent
DATA_DIR = _APP_DIR / "data"
PRODUCTS_FILE = DATA_DIR / "mock_products.json"
ORDERS_FILE = DATA_DIR / "mock_orders.json"
LOGISTICS_FILE = DATA_DIR / "mock_logistics.json"


@lru_cache(maxsize=1)
def load_products() -> list[dict]:
    """商品目录（缓存整个文件内容，进程生命周期内只读一次）"""
    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_orders() -> list[dict]:
    """订单数据（缓存整个文件内容）"""
    with open(ORDERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_logistics() -> list[dict]:
    """物流数据（缓存整个文件内容）"""
    with open(LOGISTICS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)