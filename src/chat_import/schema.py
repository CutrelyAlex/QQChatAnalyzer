"""聊天归一化数据模型。

目标：
- 把不同来源（JSON/TXT）的聊天记录统一为同一套结构，便于后续分析/展示
- **标识统一**：优先使用 exporter 提供的 uid 作为唯一标识（JSON 中一定存在）
    - 为了兼容旧代码，这里仍保留字段名 participant_id，但其值应当等同于 uid（或在 TXT 场景下等同于 uin）
- 时间统一为 epoch 毫秒（timestamp_ms）

说明：
- 只保留分析需要的结构化字段（elements/灰条/撤回/回复/@ 等）与少量展示字段
- 不保存原始 JSON/裁剪后的 raw
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

    # 同一 uid/uin 的展示名（群昵称/QQ 名称）是可变的：记录出现过的名字（按出现顺序去重）
    display_name_history: tuple[str, ...] = ()

    # 群昵称列表：来自 JSON rawMessage.sendMemberName（或 TXT 的 sender），按出现顺序去重
    member_names: tuple[str, ...] = ()

    # QQ 名：来自 JSON rawMessage.sendNickName（如存在）
    nick_name: Optional[str] = None


@dataclass(frozen=True)
class Mention:
    target_participant_id: Optional[str] = None
    target_name: Optional[str] = None
    # JSON elements.textElement.atUid（注意：这是 UIN）
    target_uin: Optional[str] = None
    # JSON elements.textElement.atNtUid（如存在，为 uid）
    target_uid: Optional[str] = None
    offset: Optional[int] = None
    length: Optional[int] = None


@dataclass(frozen=True)
class ReplyReference:
    target_message_id: Optional[str] = None
    target_timestamp_ms: Optional[int] = None
    snippet: Optional[str] = None

    # JSON replyElement.sourceMsgIdInRecords（可以通过 MsgId 查询）
    source_msg_id_in_records: Optional[str] = None
    # JSON replyElement.senderUid（注意：这里是 UIN）
    source_sender_uin: Optional[str] = None
    # JSON replyElement.senderUidStr（如存在，为 uid）
    source_sender_uid: Optional[str] = None


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

    # rawMessage.msgType（按 NTMsgType 枚举理解），保留原始 int
    nt_msg_type: Optional[int] = None

    # 系统灰条：rawMessage.elements[].grayTipElement.subElementType
    graytip_subtype: Optional[int] = None

    # 撤回：操作者信息（uid/uin）
    recall_operator_uid: Optional[str] = None
    recall_operator_uin: Optional[str] = None

    # 供现有分析器/词云等使用，从 elements 中拼接得到的真正说话文本（TEXT 且 atType=0）
    text: str = ""
    # content.text（用于组装 AI 原文，不作为分析输入）
    content_text: str = ""

    # rawMessage.elements 的统计：elementType -> count
    element_counts: Dict[int, int] = field(default_factory=dict)

    mentions: List[Mention] = field(default_factory=list)
    reply_to: Optional[ReplyReference] = None

@dataclass
class Conversation:
    conversation_id: str
    type: str  # group|private|unknown
    title: Optional[str] = None

    participants: List[Participant] = field(default_factory=list)
    messages: List[Message] = field(default_factory=list)

    message_count_raw: int = 0

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
