"""TXT 相关的预处理与清理逻辑。

说明：
- JSON：chat_import 已产出 clean_text（Message.text / content_text），可直接用于分词/热词，不再需要复杂的二次清理。
- TXT：仍可能存在 [图片]/[表情]/撤回提示/URL/XML等，需要清理与降噪。
"""

from __future__ import annotations

import collections
import re
from datetime import datetime
from typing import Iterable, List, Optional


# ==================== TXT 行解析/提及处理所需正则 ====================

# 时间戳匹配 - 聊天记录行首
TIME_LINE_PATTERN = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{1,2}:\d{2}:\d{2}) (.+)\((\d+)\)')

# @提及检测
MENTION_PATTERN = re.compile(r'@[\u4E00-\u9FFF\w\-（）\(\)]+')
AT_SYMBOL_PATTERN = re.compile(r'@\s*')

# QQ号提及检测 (带括号格式)
QQ_MENTION_PATTERN = re.compile(r'@(\w+)\((\d+)\)')


# ==================== 热词污染短语（多来自导出器提示/广告） ====================

POLLUTED_PHRASES = frozenset({
    '请使用新版收集',
    'qq体验',
    '手机QQ',
    '最新功能',
})


# ==================== 清理用正则（偏 TXT/导出器噪声） ====================

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

_URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)
_WWW_PATTERN = re.compile(r"\bwww\.[^\s]+", re.IGNORECASE)

# 移除所有 [] 包裹的内容
_ANY_BRACKET_PATTERN = re.compile(r"\[[^\]]*\]")

# QQChatExporter内部标识
_EXPORTER_UID_PATTERN = re.compile(r"\bu_[A-Za-z0-9_\-]{6,}\b")
_INTERNAL_PARTICIPANT_ID_PATTERN = re.compile(r"\b(?:uid|uin|name)\s*:\s*[^\s]{1,120}\b", re.IGNORECASE)


# ==================== 通用/轻量工具 ====================

# 系统QQ号（需要过滤的消息来源）
SYSTEM_QQ_NUMBERS = frozenset({'10000', '1000000'})

# 链接检测（轻量：只用于判断有无 URL，不做清理）
HTTP_PATTERN = re.compile(r'(http|https)://')

# 表情检测（旧格式：[xxx]）
EMOJI_PATTERN = re.compile(r'\[([^\]]+)\]')


def clean_message_content(content: str) -> str:
    """清理消息内容（主要用于 TXT/导出器噪声）。

    说明：
    - 旧实现用于从 raw 文本里剔除：[图片]/[表情]/URL/XML/hash 等
    - 新结构下：JSON 的 Message.text 已是 clean_text，一般不需要再调用
    """

    if not content:
        return ""

    text = str(content)

    # 常见固定占位：撤回不是 bracket，需要单独清理
    text = text.replace('撤回了一条消息', '')

    # 移除所有 [] 片段（如：[回复 u_xxx: 原消息]、[图片: xxx.jpg] [图片] [表情] 等）
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


def remove_nicknames_with_at(text: str, sorted_nicknames: List[str]) -> str:
    """移除文本中与@符号相关的昵称（仅替换 @昵称 形态）。"""

    if not sorted_nicknames or '@' not in text:
        return text

    result = text
    for nickname in sorted_nicknames:
        if not nickname or len(nickname) < 2:
            continue
        pattern = '@' + nickname
        if pattern in result:
            result = result.replace(pattern, ' ')
    return result


def remove_mentions_fast(text: str) -> str:
    """快速移除 @提及（正则剔除）。"""

    text = MENTION_PATTERN.sub('', text)
    text = AT_SYMBOL_PATTERN.sub('', text)
    return text.strip()


def remove_polluted_phrases_fast(text: str) -> str:
    """快速移除污染词汇（字符串替换）。"""

    for phrase in POLLUTED_PHRASES:
        if phrase in text:
            text = text.replace(phrase, '')
    return text.strip()


def normalize_for_tokenize(text: str, *, nicknames: Iterable[str] | None = None, assume_clean: bool = True) -> str:
    """统一的“分词前清理”入口。

    - assume_clean=True：假设 text 已是 clean_text（JSON/新导入层常见）；跳过重清理。
    - assume_clean=False：会调用 clean_message_content 做一次强力清理（TXT/raw 常见）。
    """

    if not text:
        return ''

    s = str(text)
    if not assume_clean:
        s = clean_message_content(s)

    # 只在有@符号且有昵称时才替换昵称
    if nicknames and '@' in s:
        sorted_nicknames = sorted({n.strip() for n in nicknames if n and str(n).strip()}, key=len, reverse=True)
        if sorted_nicknames:
            s = remove_nicknames_with_at(s, sorted_nicknames)

    s = remove_mentions_fast(s)
    s = remove_polluted_phrases_fast(s)
    return s


def parse_timestamp(time_str: str) -> Optional[datetime]:
    """解析时间戳（兼容多种格式）。

    支持：
    - "YYYY-MM-DD HH:MM:SS"（小时允许 1 位）
    - ISO-8601 变体（含时区/毫秒）
    - 末尾带 'Z' 的 ISO-8601
    """

    if not time_str:
        return None

    ts = str(time_str).strip()
    if not ts:
        return None

    if ts.endswith('Z'):
        ts = ts[:-1] + '+00:00'

    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        pass

    try:
        return datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        pass

    # 补齐单数字小时
    try:
        parts = ts.split(' ')
        if len(parts) == 2:
            date_part, time_part = parts
            t = time_part.split(':')
            if len(t) == 3:
                h, m, s = t
                normalized = f"{date_part} {int(h):02d}:{m}:{s}"
                return datetime.fromisoformat(normalized)
    except Exception:
        pass

    return None


def parse_hour_from_time(time_str: str) -> int:
    """从类似 '0:30:00' 或 '00:30:00' 的字符串提取小时。"""

    if not time_str:
        return 0
    try:
        return int(str(time_str).split(':')[0])
    except Exception:
        return 0


def has_link(content: str) -> bool:
    """判断文本中是否包含 http(s) 链接片段。"""

    if not content:
        return False
    return bool(HTTP_PATTERN.search(str(content)))


# ==================== 分词/热词 ====================

_NOISE_WORDS = frozenset({
    '合并转发', '聊天记录',
    'xml', 'msg', 'serviceid', 'templateid', 'action', 'brief', 'm_resid', 'm_filename',
    'resid', 'viewmultimsg', 'title', 'color', 'size', 'version',
    'http', 'https', 'www', 'com', 'cn', 'net', 'org',
    'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp',
    'mp4', 'mov', 'mkv', 'mp3', 'amr', 'wav',
    'zip', 'rar', '7z', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
})


def _is_noise_token(word: str) -> bool:
    if not word:
        return True
    w = word.strip()
    if not w:
        return True
    wl = w.lower()
    if wl in _NOISE_WORDS:
        return True
    if '%' in w:
        return True
    if re.search(r'\.(jpg|jpeg|png|gif|webp|bmp|mp4|mov|mkv|mp3|amr|wav)$', wl):
        return True
    return False


def cut_words(lines_to_process: List[str], top_words_num: int, nicknames: List[str] | None = None):
    """热词提取：返回 (word_counts, words_top)。

    约定：
    - 新结构下输入一般是 clean_text；此处只做轻量 normalize_for_tokenize。
    - 停用词来自 RemoveWords.remove_words。
    """

    # 避免在 import 阶段强依赖/强初始化
    import jieba

    from .RemoveWords import remove_words

    words: List[str] = []

    sorted_nicknames: List[str] = []
    if nicknames:
        sorted_nicknames = sorted({n.strip() for n in nicknames if n and str(n).strip()}, key=len, reverse=True)

    has_mentions = bool(sorted_nicknames)

    for s in lines_to_process:
        if not s:
            continue

        s_cleaned = normalize_for_tokenize(
            s,
            nicknames=sorted_nicknames if has_mentions else None,
            assume_clean=True,
        )

        words.extend(
            word
            for word in jieba.cut(s_cleaned, cut_all=False)
            if len(word) > 1 and word not in remove_words and (not _is_noise_token(word))
        )

    word_counts = collections.Counter(words)
    words_top = word_counts.most_common(int(top_words_num or 0))
    return word_counts, words_top


def extract_mentions(content: str) -> list[str]:
    """从文本中提取 @xxx（用户名/昵称）。"""

    if not content:
        return []
    return MENTION_PATTERN.findall(str(content))


def extract_qq_mentions(content: str) -> list[tuple[str, str]]:
    """从文本中提取 @name(qq) 这种形态。"""

    if not content:
        return []
    return QQ_MENTION_PATTERN.findall(str(content))
