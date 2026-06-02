"""PII 信息脱敏模块 — 对用户输入和 LLM 输出中的敏感信息进行脱敏"""

import re
from typing import Optional


class PIIScrubber:
    """PII（个人身份信息）脱敏工具

    支持脱敏的类型：
    - 手机号（国内手机号、固话、国际电话）
    - 身份证号
    - 银行卡号
    - 电子邮箱
    - 详细地址（只保留省市区）
    """

    def __init__(self):
        self._patterns = self._build_patterns()

    def _build_patterns(self) -> dict[str, list[tuple[str, bool]]]:
        """构建脱敏正则模式
        Returns: list of (pattern, is_reversible)
        """
        return {
            # 手机号：138****5678（保留前3后4）
            "phone": [
                (r"1[3-9]\d(\d{4})(\d{4})", True),  # 1[3-9]xxxxxxxx → 1[3-9]****xxxx
                (r"\+?86[- ]?1[3-9]\d[- ]?\d{4}[- ]?\d{4}", True),
                (r"\d{3,4}-?\d{7,8}", False),  # 固话：010-12345678
            ],
            # 身份证：110101**********1234（保留前6后4）
            "id_card": [
                (r"\d{6}(\d{8})\d{4}", True),  # 18位：保留出生日期前后
                (r"\d{15}", True),  # 15位
            ],
            # 银行卡：6222****1234（保留前4后4）
            "bank_card": [
                (r"\d{13,19}", True),
            ],
            # 邮箱：ani****@***m.com（保留首尾）
            "email": [
                (r"([a-zA-Z0-9._%+-]{3})[a-zA-Z0-9._%+-]*@([a-zA-Z0-9.-]{3})\.[a-zA-Z]{2,}", True),
            ],
            # 中文地址：只保留省市区，详细门牌号脱敏
            "address": [
                (r"((?:[一-龥]+(?:省|市|区|县)){1,2}(?:[一-龥]+区)?)([一-龥]+(?:街|路|弄|号|栋|单元|室).*)", True),
                # 检测完整地址关键词
                (r"[一-龥]+\d+号(?:[一-龥]?\d+号)?.*", False),
            ],
        }

    def redact(self, text: str) -> str:
        """对文本中所有已知的 PII 进行脱敏处理（ReDoS 安全版本）"""
        if not text:
            return text

        # 输入长度上限，防止 ReDoS
        if len(text) > 5000:
            text = text[:5000]

        result = text

        # 手机号：138****5678（保留前3后4）
        result = re.sub(
            r"1[3-9]\d{1}(\d{4})(\d{4})",
            lambda m: f"{m.group()[:3]}****{m.group(2)}",
            result,
        )
        result = re.sub(
            r"\+?86[- ]?1[3-9][- ]?\d{4}[- ]?\d{4}",
            lambda m: re.sub(
                r"1[3-9]\d{4}\d{4}",
                lambda x: f"{x.group()[:3]}****{x.group()[-4:]}",
                m.group(),
            ),
            result,
        )
        # 固话（精确匹配，防回溯）
        result = re.sub(r"\d{3,4}-?\d{7,8}", "***-*******", result)

        # 身份证脱敏：前6后4保留，中间脱敏（18位，精确量词防回溯）
        result = re.sub(
            r"(\d{6})\d{8}(\d{4})",
            r"\1********\2",
            result,
        )
        # 15位身份证
        result = re.sub(r"(\d{6})\d{5}(\d{4})", r"\1*****\2", result)

        # 银行卡脱敏（保留前4后4，精确量词）
        result = re.sub(
            r"\b(\d{4})\d{5,11}(\d{4})\b",
            lambda m: f"{m.group(1)}****{m.group(2)}",
            result,
        )

        # 邮箱脱敏（ possessive-like：前缀3字符 + @ + 域名头3 + TLD）
        result = re.sub(
            r"([a-zA-Z0-9._%+-]{3})[a-zA-Z0-9._%-]+@([a-zA-Z0-9.-]{1,3})\.[a-zA-Z]{2,}",
            lambda m: f"{m.group(1)}***@{m.group(2)[:3]}***",
            result,
        )

        # 地址脱敏（省市区保留，精确匹配门牌号，防回溯）
        # 模式1：省/市/区 + 具体地址
        result = re.sub(
            r"((?:[一-龥]+(?:省|市|区|县)){1,2})(?:[一-龥]+(?:街|路|弄|号|栋|单元|室))[一-龥\d]*",
            r"\1[详细地址已脱敏]",
            result,
        )
        # 模式2：含数字门牌号的地址（如"xx路88号"）
        result = re.sub(
            r"([一-龥]+\d+号)(?:[一-龥\d]*)?",
            r"\1[详细信息已脱敏]",
            result,
        )

        return result

    def check(self, text: str) -> list[dict]:
        """检测文本中包含的 PII 类型和位置"""
        findings = []
        if not text:
            return findings

        patterns = [
            ("phone", r"1[3-9]\d{9}"),
            ("id_card", r"\d{17}[\dXx]"),
            ("bank_card", r"\d{13,19}"),
            ("email", r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
        ]

        for pii_type, pattern in patterns:
            for m in re.finditer(pattern, text):
                findings.append({
                    "type": pii_type,
                    "value": m.group(),
                    "start": m.start(),
                    "end": m.end(),
                })

        return findings

    def contains_pii(self, text: str) -> bool:
        """快速检查文本是否包含 PII"""
        return len(self.check(text)) > 0


# 全局单例（延迟初始化）
_scrubber: Optional[PIIScrubber] = None


def get_scrubber() -> PIIScrubber:
    global _scrubber
    if _scrubber is None:
        _scrubber = PIIScrubber()
    return _scrubber


def redact_pii(text: str) -> str:
    """便捷函数：对文本进行 PII 脱敏"""
    return get_scrubber().redact(text)