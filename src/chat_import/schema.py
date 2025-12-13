"""聊天归一化数据模型。

目标：
- 把不同来源（JSON/TXT）的聊天记录统一为同一套结构，便于后续分析/展示
- 参与者主键稳定：同 uid 或同 uin 视为同一人（由 core.py 的规则生成 participant_id）
- 时间统一为 epoch 毫秒（timestamp_ms），便于排序与统计

说明：
- 对于 JSON 中更丰富的细节（资源、回复、系统事件等），优先放入 resources/meta/raw
- raw/meta 会做裁剪
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Participant:
    participant_id: str
    display_name: str
    uid: Optional[str] = None
    uin: Optional[str] = None


@dataclass(frozen=True)
class Mention:
    target_participant_id: Optional[str] = None
    target_name: Optional[str] = None
    offset: Optional[int] = None
    length: Optional[int] = None


@dataclass(frozen=True)
class ReplyReference:
    target_message_id: Optional[str] = None
    target_timestamp_ms: Optional[int] = None
    snippet: Optional[str] = None


@dataclass(frozen=True)
class Resource:
    # 资源/事件类型（允许扩展；未知类型用 unknown）
    # 常见：image/audio/video/file/forward/emoji/sticker/redpacket/link/special/unknown
    type: str
    name: Optional[str] = None
    url: Optional[str] = None
    size_bytes: Optional[int] = None
    meta: Optional[Dict[str, Any]] = None


@dataclass
class Message:
    # Internal unique id after dedup
    id: str

    # Source ids (optional)
    message_id: Optional[str] = None
    message_seq: Optional[int] = None
    msg_random: Optional[int] = None

    conversation_id: str = ""
    timestamp_ms: int = 0

    sender_participant_id: Optional[str] = None
    sender_name: Optional[str] = None

    is_system: bool = False
    is_recalled: bool = False

    message_type: str = "unknown"

    text: str = ""
    mentions: List[Mention] = field(default_factory=list)
    reply_to: Optional[ReplyReference] = None
    resources: List[Resource] = field(default_factory=list)

    raw: Optional[Dict[str, Any]] = None


@dataclass
class Conversation:
    conversation_id: str
    type: str  # group|private|unknown
    title: Optional[str] = None

    participants: List[Participant] = field(default_factory=list)
    messages: List[Message] = field(default_factory=list)

    message_count_raw: int = 0
    message_count_deduped: int = 0
    dedup_stats: Dict[str, int] = field(default_factory=lambda: {"byMessageId": 0, "byComposite": 0, "byFallback": 0})

    time_range: Optional[Dict[str, int]] = None  # {startTsMs, endTsMs}

    source_stats: Optional[Dict[str, Any]] = None


@dataclass
class LoadResult:
    conversation: Conversation
    warnings: List[str] = field(default_factory=list)


def safe_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None
