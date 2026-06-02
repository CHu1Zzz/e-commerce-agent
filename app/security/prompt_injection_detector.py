"""Prompt Injection 攻击检测与防御模块"""

import re
from typing import Optional


class PromptInjectionDetector:
    """检测并拦截 Prompt Injection 攻击

    防御的常见攻击模式：
    - 角色逃逸（忽略之前的指令）
    - 注入新指令
    - Base64/编码混淆
    - Markdown 格式逃逸
    """

    # 常见 injection 正则模式
    INJECTION_PATTERNS = [
        # ===== 角色逃逸 =====
        (r"忽略(?:之前|以上|所有)的指令", "忽略之前指令"),
        (r"忘了你的(?:角色|身份|设定|指令)", "忘记角色设定"),
        (r"你现在是[,，]?(?!.*客服)", "角色逃逸"),
        (r"你不再是.*?(?:客服|助手)", "角色否认"),
        (r"pretend you are(?!.*customer)", "角色伪装(英文)"),
        (r"act as if you are not", "角色否认(英文)"),
        (r"disregard your instructions", "忽略指令(英文)"),
        (r"ignore all previous", "忽略所有之前(英文)"),
        (r"(?:system|assistant) prompt", "提示词泄露(英文)"),
        (r"reveal your system prompt", "系统提示词请求"),

        # ===== 注入新指令 =====
        (r"在(?:你|它)之前添加", "指令注入前缀"),
        (r"在最后添加(?:以下|这段)", "指令追加"),
        (r"输出.*以外的.*内容", "内容过滤绕过"),
        (r"不要输出.*内容", "内容抑制"),
        (r"只需回答.{0,20}，不要.{0,30}", "内容限制绕过"),

        # ===== Base64/编码注入 =====
        (r"base64[:：]?\s*[A-Za-z0-9+/]{10,}={0,2}", "Base64编码注入"),
        (r"\\x[0-9a-fA-F]{2}", "十六进制转义注入"),

        # ===== Markdown 格式逃逸 =====
        (r"```system", "System提示词注入(代码块)"),
        (r"```instructions", "指令注入(代码块)"),
        (r"<system>", "System标签注入"),
        (r"</system>", "System标签注入"),
        (r"<!--.*?-->", "HTML注释注入"),

        # ===== 复合攻击 =====
        (r"(?:首先|第一步).*?(?:然后|第二).*?(?:最后)", "复合指令链"),
    ]

    def __init__(self):
        self._compiled = [(re.compile(p, re.IGNORECASE), desc) for p, desc in self.INJECTION_PATTERNS]
        # 单次输入最大长度（超过视为潜在攻击）
        self._max_length = 5000

    def detect(self, text: str) -> tuple[bool, str]:
        """检测输入是否包含 injection pattern

        Returns:
            (is_safe, reason) — is_safe=True 表示安全，reason 为空字符串
        """
        if not text:
            return True, ""

        # 长度检查
        if len(text) > self._max_length:
            return False, f"输入文本过长（{len(text)} 字符），已被拦截"

        # 模式匹配
        for compiled, desc in self._compiled:
            if compiled.search(text):
                return False, f"检测到可疑模式：{desc}"

        return True, ""

    def sanitize(self, text: str) -> str:
        """对输入进行清洗，移除 injection 标记"""
        result = text

        # 移除 system/assistant 相关的代码块
        result = re.sub(r"```system[\s\S]*?```", "", result, flags=re.IGNORECASE)
        result = re.sub(r"```instructions[\s\S]*?```", "", result, flags=re.IGNORECASE)
        result = re.sub(r"<system>[\s\S]*?</system>", "", result, flags=re.IGNORECASE)

        # 移除 HTML 注释
        result = re.sub(r"<!--[\s\S]*?-->", "", result)

        return result.strip()

    def is_safe(self, text: str) -> bool:
        """快捷方法：判断文本是否安全"""
        is_safe, _ = self.detect(text)
        return is_safe


# 全局单例
_detector: Optional[PromptInjectionDetector] = None


def get_detector() -> PromptInjectionDetector:
    global _detector
    if _detector is None:
        _detector = PromptInjectionDetector()
    return _detector


def check_injection(text: str) -> tuple[bool, str]:
    """便捷函数：检测 Prompt Injection"""
    return get_detector().detect(text)


def sanitize_input(text: str) -> str:
    """便捷函数：清洗输入"""
    return get_detector().sanitize(text)