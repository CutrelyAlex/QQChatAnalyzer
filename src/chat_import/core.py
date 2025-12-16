"""聊天导入层：通用核心逻辑（纯函数/小工具）。

这里聚合：
- 身份规则（uid/uin 合并）
- 去重键规则

说明：
- 消息过滤（例如排除系统/撤回）应由“热词/上层分析”管理，而不是导入层。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .schema import Message


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
    """生成稳定的参与者标识。

    约定：
    - JSON：uid 一定存在，因此标识应当等同于 uid
    - TXT：通常只有 uin，因此标识等同于 uin
    """

    uid_s = _norm_str(uid)
    if uid_s:
        return uid_s

    uin_s = _norm_str(uin)
    if uin_s:
        return uin_s

    name_s = _norm_str(fallback_name) or "unknown"
    return name_s


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


@dataclass(frozen=True)
class HotwordFilterOptions:
    exclude_system: bool = True
    exclude_recalled: bool = True

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
    """用于兜底去重的内容指纹。

    只依赖导入层保留的必要字段：
    - clean_text（msg.text）
    - nt_msg_type
    - element_counts
    - mentions 数量
    """

    parts: list[str] = []
    parts.append(msg.text or "")
    parts.append(str(msg.nt_msg_type or ""))
    # element_counts 需稳定排序
    if msg.element_counts:
        for k in sorted(msg.element_counts.keys()):
            parts.append(f"e{k}:{msg.element_counts.get(k)}")
    parts.append(f"m@:{len(msg.mentions or [])}")
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
