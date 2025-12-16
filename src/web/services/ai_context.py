from __future__ import annotations

import json
from pathlib import Path

from src.config import Config
from src.group_analyzer import GroupAnalyzer
from src.network_analyzer import NetworkAnalyzer
from src.personal_analyzer import PersonalAnalyzer

from .conversation_loader import safe_texts_file_path, load_conversation_and_messages


def clamp_float(value, *, default: float, min_value: float, max_value: float) -> float:
    try:
        v = float(value)
    except Exception:
        return float(default)
    if v < min_value:
        return float(min_value)
    if v > max_value:
        return float(max_value)
    return float(v)


def normalize_ai_summary_type(t: str) -> str:
    """把各种前端/缓存传入的 type 归一为后端内部类型。"""
    s = (t or '').strip().lower()
    if s == 'personal':
        return 'personal'
    # group/network/group_and_network 统一为融合报告
    if s in ('group', 'network', 'group_and_network'):
        return 'group_and_network'
    return s or 'personal'


def load_ai_cached_data(data: dict) -> tuple[str, str | None, dict | None]:
    """从 exports/.analysis_cache 读取缓存数据。"""
    import pickle

    summary_type = normalize_ai_summary_type(data.get('type', 'personal'))
    filename = data.get('filename')

    cache_id = data.get('cache_id')
    group_cache_id = data.get('group_cache_id')
    network_cache_id = data.get('network_cache_id')

    # 合并缓存模式（群体+网络）
    if group_cache_id and network_cache_id:
        group_cache_file = Path('exports/.analysis_cache') / f"{group_cache_id}.pkl"
        network_cache_file = Path('exports/.analysis_cache') / f"{network_cache_id}.pkl"
        if not group_cache_file.exists() or not network_cache_file.exists():
            return summary_type, filename, None

        with open(group_cache_file, 'rb') as f:
            group_cache_content = pickle.load(f)
        with open(network_cache_file, 'rb') as f:
            network_cache_content = pickle.load(f)

        group_data = group_cache_content.get('data', {})
        network_data = network_cache_content.get('data', {})

        # 优先使用较长的 chat_sample（若存在）；但统一逻辑会尽量从原文件重采样
        chat_sample = group_data.get('chat_sample', '')
        other = network_data.get('chat_sample', '')
        if len(other or '') > len(chat_sample or ''):
            chat_sample = other

        filename = group_cache_content.get('filename') or filename
        return 'group_and_network', filename, {
            'group_stats': group_data.get('group_stats', {}),
            'network_stats': network_data.get('network_stats', {}),
            'chat_sample': chat_sample,
        }

    # 单缓存模式
    if cache_id:
        cache_file = Path('exports/.analysis_cache') / f"{cache_id}.pkl"
        if not cache_file.exists():
            return summary_type, filename, None
        with open(cache_file, 'rb') as f:
            cache_content = pickle.load(f)
        cached_data = cache_content.get('data')
        filename = cache_content.get('filename') or filename
        summary_type = normalize_ai_summary_type(cache_content.get('type', summary_type))
        return summary_type, filename, cached_data

    return summary_type, filename, None


def prepare_ai_summary_context(data: dict) -> dict:
    """解析请求 -> 解析缓存 -> 加载消息 -> 得到 stats/group/network dict。"""

    # 输出长度与采样预算
    max_tokens = data.get('max_tokens', Config.DEFAULT_OUTPUT_TOKENS)
    context_budget = data.get('context_budget', Config.DEFAULT_CONTEXT_BUDGET)

    temperature = clamp_float(
        data.get('temperature', Config.DEFAULT_TEMPERATURE),
        default=Config.DEFAULT_TEMPERATURE,
        min_value=0.0,
        max_value=2.0,
    )
    top_p = clamp_float(
        data.get('top_p', data.get('topP', Config.DEFAULT_TOP_P)),
        default=Config.DEFAULT_TOP_P,
        min_value=0.0,
        max_value=1.0,
    )

    summary_type, filename, cached_data = load_ai_cached_data(data)
    summary_type = normalize_ai_summary_type(summary_type)

    if not filename and not cached_data:
        raise ValueError('未指定文件或缓存')

    filepath = None
    if filename:
        filepath = safe_texts_file_path(filename)
        if filepath is not None and (not filepath.exists()) and not cached_data:
            raise FileNotFoundError('文件不存在')

    # 尽量从原文件加载 messages（用于 chat_sample），缓存缺文件时才回退 chat_sample
    conv = None
    messages = []
    if filepath is not None and filepath.exists():
        conv, messages, _warnings = load_conversation_and_messages(filename)

    # 基于缓存/实时分析得到 stats
    qq = data.get('qq')
    stats_dict = None
    group_stats_dict = None
    network_stats_dict = None
    chat_sample = ''

    if cached_data:
        chat_sample = (cached_data.get('chat_sample') or '') if isinstance(cached_data, dict) else ''
        if summary_type == 'personal':
            stats_dict = (cached_data.get('stats') or {}) if isinstance(cached_data, dict) else {}
        else:
            group_stats_dict = (cached_data.get('group_stats') or {}) if isinstance(cached_data, dict) else {}
            network_stats_dict = (cached_data.get('network_stats') or {}) if isinstance(cached_data, dict) else {}
    else:
        if not filepath or not filepath.exists():
            raise FileNotFoundError('文件不存在')

        if summary_type == 'personal':
            if not qq:
                raise ValueError('个人总结需要指定成员（QQ号/昵称）')
            if conv is None:
                conv, messages, _warnings = load_conversation_and_messages(filename)
            analyzer = PersonalAnalyzer()
            stats = analyzer.get_user_stats(conv, str(qq))
            if not stats:
                raise FileNotFoundError(f'未找到账号 {qq} 的数据')
            stats_dict = stats.to_dict()
        else:
            g = GroupAnalyzer(); g.load_messages(messages); group_stats_dict = g.analyze().to_dict()
            n = NetworkAnalyzer(); n.load_messages(messages); network_stats_dict = n.analyze().to_dict()

    return {
        'summary_type': summary_type,
        'filename': filename,
        'filepath': filepath,
        'qq': qq,
        'max_tokens': max_tokens,
        'context_budget': context_budget,
        'temperature': temperature,
        'top_p': top_p,
        'messages': messages,
        'chat_sample': chat_sample,
        'stats': stats_dict,
        'group_stats': group_stats_dict,
        'network_stats': network_stats_dict,
    }
