"""
敏感信息脱敏工具（P1：手机号 / 身份证号 / 银行卡号）

设计要点:
- 幂等: 掩码后的字符串不再匹配正则，可对同文本重复调用而不会二次处理。
- 顺序: 先身份证（18位），再手机号（11位），最后银行卡（16-19位），
  避免 18 位身份证被银行卡规则误命中。
- 掩码规则: 手机号保留前3后4；身份证保留前6后4；银行卡保留前4后4。
"""
import re

# 身份证：18位，末位可为 X/x，保留前6后4，掩中间8位
_ID_PATTERN = re.compile(r"(?<!\d)(\d{6})\d{8}(\d{3}[0-9Xx])(?!\d)")

# 手机号：1开头11位，保留前3后4，掩中间4位
_PHONE_PATTERN = re.compile(r"(?<!\d)(1[3-9]\d)\d{4}(\d{4})(?!\d)")

# 银行卡/借记卡：16-19位连续数字，保留前4后4，掩中间
_CARD_PATTERN = re.compile(r"(?<!\d)(\d{4})\d{8,11}(\d{4})(?!\d)")


def mask_pii(text: str) -> str:
    """对文本中的手机号/身份证/银行卡号进行掩码（幂等）"""
    if not text:
        return text
    masked = _ID_PATTERN.sub(r"\1********\2", text)
    masked = _PHONE_PATTERN.sub(r"\1****\2", masked)
    masked = _CARD_PATTERN.sub(r"\1********\2", masked)
    return masked


def mask_pii_list(items):
    """对引用列表等结构中的 content 字段批量脱敏（幂等，原结构不变）"""
    if not items:
        return items
    for item in items:
        if isinstance(item, dict) and item.get("content"):
            item["content"] = mask_pii(item["content"])
    return items