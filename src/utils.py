"""
通用工具模块 - 提取各分析模块的公共代码

包含:
- 时间解析工具
- 常量定义
- 公共正则表达式
"""

import re
from datetime import datetime
from typing import Optional


# ==================== 常量定义 ====================

# 系统QQ号（需要过滤的消息来源）
SYSTEM_QQ_NUMBERS = frozenset({'10000', '1000000'})

# 污染词汇和组合词（需要从热词中移除）
POLLUTED_PHRASES = frozenset({
    '请使用新版收集',
    'qq体验',
    '手机QQ',
    '最新功能',
})


# ==================== 预编译正则表达式 ====================

# 时间戳匹配 - 聊天记录行首
TIME_LINE_PATTERN = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{1,2}:\d{2}:\d{2}) (.+)\((\d+)\)')

# @提及检测
MENTION_PATTERN = re.compile(r'@[\u4E00-\u9FFF\w\-（）\(\)]+')
AT_SYMBOL_PATTERN = re.compile(r'@\s*')

# QQ号提及检测 (带括号格式)
QQ_MENTION_PATTERN = re.compile(r'@(\w+)\((\d+)\)')

# 链接检测
HTTP_PATTERN = re.compile(r'(http|https)://')

# 表情检测
EMOJI_PATTERN = re.compile(r'\[([^\]]+)\]')

# 资源/系统占位符（用于清理热词、示例文本等）
_BRACKET_ARTIFACT_PATTERN = re.compile(
    r"\[(图片|表情|合并转发|聊天记录|语音|视频|文件|动画表情|动图|位置|红包|转账|卡片|名片|分享|链接|应用消息)\s*[:：]?[^\]]*\]"
)
_XML_DECL_PATTERN = re.compile(r"<\?xml[^>]*\?>", re.IGNORECASE)
_XML_MSG_PATTERN = re.compile(r"<msg\b[^>]*>.*?</msg>", re.IGNORECASE | re.DOTALL)
_XML_TAG_PATTERN = re.compile(r"<[^>]+>", re.IGNORECASE)
_XML_ATTR_LIKE_PATTERN = re.compile(r"\b\w+\s*=\s*\"[^\"\n]{1,2000}\"")
_XML_ATTR_LIKE_SQ_PATTERN = re.compile(r"\b\w+\s*=\s*'[^'\n]{1,2000}'")
_LONG_HEX_PATTERN = re.compile(r"\b[0-9a-fA-F]{16,}\b")
_HASHED_FILENAME_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{16,}\.(jpg|jpeg|png|gif|webp|bmp|mp4|mov|mkv|mp3|amr|wav)\b",
    re.IGNORECASE,
)

# URL 片段
_URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)
_WWW_PATTERN = re.compile(r"\bwww\.[^\s]+", re.IGNORECASE)

# 移除所有 [] 包裹的内容
_ANY_BRACKET_PATTERN = re.compile(r"\[[^\]]*\]")

# QQChatExporter / 内部标识（避免 uid token 污染热词与示例）
_EXPORTER_UID_PATTERN = re.compile(r"\bu_[A-Za-z0-9_\-]{6,}\b")
_INTERNAL_PARTICIPANT_ID_PATTERN = re.compile(r"\b(?:uid|uin|name)\s*:\s*[^\s]{1,120}\b", re.IGNORECASE)


# ==================== 时间解析工具 ====================

def parse_timestamp(time_str: str) -> Optional[datetime]:
    """
    解析时间戳，兼容多种格式：
    - 标准ISO格式: "2025-05-10 00:30:00"
    - 单数字小时: "2025-05-10 0:30:00"
    
    Args:
        time_str: 时间字符串
    
    Returns:
        datetime对象，解析失败返回None
    """
    if not time_str:
        return None
    
    ts = str(time_str).strip()
    if not ts:
        return None

    # 兼容 ISO-8601 的 UTC 结尾 "Z"（datetime.fromisoformat 不接受 'Z'）
    if ts.endswith('Z'):
        ts = ts[:-1] + '+00:00'

    # 1. 尝试标准ISO格式（支持 "YYYY-MM-DD HH:MM:SS" / "YYYY-MM-DDTHH:MM:SS" / 带毫秒 / 带时区）
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        pass
    
    # 2. 尝试 strptime 解析
    try:
        return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        pass
    
    # 3. 手动解析：补齐单数字小时
    try:
        parts = ts.split(' ')
        if len(parts) == 2:
            date_part, time_part = parts
            time_components = time_part.split(':')
            if len(time_components) == 3:
                h, m, s = time_components
                # 补齐小时为两位数
                normalized = f"{date_part} {int(h):02d}:{m}:{s}"
                return datetime.fromisoformat(normalized)
    except (ValueError, IndexError):
        pass
    
    return None


def parse_hour_from_time(time_str: str) -> int:
    """
    从时间字符串中提取小时数
    兼容 "0:30:00" 和 "00:30:00" 格式
    
    Args:
        time_str: 时间部分字符串 (HH:MM:SS 或 H:MM:SS)
    
    Returns:
        小时数 (0-23)，解析失败返回 0
    """
    if not time_str:
        return 0
    
    try:
        return int(time_str.split(':')[0])
    except (ValueError, IndexError):
        return 0


def extract_date_from_timestamp(timestamp: str) -> str:
    """
    从时间戳中提取日期部分
    
    Args:
        timestamp: 完整时间戳 "2025-05-10 12:30:00"
    
    Returns:
        日期字符串 "2025-05-10"，失败返回空字符串
    """
    if not timestamp or len(timestamp) < 10:
        return ""
    return timestamp[:10]


def extract_time_from_timestamp(timestamp: str) -> str:
    """
    从时间戳中提取时间部分
    
    Args:
        timestamp: 完整时间戳 "2025-05-10 12:30:00"
    
    Returns:
        时间字符串 "12:30:00"，失败返回空字符串
    """
    if not timestamp:
        return ""
    parts = timestamp.split(' ')
    return parts[1] if len(parts) >= 2 else ""


# ==================== 文本处理工具 ====================

def is_system_qq(qq: str) -> bool:
    """
    检查是否为系统QQ号
    
    Args:
        qq: QQ号字符串
    
    Returns:
        True如果是系统QQ号
    """
    return qq in SYSTEM_QQ_NUMBERS


def clean_message_content(content: str) -> str:
    """
    清理消息内容，移除图片/表情/撤回等标记
    
    Args:
        content: 原始消息内容
    
    Returns:
        清理后的文本
    """
    if not content:
        return ""

    text = str(content)

    # 常见固定占位
    text = (text
            .replace('[图片]', '')
            .replace('[表情]', '')
            .replace('撤回了一条消息', ''))

    # 资源类括号占位（支持“[图片: xxx.jpg]”“[合并转发: <xml...>]”等）
    text = _BRACKET_ARTIFACT_PATTERN.sub(' ', text)

    # 更激进：移除所有 [] 片段（如：[回复 u_xxx: 原消息]）
    text = _ANY_BRACKET_PATTERN.sub(' ', text)

    # 移除 URL
    text = _URL_PATTERN.sub(' ', text)
    text = _WWW_PATTERN.sub(' ', text)

    # 移除 exporter 生成的 uid / participant_id 等内部标识
    text = _EXPORTER_UID_PATTERN.sub(' ', text)
    text = _INTERNAL_PARTICIPANT_ID_PATTERN.sub(' ', text)

    # 合并转发里常见的 XML 内容（直接整段剔除，避免 hash / resid 等污染热词）
    text = _XML_MSG_PATTERN.sub(' ', text)
    text = _XML_DECL_PATTERN.sub(' ', text)

    # 兜底：剔除残留的 XML/HTML 标签与“key=\"value\"”属性碎片
    text = _XML_TAG_PATTERN.sub(' ', text)
    text = _XML_ATTR_LIKE_PATTERN.sub(' ', text)
    text = _XML_ATTR_LIKE_SQ_PATTERN.sub(' ', text)

    # 移除长 hash / hashed 文件名（图片等）
    text = _HASHED_FILENAME_PATTERN.sub(' ', text)
    text = _LONG_HEX_PATTERN.sub(' ', text)

    # 统一空白
    text = text.replace('\n', ' ')
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_mentions(content: str) -> list:
    """
    从消息中提取@的用户名
    
    Args:
        content: 消息内容
    
    Returns:
        被@的用户名列表
    """
    return MENTION_PATTERN.findall(content)


def extract_qq_mentions(content: str) -> list:
    """
    从消息中提取@的QQ号（带括号格式）
    
    Args:
        content: 消息内容
    
    Returns:
        [(用户名, QQ号), ...]
    """
    return QQ_MENTION_PATTERN.findall(content)


def has_link(content: str) -> bool:
    """
    检查消息是否包含链接
    
    Args:
        content: 消息内容
    
    Returns:
        True如果包含链接
    """
    return bool(HTTP_PATTERN.search(content))


def extract_emojis(content: str) -> list:
    """
    从消息中提取表情名称
    
    Args:
        content: 消息内容
    
    Returns:
        表情名称列表
    """
    return EMOJI_PATTERN.findall(content)
