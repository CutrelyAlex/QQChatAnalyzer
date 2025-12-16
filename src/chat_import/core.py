"""聊天导入层：通用核心逻辑（纯函数/小工具）。

这里聚合：
- 身份规则（uid/uin 合并）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

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
