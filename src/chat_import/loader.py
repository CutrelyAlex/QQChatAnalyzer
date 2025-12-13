"""统一加载入口。

这里是 app.py 与分析器应当使用的唯一入口：
- 根据文件后缀选择解析器（JSON / TXT）
- 按选项过滤系统/撤回
- 去重并回填统计信息
- 计算时间范围
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from .core import DedupTracker, FilterOptions, apply_filters, dedup_key
from .importers import load_conversation_from_json, load_conversation_from_txt
from .schema import Conversation, LoadResult


def _compute_time_range(conversation: Conversation) -> None:
    ts = [m.timestamp_ms for m in conversation.messages if m.timestamp_ms]
    if not ts:
        conversation.time_range = None
        return
    conversation.time_range = {"startTsMs": min(ts), "endTsMs": max(ts)}


def load_chat_file(file_path: str, options: Optional[Dict[str, Any]] = None) -> LoadResult:
    options = options or {}
    include_system = bool(options.get("includeSystem", True))
    include_recalled = bool(options.get("includeRecalled", True))

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".json":
        conversation, warnings = load_conversation_from_json(file_path)
    elif ext == ".txt":
        conversation, warnings = load_conversation_from_txt(file_path)
    else:
        raise ValueError(f"不支持的文件类型: {ext}")

    conversation.message_count_raw = len(conversation.messages)

    # 应用过滤：是否包含系统/撤回
    filtered = apply_filters(conversation.messages, FilterOptions(include_system=include_system, include_recalled=include_recalled))

    # 去重
    tracker = DedupTracker()
    deduped = []
    for m in filtered:
        if tracker.is_duplicate(m):
            continue

        # 回填稳定内部 id
        _tier, key = dedup_key(m)
        m.id = key
        deduped.append(m)

    conversation.messages = deduped
    conversation.message_count_deduped = len(deduped)
    conversation.dedup_stats = tracker.stats

    _compute_time_range(conversation)

    return LoadResult(conversation=conversation, warnings=warnings)
