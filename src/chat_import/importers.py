"""聊天导入层：具体格式解析（JSON / TXT）。

目前支持两类输入：
- QQChatExporter V4 导出的 JSON
- 文本 TXT

这里提供两个加载函数，统一输出归一化 Conversation。
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .core import extract_sender_identity, merge_display_name, participant_id_from_uid_uin
from .schema import Conversation, Mention, Message, Participant, ReplyReference, safe_int
from ..config import Config


# -------------------------
# JSON：QQChatExporter V4
# -------------------------


def _norm_name(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _looks_like_number(s: Optional[str]) -> bool:
    if not s:
        return False
    s2 = s.strip()
    return s2.isdigit()


def _extract_sender_names_from_raw_message(raw_message: Optional[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
    """按当前 exporter JSON 的结构提取名字：

    - 群昵称：rawMessage.sendMemberName
    - QQ 名称：rawMessage.sendNickName
    """

    if not isinstance(raw_message, dict):
        return None, None

    member_name = _norm_name(raw_message.get("sendMemberName"))
    nick_name = _norm_name(raw_message.get("sendNickName"))

    return member_name, nick_name


def _extract_nickname_from_statistics_senders(statistics: Any) -> Dict[str, Tuple[int, str]]:
    """从 root.statistics.senders 中抽取 uid -> name 的映射（仅做留存/兜底）。

    约定：
    - senders 里可能出现 {uid: 纯数字, name: "0"} 的系统占位发送者，需跳过
    - 这里的 name 是 QQ 名称（不是群昵称）
    """

    out: Dict[str, Tuple[int, str]] = {}
    if not isinstance(statistics, dict):
        return out

    senders = statistics.get("senders")
    if not isinstance(senders, list):
        return out

    for it in senders:
        if not isinstance(it, dict):
            continue
        uid = _norm_name(it.get("uid"))
        name = _norm_name(it.get("name"))
        if not uid or not name:
            continue
        if name == "0" and _looks_like_number(uid):
            continue

        # participant_id 在本项目中约定等同于 uid/uin 字符串
        pid = participant_id_from_uid_uin(uid=uid)
        out[pid] = (2, name)

    return out


def _parse_timestamp_ms(value: Any) -> Optional[int]:
    """把导出时间戳统一为 epoch ms。

    支持：
    - ISO 字符串：2025-12-13T13:22:28.000Z
    - 秒/毫秒数字（int/str）
    """

    if isinstance(value, str):
        s = value.strip()
        mode = (getattr(Config, 'JSON_TIMESTAMP_MODE', None) or 'utc_to_local').strip().lower()

        # 1) ISO 8601
        try:
            if mode == 'utc_to_local':
                # 标准语义：
                # - '...Z' 解析为 UTC aware
                # - '...+08:00' 等 offset 保留
                # - 无 offset 的 naive 按本地时间（datetime.timestamp() 会用本机时区解释）
                if s.endswith('Z'):
                    dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
                    return int(dt.timestamp() * 1000)

                dt = datetime.fromisoformat(s)
                return int(dt.timestamp() * 1000)

            # mode == 'wysiwyg'
            # 规则：timestamp 所见即所得
            # - 忽略 Z / offset 等时区标记（不做任何“转换”）
            # - 忽略毫秒（只取 HH:MM:SS）
            # - epoch 计算按 UTC 固定，避免运行环境时区影响
            if 'T' in s and len(s) >= 19:
                date_part, time_part = s.split('T', 1)
                time_hms = time_part[:8]
                dt_naive = datetime.fromisoformat(f"{date_part} {time_hms}")
                return int(dt_naive.replace(tzinfo=timezone.utc).timestamp() * 1000)

            if len(s) >= 19 and s[10] in (' ', 'T'):
                base = s[:19].replace('T', ' ')
                dt_naive = datetime.fromisoformat(base)
                return int(dt_naive.replace(tzinfo=timezone.utc).timestamp() * 1000)

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

    说明：在当前导出 JSON 中，顶层字段可能为：
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


def _append_unique_history(history: tuple[str, ...], name: Optional[str]) -> tuple[str, ...]:
    name = _norm_name(name)
    if not name:
        return history
    if name in history:
        return history
    return (*history, name)


def _parse_elements(
    raw_message: Optional[Dict[str, Any]],
) -> Tuple[Dict[int, int], str, List[Mention], Optional[ReplyReference], Optional[int], Optional[str], Optional[str], Optional[str]]:
    """解析 rawMessage.elements。

    返回：
    - element_counts: elementType -> count
    - clean_text: TEXT(elementType=1) 且 atType=0 的 content 拼接结果
    - mentions: TEXT 且 atType!=0 的 atUid(UIN)/atNtUid(uid)
    - reply_to: REPLY(elementType=7) 的关键字段
    - graytip_subtype: 系统灰条子类型（如存在）
    - graytip_xml_busi_type: 系统灰条 xmlElement.busiType（如存在）
    - recall_operator_uid / recall_operator_uin: 撤回操作者（如存在）
    """

    element_counts: Dict[int, int] = {}
    clean_parts: List[str] = []
    mentions: List[Mention] = []
    reply_to: Optional[ReplyReference] = None
    graytip_subtype: Optional[int] = None
    graytip_xml_busi_type: Optional[str] = None
    recall_operator_uid: Optional[str] = None
    recall_operator_uin: Optional[str] = None

    if not isinstance(raw_message, dict):
        return element_counts, "", mentions, reply_to, graytip_subtype, graytip_xml_busi_type, recall_operator_uid, recall_operator_uin

    elements = raw_message.get("elements")
    if not isinstance(elements, list):
        return element_counts, "", mentions, reply_to, graytip_subtype, graytip_xml_busi_type, recall_operator_uid, recall_operator_uin

    for el in elements:
        if not isinstance(el, dict):
            continue
        et = safe_int(el.get("elementType"))
        if et is None:
            continue
        element_counts[et] = int(element_counts.get(et, 0)) + 1

        # TEXT
        if et == 1:
            te = el.get("textElement")
            if not isinstance(te, dict):
                continue
            at_type = safe_int(te.get("atType")) or 0
            content = te.get("content")
            if content is None:
                content = ""
            if not isinstance(content, str):
                content = str(content)

            if at_type == 0:
                clean_parts.append(content)
            else:
                at_uid = _norm_name(te.get("atUid"))
                at_nt_uid = _norm_name(te.get("atNtUid"))
                mentions.append(
                    Mention(
                        target_participant_id=None,
                        target_name=_norm_name(content),
                        target_uin=at_uid,
                        target_uid=at_nt_uid,
                    )
                )

        # REPLY
        elif et == 7:
            re = el.get("replyElement")
            if not isinstance(re, dict):
                continue

            source_msg_id = re.get("sourceMsgIdInRecords")
            if source_msg_id is not None and not isinstance(source_msg_id, str):
                source_msg_id = str(source_msg_id)

            # 注意：replyElement.senderUid 是 UIN；senderUidStr 才是 uid
            source_sender_uin = _norm_name(re.get("senderUid"))
            source_sender_uid = _norm_name(re.get("senderUidStr"))

            # 从 sourceMsgTextElems 提取一段可读摘要（不做截断存储）
            snippet = None
            elems = re.get("sourceMsgTextElems")
            if isinstance(elems, list):
                parts: List[str] = []
                for it in elems:
                    if not isinstance(it, dict):
                        continue
                    t = it.get("textElemContent")
                    if t is None:
                        continue
                    if not isinstance(t, str):
                        t = str(t)
                    if t:
                        parts.append(t)
                if parts:
                    snippet = "".join(parts)

            reply_to = ReplyReference(
                target_message_id=str(source_msg_id) if source_msg_id else None,
                target_timestamp_ms=None,
                snippet=snippet if snippet else None,
                source_msg_id_in_records=str(source_msg_id) if source_msg_id else None,
                source_sender_uin=source_sender_uin,
                source_sender_uid=source_sender_uid,
            )

        # GrayTip (系统灰条)
        elif et == 8:
            gray = el.get("grayTipElement")
            if isinstance(gray, dict):
                st = safe_int(gray.get("subElementType"))
                if st is not None:
                    graytip_subtype = st
                xml = gray.get("xmlElement")
                if isinstance(xml, dict):
                    bt = xml.get("busiType")
                    if bt is not None and not isinstance(bt, str):
                        bt = str(bt)
                    if bt:
                        graytip_xml_busi_type = bt

                revoke = gray.get("revokeElement")
                if isinstance(revoke, dict):
                    recall_operator_uid = _norm_name(revoke.get("operatorUid"))
                    recall_operator_uin = _norm_name(revoke.get("operatorUin"))
                    # 部分情况下只有 operatorNick，没有 uin；不强求

    clean_text = "".join(clean_parts).strip()
    return (
        element_counts,
        clean_text,
        mentions,
        reply_to,
        graytip_subtype,
        graytip_xml_busi_type,
        recall_operator_uid,
        recall_operator_uin,
    )


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

    # 只保留必要的会话级信息：chatInfo + statistics(可信字段)
    stats = root.get("statistics") if isinstance(root.get("statistics"), dict) else None
    trusted_stats: Dict[str, Any] = {}
    if isinstance(stats, dict):
        trusted_stats["totalMessages"] = safe_int(stats.get("totalMessages"))
        trusted_stats["senders"] = stats.get("senders")
        trusted_stats["resources"] = stats.get("resources")

        # timeRange/messageTypes 暂不可信：但预留接口（空/unknown 则跳过）
        tr = stats.get("timeRange")
        if isinstance(tr, dict):
            start = _norm_name(tr.get("start"))
            end = _norm_name(tr.get("end"))
            if start and end:
                trusted_stats["timeRange"] = tr

        mt = stats.get("messageTypes")
        if isinstance(mt, dict):
            # exporter 里可能只有 unknown
            keys = {str(k).lower() for k in mt.keys()}
            if keys and keys != {"unknown"}:
                # 只保留我们关心的四类统计（totalSize 不可信，因此不依赖）
                keep: Dict[str, int] = {}
                for k in ("image", "audio", "video", "file"):
                    v = safe_int(mt.get(k))
                    if v is not None and v > 0:
                        keep[k] = v
                if keep:
                    trusted_stats["messageTypes"] = keep

    chat_info = root.get("chatInfo") if isinstance(root.get("chatInfo"), dict) else {}
    conv.source_stats = {
        "chatInfo": {
            "name": chat_info.get("name"),
            "type": chat_info.get("type"),
        },
        "trusted_statistics": trusted_stats,
    }

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

        raw_message = m.get("rawMessage") if isinstance(m.get("rawMessage"), dict) else None

        # sender 身份：优先用 rawMessage.senderUid/senderUin（JSON 中 uid 一定存在；系统灰条可能缺 senderUid）
        raw_uid = _norm_name(raw_message.get("senderUid")) if isinstance(raw_message, dict) else None
        raw_uin = _norm_name(raw_message.get("senderUin")) if isinstance(raw_message, dict) else None
        merged_sender = {
            "uid": sender_obj.get("uid") or raw_uid,
            "uin": sender_obj.get("uin") or raw_uin,
            "name": sender_obj.get("name"),
        }
        sender_ident = extract_sender_identity(merged_sender)

        raw_is_system, raw_is_recalled = _detect_system_and_recall_from_raw_message(raw_message)
        is_system = bool(m.get("isSystemMessage", False)) or raw_is_system
        is_recalled = bool(m.get("isRecalled", False)) or raw_is_recalled

        # 系统占位 sender：uid=纯数字 且 name="0"（跳过参与者入表；消息 sender 也用 None 兜底）
        is_system_sender_zero = (
            _norm_name(merged_sender.get("name")) == "0" and _looks_like_number(_norm_name(merged_sender.get("uid")))
        )

        sender_pid: Optional[str] = None
        sender_display: Optional[str] = None
        if not (is_system and is_system_sender_zero):
            sender_pid = sender_ident.participant_id

            # 展示名规则：优先群昵称 sendMemberName，其次 QQ 名称 sendNickName（一定存在）
            member_name, nick_name = _extract_sender_names_from_raw_message(raw_message)
            best_name = member_name or nick_name or sender_ident.display_name

            existing = participants_by_id.get(sender_pid)
            if existing is None:
                participants_by_id[sender_pid] = Participant(
                    participant_id=sender_pid,
                    uid=sender_ident.uid,
                    uin=sender_ident.uin,
                    display_name=best_name,
                    display_name_history=_append_unique_history((), best_name),
                )
            else:
                new_history = _append_unique_history(existing.display_name_history, best_name)
                participants_by_id[sender_pid] = Participant(
                    participant_id=existing.participant_id,
                    uid=existing.uid or sender_ident.uid,
                    uin=existing.uin or sender_ident.uin,
                    display_name=merge_display_name(existing.display_name, best_name),
                    display_name_history=new_history,
                )

            sender_display = participants_by_id[sender_pid].display_name

        # 当前导出 JSON 里 receiver 可能存在：
        # - 群聊：receiver.type="group" 且 receiver.uid=群号（不是“参与者”，跳过）
        # - 私聊：receiver 可能是对方（可纳入 participants）
        if receiver_obj is not None and str(receiver_obj.get("type") or "").lower() != "group":
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
                    display_name_history=_append_unique_history(ex2.display_name_history, rec_p.display_name),
                )

        content = m.get("content") if isinstance(m.get("content"), dict) else {}

        content_text = content.get("text")
        if not isinstance(content_text, str):
            content_text = ""

        message_id = m.get("messageId")
        if message_id is not None and not isinstance(message_id, str):
            message_id = str(message_id)

        message_seq = safe_int(m.get("messageSeq"))
        msg_random = safe_int(m.get("msgRandom"))

        # elements（作为分析输入）
        (
            element_counts,
            clean_text,
            mentions,
            reply_to,
            graytip_subtype,
            graytip_xml_busi_type,
            recall_operator_uid,
            recall_operator_uin,
        ) = _parse_elements(raw_message)

        # message_type 推断：优先看系统/撤回/回复；其次看 element_counts
        message_type = "text"
        if is_system:
            message_type = "system"
        elif reply_to is not None:
            message_type = "reply"
        else:
            # ElementType: 2=图片, 3=文件, 4=语音, 5=视频, 6/11=表情
            if element_counts.get(2, 0) > 0:
                message_type = "image"
            elif element_counts.get(5, 0) > 0:
                message_type = "video"
            elif element_counts.get(4, 0) > 0:
                message_type = "audio"
            elif element_counts.get(3, 0) > 0:
                message_type = "file"
            elif (element_counts.get(6, 0) > 0 or element_counts.get(11, 0) > 0) and not clean_text.strip():
                message_type = "emoji"

        nt_msg_type = None
        if isinstance(raw_message, dict):
            nt_msg_type = safe_int(raw_message.get("msgType"))
        if nt_msg_type is None:
            nt_msg_type = safe_int(m.get("messageType"))

        msg = Message(
            id=f"tmp:{idx}",
            message_id=message_id,
            message_seq=message_seq,
            msg_random=msg_random,
            conversation_id=conversation_id,
            timestamp_ms=ts_ms,
            sender_participant_id=sender_pid,
            sender_name=sender_display,
            is_system=is_system,
            is_recalled=is_recalled,
            message_type=message_type,
            nt_msg_type=nt_msg_type,
            graytip_subtype=graytip_subtype,
            graytip_xml_busi_type=graytip_xml_busi_type,
            recall_operator_uid=recall_operator_uid,
            recall_operator_uin=recall_operator_uin,
            text=clean_text,
            content_text=content_text,
            element_counts=element_counts,
            mentions=mentions,
            reply_to=reply_to,
        )
        conv.messages.append(msg)

    conv.participants = list(participants_by_id.values())
    conv.message_count_raw = len(conv.messages)

    # chatInfo.type 可能不可靠：按参与者数量做兜底推断
    inferred = None
    if len(conv.participants) == 2:
        inferred = "private"
    elif len(conv.participants) > 2:
        inferred = "group"

    if inferred and conv.type != inferred:
        warnings.append(f"chatInfo.type={conv.type} 与参与者数量不一致，已按人数推断为 {inferred}")
        conv.type = inferred

    # 统一把 message.sender_name 归一化为最终 participant.display_name（避免前后消息名字不一致）
    pid_to_name = {p.participant_id: p.display_name for p in participants_by_id.values()}
    for msg in conv.messages:
        if msg.sender_participant_id and msg.sender_participant_id in pid_to_name:
            msg.sender_name = pid_to_name[msg.sender_participant_id]

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

        # TXT importer 只保留文本与 mentions；媒体/链接由旧分析器自行启发式判断

        mentions: List[Mention] = []
        for m in ld.mentions or []:
            mentions.append(Mention(target_participant_id=participant_id_from_uid_uin(uin=m), target_name=str(m), target_uin=str(m)))

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
        )
        conv.messages.append(msg)

    conv.participants = list(participants_by_id.values())
    conv.message_count_raw = len(conv.messages)

    if len(conv.participants) == 2:
        conv.type = "private"
    elif len(conv.participants) > 2:
        conv.type = "group"

    return conv, warnings
