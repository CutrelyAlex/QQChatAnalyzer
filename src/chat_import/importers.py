"""聊天导入层：具体格式解析（JSON / TXT）。

目前支持两类输入：
- QQChatExporter V4 导出的 JSON
- 文本 TXT

这里提供两个加载函数，统一输出归一化 Conversation。
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .core import extract_sender_identity, merge_display_name, participant_id_from_uid_uin
from .schema import Conversation, Mention, Message, Participant, ReplyReference, Resource, safe_int


# -------------------------
# 裁剪，避免保存过大 raw
# -------------------------


def _truncate_str(s: Any, max_len: int = 8000) -> Any:
    if not isinstance(s, str):
        return s
    if len(s) <= max_len:
        return s
    return s[:max_len] + "…(截断)"


def _shallow_trim(obj: Any, *, max_depth: int = 3, max_keys: int = 60, max_list: int = 60) -> Any:
    """把任意 JSON 对象裁剪"""

    if max_depth <= 0:
        return None

    if isinstance(obj, str):
        return _truncate_str(obj)

    if isinstance(obj, (int, float, bool)) or obj is None:
        return obj

    if isinstance(obj, list):
        out = []
        for x in obj[:max_list]:
            out.append(_shallow_trim(x, max_depth=max_depth - 1, max_keys=max_keys, max_list=max_list))
        if len(obj) > max_list:
            out.append(f"…(列表截断，原长度 {len(obj)})")
        return out

    if isinstance(obj, dict):
        out = {}
        for i, (k, v) in enumerate(obj.items()):
            if i >= max_keys:
                out["…"] = f"(字段截断，原字段数 {len(obj)})"
                break
            out[str(k)] = _shallow_trim(v, max_depth=max_depth - 1, max_keys=max_keys, max_list=max_list)
        return out

    # 其他类型兜底
    return _truncate_str(str(obj))


# -------------------------
# JSON：QQChatExporter V4
# -------------------------


def _parse_timestamp_ms(value: Any) -> Optional[int]:
    """把导出时间戳统一为 epoch ms。

    支持：
    - ISO 字符串：2025-12-13T13:22:28.000Z
    - 秒/毫秒数字（int/str）
    """

    if isinstance(value, str):
        s = value.strip()

        # ISO 8601
        try:
            # QQChatExporter V4 的 timestamp 常以 "Z" 结尾，但很多导出文件里这个时间本身就是“本地时间”。
            # 如果把它当 UTC，再转换为本地时间，会导致小时分布整体偏移（例如 06:00 变成 14:00）。
            # 默认：把 "Z" 当作“本地时间标记”处理（去掉 Z，按本地时区解释）。
            # 如需严格按 UTC 解释，可设置环境变量 CIYUN_JSON_ASSUME_UTC=1。
            if s.endswith("Z"):
                assume_utc = os.getenv("CIYUN_JSON_ASSUME_UTC", "0").strip().lower() in (
                    "1", "true", "yes", "y", "on"
                )
                if assume_utc:
                    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
                else:
                    dt = datetime.fromisoformat(s[:-1])
                return int(dt.timestamp() * 1000)

            # 其他 ISO（可能带 offset / 不带 offset）
            dt = datetime.fromisoformat(s)
            return int(dt.timestamp() * 1000)
        except Exception:
            pass

        # numeric string
        v = safe_int(s)
        if v is not None:
            value = v

    v = safe_int(value)
    if v is None:
        return None

    # < 1e10 认为是秒
    if v < 10_000_000_000:
        return v * 1000

    # 其余按毫秒
    if v < 10_000_000_000_000_000:
        return v

    return None


def _detect_system_and_recall_from_raw_message(raw_message: Any) -> Tuple[bool, bool]:
    """从 exporter 的 rawMessage 中推断系统事件/撤回。

    背景：QQChatExporter V4 在部分导出场景中，顶层字段可能为：
    - isSystemMessage=false
    - isRecalled=false
    但真实的“灰条提示/撤回”会出现在 rawMessage.elements[].grayTipElement 中，
    或通过 rawMessage.msgType/subMsgType 表达。

    返回： (is_system, is_recalled)
    """

    if not isinstance(raw_message, dict):
        return False, False

    is_system = False
    is_recalled = False

    msg_type = safe_int(raw_message.get("msgType"))
    sub_msg_type = safe_int(raw_message.get("subMsgType"))

    # msgType=5 是灰条/系统类（包含撤回、入群提示等）
    if msg_type == 5:
        is_system = True
        # subMsgType=4 为撤回提示
        if sub_msg_type == 4:
            is_recalled = True

    elements = raw_message.get("elements")
    if isinstance(elements, list):
        for el in elements:
            if not isinstance(el, dict):
                continue
            gray = el.get("grayTipElement")
            if not isinstance(gray, dict):
                continue
            # grayTip 视为系统类事件
            is_system = True
            # revokeElement 存在即为撤回提示
            if isinstance(gray.get("revokeElement"), dict):
                is_recalled = True

    return is_system, is_recalled


def _guess_conversation_meta(root: Dict[str, Any], file_path: str) -> Tuple[str, str, str]:
    chat_info = root.get("chatInfo") or {}
    if not isinstance(chat_info, dict):
        chat_info = {}

    title = chat_info.get("name") or chat_info.get("title") or os.path.basename(file_path)
    if not isinstance(title, str):
        title = os.path.basename(file_path)

    raw_type = chat_info.get("type")
    ctype = "unknown"
    if isinstance(raw_type, str) and raw_type.lower() in ("group", "private"):
        ctype = raw_type.lower()

    # conversationId优先使用文件名派生
    conversation_id = f"json:{os.path.basename(file_path)}"

    return conversation_id, title, ctype


def _participant_from_sender(sender: Dict[str, Any]) -> Participant:
    ident = extract_sender_identity(sender)
    return Participant(
        participant_id=ident.participant_id,
        uid=ident.uid,
        uin=ident.uin,
        display_name=ident.display_name,
    )


def _resource_from_json_item(item: Dict[str, Any]) -> Resource:
    """把 exporter 提供的资源对象映射为 Resource。

    典型字段：type/fileName/fileSize/originalUrl/md5/accessible/checkedAt/...
    """

    rtype = str(item.get("type") or "unknown")

    name = item.get("fileName") or item.get("name")
    if name is not None and not isinstance(name, str):
        name = str(name)

    url = item.get("originalUrl") or item.get("url")
    if url is not None and not isinstance(url, str):
        url = str(url)

    size_bytes = safe_int(item.get("fileSize") or item.get("sizeBytes") or item.get("size"))

    meta = _shallow_trim({k: v for k, v in item.items() if k not in ("type", "fileName", "name", "originalUrl", "url", "fileSize", "sizeBytes", "size")})

    return Resource(type=rtype, name=name, url=url, size_bytes=size_bytes, meta=meta)


def _resource_from_emoji_item(item: Dict[str, Any]) -> Resource:
    etype = str(item.get("type") or "emoji")
    # face/marketFace/sticker 等都保留到 meta 里
    name = item.get("name")
    if name is not None and not isinstance(name, str):
        name = str(name)

    # 统一把“贴纸”单独区分出来
    rtype = "sticker" if etype.lower() in ("sticker", "marketface", "market_face", "stickerface") else "emoji"

    return Resource(type=rtype, name=name, url=None, size_bytes=None, meta=_shallow_trim(item))


def load_conversation_from_json(file_path: str) -> Tuple[Conversation, List[str]]:
    warnings: List[str] = []

    with open(file_path, "r", encoding="utf-8") as f:
        root = json.load(f)

    if not isinstance(root, dict):
        raise ValueError("JSON 根节点不是对象（dict）")

    msgs = root.get("messages")
    if not isinstance(msgs, list):
        raise ValueError("JSON 中缺少 messages 列表")

    conversation_id, title, ctype = _guess_conversation_meta(root, file_path)
    conv = Conversation(conversation_id=conversation_id, type=ctype, title=title)

    # 保留 exporter 给的统计/元信息
    conv.source_stats = _shallow_trim(
        {
            "statistics": root.get("statistics"),
            "metadata": root.get("metadata"),
            "exportOptions": root.get("exportOptions"),
            "chatInfo": root.get("chatInfo"),
        }
    )

    participants_by_id: Dict[str, Participant] = {}

    for idx, m in enumerate(msgs):
        if not isinstance(m, dict):
            continue

        ts_ms = _parse_timestamp_ms(m.get("timestamp"))
        if ts_ms is None:
            warnings.append(f"message[{idx}] 时间戳无法解析")
            ts_ms = 0

        sender_obj = m.get("sender") if isinstance(m.get("sender"), dict) else {}
        receiver_obj = m.get("receiver") if isinstance(m.get("receiver"), dict) else None

        sender_p = _participant_from_sender(sender_obj)
        existing = participants_by_id.get(sender_p.participant_id)
        if existing is None:
            participants_by_id[sender_p.participant_id] = sender_p
        else:
            participants_by_id[sender_p.participant_id] = Participant(
                participant_id=existing.participant_id,
                uid=existing.uid or sender_p.uid,
                uin=existing.uin or sender_p.uin,
                display_name=merge_display_name(existing.display_name, sender_p.display_name),
            )

        # 对于私聊/临时会话，有些 exporter 会把对方也放在 receiver
        if receiver_obj is not None:
            rec_p = _participant_from_sender(receiver_obj)
            ex2 = participants_by_id.get(rec_p.participant_id)
            if ex2 is None:
                participants_by_id[rec_p.participant_id] = rec_p
            else:
                participants_by_id[rec_p.participant_id] = Participant(
                    participant_id=ex2.participant_id,
                    uid=ex2.uid or rec_p.uid,
                    uin=ex2.uin or rec_p.uin,
                    display_name=merge_display_name(ex2.display_name, rec_p.display_name),
                )

        content = m.get("content") if isinstance(m.get("content"), dict) else {}

        text = content.get("text")
        if not isinstance(text, str):
            text = ""

        raw_message = m.get("rawMessage") if isinstance(m.get("rawMessage"), dict) else None
        raw_is_system, raw_is_recalled = _detect_system_and_recall_from_raw_message(raw_message)

        is_system = bool(m.get("isSystemMessage", False)) or raw_is_system
        is_recalled = bool(m.get("isRecalled", False)) or raw_is_recalled

        message_id = m.get("messageId")
        if message_id is not None and not isinstance(message_id, str):
            message_id = str(message_id)

        message_seq = safe_int(m.get("messageSeq"))
        msg_random = safe_int(m.get("msgRandom"))

        # mentions
        mentions: List[Mention] = []
        raw_mentions = content.get("mentions")
        if isinstance(raw_mentions, list):
            for it in raw_mentions:
                if not isinstance(it, dict):
                    continue
                uid = it.get("uid")
                name = it.get("name")
                pid = None
                if uid and uid != "unknown":
                    pid = participant_id_from_uid_uin(uid=uid)
                mentions.append(Mention(target_participant_id=pid, target_name=str(name) if name is not None else None))

        # reply
        reply_to: Optional[ReplyReference] = None
        raw_reply = content.get("reply")
        if isinstance(raw_reply, dict):
            target_mid = raw_reply.get("referencedMessageId") or raw_reply.get("messageId")
            if target_mid is not None and not isinstance(target_mid, str):
                target_mid = str(target_mid)
            snippet = raw_reply.get("content")
            if snippet is not None and not isinstance(snippet, str):
                snippet = str(snippet)
            reply_to = ReplyReference(target_message_id=target_mid, target_timestamp_ms=None, snippet=_truncate_str(snippet, 500) if snippet else None)

        # resources / emojis / multiForward / special
        resources: List[Resource] = []

        raw_resources = content.get("resources")
        if isinstance(raw_resources, list):
            for it in raw_resources:
                if isinstance(it, dict):
                    resources.append(_resource_from_json_item(it))

        raw_emojis = content.get("emojis")
        if isinstance(raw_emojis, list):
            for it in raw_emojis:
                if isinstance(it, dict):
                    resources.append(_resource_from_emoji_item(it))

        raw_forward = content.get("multiForward")
        if raw_forward:
            resources.append(Resource(type="forward", name=None, url=None, size_bytes=None, meta=_shallow_trim(raw_forward)))

        raw_special = content.get("special")
        if raw_special:
            # TODO:special 里可能包含红包/转账/群投票/位置等，类型各异，先统一保存
            # 红包标成 redpacket
            rtype = "special"
            if isinstance(raw_special, dict):
                st = raw_special.get("type") or raw_special.get("kind")
                if isinstance(st, str) and "red" in st.lower():
                    rtype = "redpacket"
            resources.append(Resource(type=rtype, name=None, url=None, size_bytes=None, meta=_shallow_trim(raw_special)))

        # message_type 推断：优先看资源与 reply
        message_type = "text"
        if is_system:
            message_type = "system"
        elif reply_to is not None:
            message_type = "reply"
        elif any(r.type == "image" for r in resources):
            message_type = "image"
        elif any(r.type == "video" for r in resources):
            message_type = "video"
        elif any(r.type == "audio" for r in resources):
            message_type = "audio"
        elif any(r.type == "file" for r in resources):
            message_type = "file"
        elif any(r.type in ("emoji", "sticker") for r in resources) and not text.strip():
            message_type = "emoji"

        msg = Message(
            id=f"tmp:{idx}",
            message_id=message_id,
            message_seq=message_seq,
            msg_random=msg_random,
            conversation_id=conversation_id,
            timestamp_ms=ts_ms,
            sender_participant_id=sender_p.participant_id,
            sender_name=sender_p.display_name,
            is_system=is_system,
            is_recalled=is_recalled,
            message_type=message_type,
            text=text,
            mentions=mentions,
            reply_to=reply_to,
            resources=resources,
            raw=_shallow_trim(
                {
                    "messageType": m.get("messageType"),
                    "isTempMessage": m.get("isTempMessage"),
                    "receiver": receiver_obj,
                    "stats": m.get("stats"),
                    "rawMessage": raw_message,
                    "content": {
                        # 保留 html/raw 供后续需要时使用
                        "html": content.get("html"),
                        "raw": content.get("raw"),
                    },
                }
            ),
        )
        conv.messages.append(msg)

    conv.participants = list(participants_by_id.values())
    conv.message_count_raw = len(conv.messages)

    # chatInfo.type 在不同版本/导出场景下可能不可靠：按参与者数量做兜底推断
    inferred = None
    if len(conv.participants) == 2:
        inferred = "private"
    elif len(conv.participants) > 2:
        inferred = "group"

    if inferred and conv.type != inferred:
        warnings.append(f"chatInfo.type={conv.type} 与参与者数量不一致，已按人数推断为 {inferred}")
        conv.type = inferred

    return conv, warnings


# -------------------------
# TXT：文本格式
# -------------------------


def load_conversation_from_txt(file_path: str) -> Tuple[Conversation, List[str]]:
    """把旧 TXT 转换为归一化 Conversation。

    说明：这里复用现有解析逻辑，尽量不改变旧语义。
    """

    from ..LineProcess import process_lines_data
    from ..utils import parse_timestamp

    warnings: List[str] = []

    _all_lines, all_lines_data, _qq_to_name_map = process_lines_data(file_path, mode="all")

    conversation_id = f"txt:{os.path.basename(file_path)}"
    title = os.path.basename(file_path)
    conv = Conversation(conversation_id=conversation_id, type="unknown", title=title)

    participants_by_id: Dict[str, Participant] = {}

    for idx, ld in enumerate(all_lines_data):
        ts_ms = 0
        try:
            dt = parse_timestamp(ld.timepat)
            if dt:
                ts_ms = int(dt.timestamp() * 1000)
        except Exception:
            ts_ms = 0

        participant_id = participant_id_from_uid_uin(uin=ld.qq, fallback_name=ld.sender)

        if participant_id not in participants_by_id:
            participants_by_id[participant_id] = Participant(
                participant_id=participant_id,
                uin=str(ld.qq) if ld.qq else None,
                uid=None,
                display_name=ld.sender or (ld.qq or "unknown"),
            )

        resources: List[Resource] = []
        if ld.image_count > 0:
            resources.append(Resource(type="image"))
        if ld.emoji_count > 0:
            resources.append(Resource(type="emoji"))
        if ld.has_link:
            resources.append(Resource(type="link"))

        mentions: List[Mention] = []
        for m in ld.mentions or []:
            mentions.append(Mention(target_participant_id=participant_id_from_uid_uin(uin=m), target_name=str(m)))

        msg = Message(
            id=f"tmp:{idx}",
            message_id=None,
            message_seq=None,
            msg_random=None,
            conversation_id=conversation_id,
            timestamp_ms=ts_ms,
            sender_participant_id=participant_id,
            sender_name=ld.sender,
            is_system=False,
            is_recalled=bool(ld.is_recall),
            message_type=ld.get_message_type(),
            text=ld.raw_text or "",
            mentions=mentions,
            resources=resources,
            raw=None,
        )
        conv.messages.append(msg)

    conv.participants = list(participants_by_id.values())
    conv.message_count_raw = len(conv.messages)

    if len(conv.participants) == 2:
        conv.type = "private"
    elif len(conv.participants) > 2:
        conv.type = "group"

    return conv, warnings
