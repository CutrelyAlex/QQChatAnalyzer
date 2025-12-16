"""TXT 导入。

目标：
- 把 TXT 聊天记录解析为 chat_import.schema.Conversation/Message
- 统一通过 elements 体系表达非文本信息：使用 element_counts (ElementType -> count)

TXT 行格式：
- 时间行：YYYY-MM-DD HH:MM:SS 昵称(QQ)
- 内容行：紧随其后一行（如果下一行不是时间行）

说明：
- TXT 没有 uid 概念，因此 participant_id 等同于 uin
- TXT 里出现的 [图片] / [表情] 等占位符，会被映射为 element_counts（图片=2，表情=6）
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .core import participant_id_from_uid_uin
from .schema import Conversation, Mention, Message, Participant

from ..txt_process import (
    SYSTEM_QQ_NUMBERS,
    TIME_LINE_PATTERN,
    clean_message_content,
    extract_qq_mentions,
    has_link,
    parse_timestamp,
)


@dataclass
class LineData:
    """TXT 的单条消息解析结果。"""

    raw_text: str
    clean_text: str
    char_count: int
    timepat: str
    qq: str
    sender: str
    image_count: int
    emoji_count: int
    mentions: List[str]
    has_link: bool
    is_recall: bool

    def get_date(self) -> str:
        return self.timepat.split(' ')[0] if self.timepat else ""

    def get_time(self) -> str:
        return self.timepat.split(' ')[1] if self.timepat else ""

    def get_message_type(self) -> str:
        if self.is_recall:
            return 'recall'
        if self.image_count > 0:
            return 'image'
        if self.emoji_count > 0:
            return 'emoji'
        if self.has_link:
            return 'link'
        return 'text'


def process_lines_data(file_name: str, mode: str, part_name: Optional[List[str]] = None):
    """解析 TXT，返回 (all_lines, all_lines_data, qq_to_name_map)。
    """

    if part_name is None:
        part_name = []

    all_lines: List[str] = []
    all_lines_data: List[LineData] = []
    qq_to_name_map: Dict[str, set] = {}

    with open(file_name, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m = TIME_LINE_PATTERN.match(line)
        if not m:
            i += 1
            continue

        timepat = m.group(1)
        sender = m.group(2)
        qq = m.group(3)

        # 过滤系统 QQ 的消息
        if qq in SYSTEM_QQ_NUMBERS:
            i += 1
            if i < len(lines):
                next_line = lines[i].strip()
                if not TIME_LINE_PATTERN.match(next_line):
                    i += 1
            continue

        # 内容可能在下一行
        content = ""
        if i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if not TIME_LINE_PATTERN.match(next_line):
                content = next_line
                i += 1

        # part 过滤
        if mode == 'part' and part_name and (qq not in part_name):
            i += 1
            continue

        # counts
        image_count = content.count('[图片]')
        emoji_count = content.count('[表情]')
        content_has_link = has_link(content)
        is_recall = ('撤回了一条消息' in content)

        clean_text = clean_message_content(content)
        char_count = len(clean_text)

        mentions_pairs = extract_qq_mentions(content)
        mentioned_qqs = [p[1] for p in mentions_pairs] if mentions_pairs else []

        all_lines.append(content)
        all_lines_data.append(
            LineData(
                raw_text=content,
                clean_text=clean_text,
                char_count=char_count,
                timepat=timepat,
                qq=qq,
                sender=sender,
                image_count=image_count,
                emoji_count=emoji_count,
                mentions=mentioned_qqs,
                has_link=content_has_link,
                is_recall=is_recall,
            )
        )

        # 收集历史昵称
        if qq and sender:
            qq_to_name_map.setdefault(qq, set()).add(sender)

        i += 1

    qq_to_name_map_list = {qq: list(names) for qq, names in qq_to_name_map.items()}
    return all_lines, all_lines_data, qq_to_name_map_list


def load_conversation_from_txt(file_path: str) -> Tuple[Conversation, List[str]]:
    """把旧 TXT 转换为归一化 Conversation（elements 体系）。"""

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

        sender_pid = participant_id_from_uid_uin(uin=ld.qq, fallback_name=ld.sender)

        if sender_pid not in participants_by_id:
            participants_by_id[sender_pid] = Participant(
                participant_id=sender_pid,
                uin=str(ld.qq) if ld.qq else None,
                uid=None,
                display_name=ld.sender or (ld.qq or "unknown"),
                member_names=(str(ld.sender).strip(),) if (ld.sender and str(ld.sender).strip()) else (),
            )

        # elements 统计
        element_counts: Dict[int, int] = {}
        if ld.image_count:
            element_counts[2] = int(ld.image_count)
        if ld.emoji_count:
            element_counts[6] = int(ld.emoji_count)

        mentions: List[Mention] = []
        for target_uin in ld.mentions or []:
            pid = participant_id_from_uid_uin(uin=target_uin)
            mentions.append(
                Mention(
                    target_participant_id=pid,
                    target_name=str(target_uin),
                    target_uin=str(target_uin),
                )
            )

        msg = Message(
            id=f"tmp:{idx}",
            message_id=None,
            message_seq=None,
            msg_random=None,
            conversation_id=conversation_id,
            timestamp_ms=ts_ms,
            sender_participant_id=sender_pid,
            sender_name=ld.sender,
            is_system=False,
            is_recalled=bool(ld.is_recall),
            message_type=ld.get_message_type(),
            text=ld.clean_text or "",
            content_text=ld.clean_text or "",
            element_counts=element_counts,
            mentions=mentions,
            reply_to=None,
        )
        conv.messages.append(msg)

    conv.participants = list(participants_by_id.values())
    conv.message_count_raw = len(conv.messages)

    if len(conv.participants) == 2:
        conv.type = "private"
    elif len(conv.participants) > 2:
        conv.type = "group"

    return conv, warnings
