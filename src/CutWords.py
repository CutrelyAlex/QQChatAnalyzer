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
    has_mention = False  # 标记是否需要检查@符号
    
    # 预处理昵称列表
    nickname_id = id(nicknames)  # 使用对象ID作为缓存键
    if nicknames and nickname_id not in _nickname_cache:
        _nickname_cache[nickname_id] = sorted(set(n for n in nicknames if n), key=len, reverse=True)
    sorted_nicknames = _nickname_cache.get(nickname_id) if nicknames else None
    
    for s in lines_to_process:
        # 只在有@符号时才替换昵称
        if sorted_nicknames and '@' in s:
            s = replace_nicknames_fast(s, sorted_nicknames)
            has_mention = True
        
        # 去除 @提及 和污染词汇
        s_cleaned = remove_mentions_fast(s)
        s_cleaned = remove_polluted_phrases_fast(s_cleaned)
        
        # 分词并过滤
        words.extend(word for word in jieba.cut(s_cleaned, cut_all=False) 
                     if len(word) > 1 and word not in remove_words)
    
    word_counts = collections.Counter(words)
    words_top = word_counts.most_common(top_words_num)
    
    return word_counts, words_top


def replace_nicknames_fast(text, sorted_nicknames):
    """
    快速替换昵称
    
    Args:
        text: 输入文本
        sorted_nicknames: 已按长度降序排序的昵称列表
    
    Returns:
        替换后的文本
    """
    for nickname in sorted_nicknames:
        if nickname in text:
            text = text.replace(nickname, ' ')
    return text


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
    
    # 遍历每个昵称，如果出现在文本中，将其替换为空格
    for nickname in sorted_nicknames:
        if nickname and len(nickname) > 0:
            # 只有文本中同时有@和昵称时，才替换该昵称
            if nickname in text:
                text = text.replace(nickname, ' ')
    
    return text


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