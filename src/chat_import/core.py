"""聊天导入层：通用核心逻辑（纯函数/小工具）。

这里聚合：
- 身份规则（uid/uin 合并）
- 去重键规则
- 消息过滤（是否包含系统/撤回；热词默认排除）
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .schema import Conversation, Message


# -------------------------
# 身份规则（uid/uin 合并）
# -------------------------


@dataclass(frozen=True)
class SenderIdentity:
    participant_id: str
    uid: Optional[str]
    uin: Optional[str]
    display_name: str


def _norm_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def participant_id_from_uid_uin(uid: Any = None, uin: Any = None, fallback_name: Any = None) -> str:
    """生成稳定 participant_id。

    优先级：
    - uid（若存在）
    - uin（若存在）
    - fallback_name（仅用于缺失 uid/uin 的极端情况）

    使用前缀避免命名空间冲突。
    """

    uid_s = _norm_str(uid)
    if uid_s:
        return f"uid:{uid_s}"

    uin_s = _norm_str(uin)
    if uin_s:
        return f"uin:{uin_s}"

    name_s = _norm_str(fallback_name) or "unknown"
    return f"name:{name_s}"


def extract_sender_identity(sender_obj: Dict[str, Any] | None) -> SenderIdentity:
    """从 exporter 的 sender 结构提取身份信息。"""

    sender_obj = sender_obj or {}
    uid = _norm_str(sender_obj.get("uid"))
    uin = _norm_str(sender_obj.get("uin"))
    name = _norm_str(sender_obj.get("name")) or uid or uin or "unknown"

    participant_id = participant_id_from_uid_uin(uid=uid, uin=uin, fallback_name=name)
    return SenderIdentity(participant_id=participant_id, uid=uid, uin=uin, display_name=name)


def merge_display_name(current: str, new_name: str) -> str:
    """展示名可变：优先使用最新的非空名字。"""

    new_name = (new_name or "").strip()
    if new_name:
        return new_name
    return current


# -------------------------
# 过滤规则
# -------------------------


@dataclass(frozen=True)
class FilterOptions:
    include_system: bool = True
    include_recalled: bool = True


@dataclass(frozen=True)
class HotwordFilterOptions:
    exclude_system: bool = True
    exclude_recalled: bool = True


def apply_filters(messages: Iterable[Message], options: FilterOptions) -> List[Message]:
    out: List[Message] = []
    for m in messages:
        if not options.include_system and m.is_system:
            continue
        if not options.include_recalled and m.is_recalled:
            continue
        out.append(m)
    return out


def apply_hotword_filters(messages: Iterable[Message], options: HotwordFilterOptions) -> List[Message]:
    out: List[Message] = []
    for m in messages:
        if options.exclude_system and m.is_system:
            continue
        if options.exclude_recalled and m.is_recalled:
            continue
        out.append(m)
    return out


# -------------------------
# 去重键与统计
# -------------------------


def _hash_text(s: str) -> str:
    h = hashlib.sha256()
    h.update((s or "").encode("utf-8", errors="ignore"))
    return h.hexdigest()


def content_fingerprint(msg: Message) -> str:
    """用于兜底去重的内容指纹：文本 + 资源摘要。"""

    parts = [msg.text or ""]
    for r in msg.resources or []:
        parts.append(r.type or "")
        if r.name:
            parts.append(r.name)
        if r.url:
            parts.append(r.url)
    return _hash_text("\n".join(parts))


def dedup_key(msg: Message) -> Tuple[str, str]:
    """返回 (层级, key)。层级：messageId/composite/fallback"""

    if msg.message_id:
        return "messageId", f"mid:{msg.message_id}"

    if msg.conversation_id and msg.message_seq is not None and msg.msg_random is not None:
        return "composite", f"cmp:{msg.conversation_id}:{msg.message_seq}:{msg.msg_random}"

    sender = msg.sender_participant_id or ""
    fp = content_fingerprint(msg)
    return "fallback", f"fb:{msg.timestamp_ms}:{sender}:{fp}"


@dataclass
class DedupTracker:
    seen: Set[str] = field(default_factory=set)
    stats: Dict[str, int] = field(default_factory=lambda: {"byMessageId": 0, "byComposite": 0, "byFallback": 0})

    def is_duplicate(self, msg: Message) -> bool:
        tier, key = dedup_key(msg)
        if key in self.seen:
            if tier == "messageId":
                self.stats["byMessageId"] += 1
            elif tier == "composite":
                self.stats["byComposite"] += 1
            else:
                self.stats["byFallback"] += 1
            return True
        self.seen.add(key)
        return False
