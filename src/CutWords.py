import jieba
import collections
import re
from functools import lru_cache

try:
    from .RemoveWords import remove_words
    from .utils import SYSTEM_QQ_NUMBERS, POLLUTED_PHRASES, MENTION_PATTERN, AT_SYMBOL_PATTERN
except ImportError:
    from RemoveWords import remove_words
    from utils import SYSTEM_QQ_NUMBERS, POLLUTED_PHRASES, MENTION_PATTERN, AT_SYMBOL_PATTERN

# 局部别名（兼容现有代码）
_MENTION_PATTERN = MENTION_PATTERN
_AT_PATTERN = AT_SYMBOL_PATTERN

# 缓存昵称集合
_nickname_cache = {}

def build_qq_nickname_map(chat_messages):
    """
    从聊天记录构建 QQ-昵称映射
    
    Args:
        chat_messages: 聊天消息列表，每条为 {'sender': 昵称, 'qq': QQ号, ...} 的字典
    
    Returns:
        dict: {昵称: QQ号, ...} 的映射
    """
    qq_nickname_map = {}
    if not chat_messages:
        return qq_nickname_map
    
    for msg in chat_messages:
        if isinstance(msg, dict) and 'sender' in msg and 'qq' in msg:
            nickname = msg.get('sender', '').strip()
            qq = msg.get('qq', '').strip()
            if nickname and qq:
                qq_nickname_map[nickname] = qq
    
    return qq_nickname_map


def cut_words(lines_to_process : list, top_words_num: int, nicknames: list = None):
    """提取热词并返回词频统计
    
    Args:
        lines_to_process: 文本行列表
        top_words_num: 返回前N个热词
        nicknames: 昵称列表（仅在有@符号时替换）
    
    Returns:
        (word_counts, words_top) - 完整词频统计和前N个热词
    """
    words = []
    
    # 预处理昵称列表：去重并按长度降序排序
    sorted_nicknames = []
    if nicknames:
        sorted_nicknames = sorted(set(n.strip() for n in nicknames if n and n.strip()), 
                                 key=len, reverse=True)
    
    for s in lines_to_process:
        # 只在有@符号且有昵称时才替换昵称
        if sorted_nicknames and '@' in s:
            s = remove_nicknames_with_at(s, sorted_nicknames)
        
        # 去除 @提及 和污染词汇
        s_cleaned = remove_mentions_fast(s)
        s_cleaned = remove_polluted_phrases_fast(s_cleaned)
        
        # 分词并过滤
        words.extend(word for word in jieba.cut(s_cleaned, cut_all=False) 
                     if len(word) > 1 and word not in remove_words)
    
    word_counts = collections.Counter(words)
    words_top = word_counts.most_common(top_words_num)
    
    return word_counts, words_top


def remove_nicknames_with_at(text, sorted_nicknames):
    """
    移除文本中与@符号相关的昵称
    
    策略：
    1. 首先扫描是否有@符号，没有则直接返回
    2. 按长度降序处理昵称（长昵称优先）
    3. 移除所有 @昵称 的格式（可能跟随空格或标点）
    4. 移除所有 昵称@ 的格式（@ 在昵称后面）
    
    Args:
        text: 输入文本
        sorted_nicknames: 已按长度降序排序的昵称列表
    
    Returns:
        处理后的文本
    """
    if not sorted_nicknames or '@' not in text:
        return text
    
    result = text
    
    for nickname in sorted_nicknames:
        if not nickname:
            continue
        
        # 转义正则表达式特殊字符
        escaped_nickname = re.escape(nickname)
        
        # 1. 移除 @昵称 + 空格的格式
        # 匹配 @昵称 后跟空格、标点、括号或结尾
        result = re.sub(r'@\s*' + escaped_nickname + r'(?=[\s\.\,，。！？\:\：\)\）\]\】\(（@]|$)', ' ', result)
        
        # 2. 移除 昵称@ 的格式
        result = re.sub(escaped_nickname + r'@', ' ', result)
        
        # 3. 移除 @昵称）的格式（中文括号）
        result = re.sub(r'@' + escaped_nickname + r'[\）]', ' ', result)
        
        # 4. 移除末尾多余的括号（当@昵称被移除后留下的括号）
        result = re.sub(r'[\）]\s*$', '', result)
    
    return result


def replace_nicknames_fast(text, sorted_nicknames):
    """
    快速替换昵称 (已弃用，使用 remove_nicknames_with_at 替代)
    """
    return remove_nicknames_with_at(text, sorted_nicknames)


def remove_mentions_fast(text):
    """
    快速移除@提及
    """
    text = _MENTION_PATTERN.sub('', text)
    text = _AT_PATTERN.sub('', text)
    return text.strip()


def remove_polluted_phrases_fast(text):
    """
    快速移除污染词汇
    """
    for phrase in POLLUTED_PHRASES:
        if phrase in text:
            text = text.replace(phrase, '')
    return text.strip()


def replace_nicknames(text, nicknames):
    """
    将文本中的昵称替换为空字符串，但仅在同时存在"@"符号时才替换
    这样可以识别出 @昵称 的模式，避免过滤掉正常聊天中的有含义词汇
    
    按长度降序处理，确保长昵称优先替换
    
    Args:
        text: 输入文本
        nicknames: 昵称列表
    
    Returns:
        替换后的文本
    """
    if not nicknames or '@' not in text:
        # 如果没有昵称列表或文本中没有@符号，直接返回
        return text
    
    # 按长度降序排序昵称
    sorted_nicknames = sorted(set(nicknames), key=len, reverse=True)
    
    # 使用改进的函数
    return remove_nicknames_with_at(text, sorted_nicknames)


def remove_mentions(text):
    """
    移除文本中的 @昵称 部分
    """
    # 移除 @ 后跟昵称（包含中文、英文、数字、下划线、连字符等）
    # 昵称可能包含：汉字、字母、数字、下划线、连字符、括号等
    text = re.sub(r'@[\u4E00-\u9FFF\w\-（）\(\)]+', '', text)
    
    # 移除单独的 @ 符号
    text = re.sub(r'@\s*', '', text)
    
    return text.strip()


def remove_polluted_phrases(text):
    """
    移除污染词汇和组合词
    """
    for phrase in POLLUTED_PHRASES:
        text = text.replace(phrase, '')
    
    return text.strip()