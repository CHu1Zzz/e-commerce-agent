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
        # 手机号：138****5678（保留前3后4）
        self._phone_patterns = [
            re.compile(r"1[3-9]\d{1}(\d{4})(\d{4})"),
            re.compile(r"\+?86[- ]?1[3-9]\d[- ]?\d{4}[- ]?\d{4}"),
            re.compile(r"\d{3,4}-?\d{7,8}"),
        ]
        # 身份证：前6后4保留，中间脱敏
        self._id_patterns = [
            re.compile(r"(\d{6})\d{8}(\d{4})"),
            re.compile(r"(\d{6})\d{5}(\d{4})"),
        ]
        # 银行卡：保留前4后4
        self._bank_patterns = [
            re.compile(r"\b(\d{4})\d{5,11}(\d{4})\b"),
        ]
        # 邮箱
        self._email_pattern = re.compile(
            r"([a-zA-Z0-9._%+-]{1,50})@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        )
        # 地址
        self._address_patterns = [
            re.compile(
                r"((?:[一-龥]+(?:省|市|区|县)){1,2})(?:[一-龥]+(?:街|路|弄|号|栋|单元|室))[一-龥\d]*"
            ),
            re.compile(r"([一-龥]+\d+号)(?:[一-龥\d]*)?$"),
        ]

    @staticmethod
    def _mask_email(local_part: str) -> str:
        """对邮箱本地部分脱敏，保留首尾各1字符，中间用*替代"""
        if len(local_part) <= 2:
            masked = "*" * len(local_part)
        else:
            masked = local_part[0] + "*" * (len(local_part) - 2) + local_part[-1]
        return f"{masked}@***"

    def redact(self, text: str) -> str:
        """对文本中所有已知的 PII 进行脱敏处理（ReDoS 安全版本）"""
        if not text:
            return text

        # 输入长度上限，防止 ReDoS
        if len(text) > 5000:
            text = text[:5000]

        result = text

        # 手机号：138****5678
        result = self._phone_patterns[0].sub(
            lambda m: f"{m.group()[:3]}****{m.group(2)}", result
        )
        result = self._phone_patterns[1].sub(
            lambda m: re.sub(
                r"1[3-9]\d{4}\d{4}",
                lambda x: f"{x.group()[:3]}****{x.group()[-4:]}",
                m.group(),
            ),
            result,
        )
        # 固话
        result = self._phone_patterns[2].sub("***-*******", result)

        # 身份证
        result = self._id_patterns[0].sub(r"\1********\2", result)
        result = self._id_patterns[1].sub(r"\1*****\2", result)

        # 银行卡
        result = self._bank_patterns[0].sub(
            lambda m: f"{m.group(1)}****{m.group(2)}", result
        )

        # 邮箱
        result = self._email_pattern.sub(
            lambda m: self._mask_email(m.group(1)), result
        )

        # 地址
        result = self._address_patterns[0].sub(r"\1[详细地址已脱敏]", result)
        result = self._address_patterns[1].sub(r"\1[详细信息已脱敏]", result)

        return result

    def check(self, text: str) -> list[dict]:
        """检测文本中包含的 PII 类型和位置"""
        findings = []
        if not text:
            return findings

        checks = [
            ("phone", re.compile(r"1[3-9]\d{9}")),
            ("id_card", re.compile(r"\d{17}[\dXx]")),
            ("bank_card", re.compile(r"\d{13,19}")),
            ("email", re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")),
        ]

        for pii_type, pattern in checks:
            for m in pattern.finditer(text):
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