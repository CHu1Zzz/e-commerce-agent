"""LLM 幻觉检测模块 — 校验 LLM 输出与工具返回数据的一致性"""

import re
from typing import Optional


class HallucinationDetector:
    """检测 LLM 回复中的幻觉内容

    核心逻辑：关键事实类信息（订单号、金额、日期、运单号等）
    必须在工具返回的原始数据中存在，LLM 不得自行编造。
    """

    def __init__(self):
        self._critical_patterns = {
            "order_id": re.compile(r"ORD-\d{8}-\d{3}"),
            "tracking_number": re.compile(r"(?:SF|ZT|JD|YD)\d{10,}"),
            "amount": re.compile(r"¥?\d+\.?\d{0,2}"),
            "date": re.compile(r"\d{4}[-/]\d{2}[-/]\d{2}|\d{4}年\d{1,2}月\d{1,2}日"),
            "phone": re.compile(r"1[3-9]\d{9}"),
        }

    def check(self, llm_output: str, tool_result: str) -> dict:
        """比对 LLM 输出和工具返回是否一致

        Args:
            llm_output: LLM 生成的回复文本
            tool_result: 工具返回的原始数据（通常是对话框形式的纯文本）

        Returns:
            {
                "is_consistent": bool,
                "conflicts": list[str],
                "checked_fields": dict
            }
        """
        conflicts = []
        checked_fields = {}

        # 检查订单号
        llm_order_ids = set(self._critical_patterns["order_id"].findall(llm_output))
        tool_order_ids = set(self._critical_patterns["order_id"].findall(tool_result))
        for oid in llm_order_ids:
            if oid not in tool_order_ids:
                conflicts.append(f"订单号 {oid} 在工具返回中未找到，可能为幻觉")
            else:
                checked_fields.setdefault("order_id", []).append({"value": oid, "consistent": True})

        # 检查运单号
        llm_tracking = set(self._critical_patterns["tracking_number"].findall(llm_output))
        tool_tracking = set(self._critical_patterns["tracking_number"].findall(tool_result))
        for tn in llm_tracking:
            if tn not in tool_tracking:
                conflicts.append(f"运单号 {tn} 在工具返回中未找到，可能为幻觉")
            else:
                checked_fields.setdefault("tracking_number", []).append({"value": tn, "consistent": True})

        # 检查金额（允许小数点后2位精度差）
        llm_amounts = set(self._critical_patterns["amount"].findall(llm_output))
        tool_amounts = [re.sub(r"¥", "", a) for a in self._critical_patterns["amount"].findall(tool_result)]
        for amt_str in llm_amounts:
            amt = re.sub(r"¥", "", amt_str)
            try:
                amt_float = float(amt)
                found = any(abs(amt_float - float(t)) < 0.01 for t in tool_amounts)
                if not found:
                    conflicts.append(f"金额 {amt_str} 在工具返回中未找到匹配")
                else:
                    checked_fields.setdefault("amount", []).append({"value": amt_str, "consistent": True})
            except ValueError:
                pass

        # 检查日期
        llm_dates = set(self._critical_patterns["date"].findall(llm_output))
        tool_dates = set(self._critical_patterns["date"].findall(tool_result))
        for d in llm_dates:
            if d not in tool_dates:
                conflicts.append(f"日期 {d} 在工具返回中未找到")

        return {
            "is_consistent": len(conflicts) == 0,
            "conflicts": conflicts,
            "checked_fields": checked_fields,
        }

    def validate_response(self, response: str, context: dict) -> str:
        """在返回用户前做最终校验，检测到冲突时返回安全降级回复

        Args:
            response: LLM 原始回复
            context: 包含 tool_used 和 tool_result 的上下文

        Returns:
            校验通过返回原回复，检测到冲突返回安全降级回复
        """
        if context.get("tool_used") and context.get("tool_result"):
            check = self.check(response, context["tool_result"])
            if not check["is_consistent"]:
                return (
                    "抱歉，我在核对信息时发现了一些不一致，"
                    "为了确保准确，建议您联系人工客服确认详情。"
                )

        return response


# 全局单例
_detector: Optional[HallucinationDetector] = None


def get_detector() -> HallucinationDetector:
    global _detector
    if _detector is None:
        _detector = HallucinationDetector()
    return _detector


def check_hallucination(llm_output: str, tool_result: str) -> dict:
    """便捷函数：检查幻觉"""
    return get_detector().check(llm_output, tool_result)


def validate_response(response: str, context: dict) -> str:
    """便捷函数：验证并可能降级回复"""
    return get_detector().validate_response(response, context)