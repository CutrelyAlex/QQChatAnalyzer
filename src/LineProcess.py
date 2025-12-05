import re
from datetime import datetime
from typing import List, Dict, Tuple

try:
    from .utils import (
        parse_timestamp, SYSTEM_QQ_NUMBERS, TIME_LINE_PATTERN,
        clean_message_content, has_link, extract_qq_mentions
    )
except ImportError:
    from utils import (
        parse_timestamp, SYSTEM_QQ_NUMBERS, TIME_LINE_PATTERN,
        clean_message_content, has_link, extract_qq_mentions
    )


class LineData:
    def __init__(self, raw_text, clean_text, char_count, timepat, qq, sender, image_count, emoji_count, mentions=None, has_link=False, is_recall=False):
        self.raw_text = raw_text
        self.clean_text = clean_text
        self.char_count = char_count
        self.timepat = timepat
        self.qq = qq
        self.sender = sender
        self.image_count = image_count
        self.emoji_count = emoji_count
        self.mentions = mentions if mentions else []  # @他人的QQ列表
        self.has_link = has_link  # 是否包含链接
        self.is_recall = is_recall  # 是否为撤回消息
        
    def get_date(self) -> str:
        """获取日期 YYYY-MM-DD"""
        return self.timepat.split(' ')[0] if self.timepat else ""

    def get_time(self) -> str:
        """获取时间 HH:MM:SS"""
        return self.timepat.split(' ')[1] if self.timepat else ""
    
    def get_hour(self) -> int:
        """获取小时（0-23）"""
        dt = parse_timestamp(self.timepat)
        return dt.hour if dt else -1
    
    def get_month(self) -> str:
        """获取月份 YYYY-MM"""
        dt = parse_timestamp(self.timepat)
        return dt.strftime('%Y-%m') if dt else ""
    
    def get_weekday(self) -> int:
        """获取周几 0=Monday, 6=Sunday"""
        dt = parse_timestamp(self.timepat)
        return dt.weekday() if dt else -1
    
    def get_message_type(self) -> str:
        """获取消息类型: text/image/emoji/link/recall"""
        if self.is_recall:
            return 'recall'
        if self.image_count > 0:
            return 'image'
        if self.emoji_count > 0:
            return 'emoji'
        if self.has_link:
            return 'link'
        return 'text'


def process_lines_data(file_name, mode, part_name=None):
    all_lines = []
    all_linesData = []
    qq_to_name_map = {}  # QQ到所有昵称的映射：{qq: set(昵称1, 昵称2, ...)}
    time_pattern = TIME_LINE_PATTERN

    with open(file_name, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m = time_pattern.match(line)
        if m:
            timepat = m.group(1)
            sender = m.group(2)
            qq = m.group(3)
            
            # 过滤系统QQ号的消息（QQ 10000 和 1000000）
            if qq in SYSTEM_QQ_NUMBERS:
                i += 1
                # 如果下一行是消息内容（不是时间戳），也跳过
                if i < len(lines):
                    next_line = lines[i].strip()
                    if not time_pattern.match(next_line):
                        i += 1
                continue
            
            # 消息内容可能在下一行
            content = ""
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                # 如果下一行不是时间行，则为内容
                if not time_pattern.match(next_line):
                    content = next_line
                    i += 1  # 跳过内容行
            # 过滤模式
            if mode == 'part' and part_name and qq not in part_name:
                i += 1
                continue
            clean_text = clean_message_content(content)
            char_count = len(clean_text)
            image_count = content.count('[图片]')
            emoji_count = content.count('[表情]')
            
            # 新增：@检测
            mentions = extract_qq_mentions(content)
            mentioned_qqs = [m[1] for m in mentions]
            
            # 新增：链接检测
            content_has_link = has_link(content)
            
            # 新增：撤回消息检测
            is_recall = "撤回了一条消息" in content
            
            all_lines.append(content)
            line_data = LineData(
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
                is_recall=is_recall
            )
            all_linesData.append(line_data)
            
            # 新增：收集同一QQ的所有昵称（历史昵称）
            if qq and sender:
                if qq not in qq_to_name_map:
                    qq_to_name_map[qq] = set()
                qq_to_name_map[qq].add(sender)
        i += 1
    
    # 将set转换为list，便于后续使用
    qq_to_name_map = {qq: list(names) for qq, names in qq_to_name_map.items()}
    
    return all_lines, all_linesData, qq_to_name_map

def process_lines(file_path, mode='all', part_name=None):
    if part_name is None:
        part_name = ["None"]
    
    with open(file_path, "r", encoding="utf-8") as file:
        timepat = re.compile(r"\d{4}-\d{1,2}-\d{1,2}")

        flag = 0
        lines = file.readlines()
        selected_lines = []
        all_lines = []
        for line in lines:
            
            line = line.replace("[图片]", "").replace("[表情]", "").replace("\n", "").replace("撤回了一条消息", "")
            if not(re.search(timepat, line) or ("@" in line)):
                all_lines.append(line)
            if flag == "part" and not("@" in line):
                selected_lines.append(line)
                flag = 0
            if re.search(timepat, line):
                for w in part_name:
                    if w in line:
                        flag = "part"
                        break

        if mode == 'part':
            return selected_lines
        return all_lines