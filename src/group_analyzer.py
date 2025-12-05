"""
群体分析模块 - 分析群聊的整体特征和数据
"""

from collections import defaultdict, Counter
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any
import json
import re

try:
    # 当作为包导入时
    from .LineProcess import process_lines_data, LineData
    from .CutWords import cut_words
    from .RemoveWords import remove_words
    from .utils import parse_timestamp, SYSTEM_QQ_NUMBERS, EMOJI_PATTERN
except ImportError:
    # 当直接执行时
    from LineProcess import process_lines_data, LineData
    from CutWords import cut_words
    from RemoveWords import remove_words
    from utils import parse_timestamp, SYSTEM_QQ_NUMBERS, EMOJI_PATTERN


class GroupStats:
    """群体统计数据容器"""
    
    def __init__(self):
        # 群活跃度指标
        self.total_messages = 0
        self.daily_average = 0.0
        self.monthly_trend = {}  # {month: count}
        self.hourly_peak = 0
        self.peak_hours = []
        
        # 成员分层 - 现在包含 QQ 和昵称
        self.core_members = []      # [{'qq': qq, 'name': name, 'count': count}, ...]
        self.active_members = []    # 10%-40%
        self.normal_members = []    # 40%-80%
        self.lurkers = []           # Bottom 20%
        self.member_message_count = {}  # {qq: {'name': name, 'count': count}}
        
        # 消息类型分析
        self.text_ratio = 0.0
        self.image_ratio = 0.0
        self.emoji_ratio = 0.0
        self.link_ratio = 0.0
        self.forward_ratio = 0.0
        
        # 热词和表情
        self.hot_words = []         # [(word, count), ...]
        self.hot_emojis = []        # [(emoji, count), ...]
        
        # 7*24热力图
        self.heatmap = {}           # {day*24+hour: count}
        
        # 新增：时段和日期统计分析
        self.hourly_top_users = {}     # {hour: {'qq': qq, 'name': name, 'count': count}} 每小时最活跃用户
        self.weekday_top_users = {}    # {weekday: {'qq': qq, 'name': name, 'count': count}} 每日最活跃用户 (0=周一)
        self.weekday_totals = {}       # {weekday: count} 全年各星期几的总消息数 (0=周一)
        
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            'total_messages': self.total_messages,
            'daily_average': round(self.daily_average, 2),
            'monthly_trend': self.monthly_trend,
            'hourly_peak': self.hourly_peak,
            'peak_hours': self.peak_hours,
            'core_members': self.core_members,
            'active_members': self.active_members,
            'normal_members': self.normal_members,
            'lurkers': self.lurkers,
            'member_message_count': self.member_message_count,
            'text_ratio': round(self.text_ratio, 2),
            'image_ratio': round(self.image_ratio, 2),
            'emoji_ratio': round(self.emoji_ratio, 2),
            'link_ratio': round(self.link_ratio, 2),
            'forward_ratio': round(self.forward_ratio, 2),
            # 转换热词格式: [(word, count)] -> [{word, count}]
            'hot_words': [{'word': w, 'count': c} for w, c in self.hot_words[:20]],
            'hot_emojis': [{'emoji': e, 'count': c} for e, c in self.hot_emojis[:10]],
            'heatmap': self.heatmap,
            # 新增时段分析
            'hourly_top_users': self.hourly_top_users,
            'weekday_top_users': self.weekday_top_users,
            'weekday_totals': self.weekday_totals
        }


class GroupAnalyzer:
    """群体分析器 - 分析群聊的整体特征"""
    
    def __init__(self):
        self.lines_data = []  # LineData对象列表
        self.stats = GroupStats()
        self.qq_to_name = {}  # QQ -> 昵称映射
    
    def load_messages_from_file(self, filepath: str) -> None:
        """
        从文件加载消息并预处理
        
        Args:
            filepath: 聊天记录文件路径
        """
        # 使用 LineProcess 加载和预处理数据（现在返回 qq_to_name_map）
        all_lines, all_lines_data, qq_to_name_map = process_lines_data(filepath, mode='all')
        self.lines_data = all_lines_data
        self.qq_to_name = qq_to_name_map
    
    def load_messages(self, messages: List[Dict[str, Any]]) -> None:
        """
        加载消息列表（API 调用方式）
        
        Args:
            messages: 消息列表，每条消息包含: qq, time, content, sender等字段
        """
        self.lines_data = []
        for msg in messages:
            qq = msg.get('qq', '')
            
            # 过滤系统QQ号
            if qq in SYSTEM_QQ_NUMBERS:
                continue
            
            line_data = LineData(
                raw_text=msg.get('content', ''),
                clean_text=msg.get('content', '').replace('[图片]', '').replace('[表情]', '').replace('撤回了一条消息', ''),
                char_count=len(msg.get('content', '')),
                timepat=msg.get('time', ''),
                qq=qq,
                sender=msg.get('sender', ''),
                image_count=msg.get('content', '').count('[图片]'),
                emoji_count=msg.get('content', '').count('[表情]'),
                mentions=[],  # 从 content 中提取
                has_link='http://' in msg.get('content', '') or 'https://' in msg.get('content', ''),
                is_recall='撤回了一条消息' in msg.get('content', '')
            )
            self.lines_data.append(line_data)
            
            # 构建映射
            if line_data.qq not in self.qq_to_name:
                self.qq_to_name[line_data.qq] = line_data.sender
    
    def analyze(self) -> GroupStats:
        """
        执行完整的群体分析

        Returns:
            GroupStats对象
        """
        if not self.lines_data:
            return self.stats

        # 按顺序执行各项分析
        self._analyze_activity_metrics()
        self._analyze_member_stratification()
        self._analyze_message_types()
        self._extract_hot_content()
        self._build_heatmap()
        self._analyze_time_based_top_users()  # 新增：时段和日期统计

        return self.stats   
    
    def _analyze_activity_metrics(self) -> None:
        """T022: 分析群活跃度指标 - 总消息、日均、月度趋势、高峰时段"""
        # 总消息数
        self.stats.total_messages = len(self.lines_data)
        
        if not self.lines_data:
            return
        
        # 计算活跃天数
        unique_dates = {}  # {date: True}
        monthly_count = defaultdict(int)
        hourly_count = defaultdict(int)
        
        for line_data in self.lines_data:
            date = line_data.get_date()
            if date:
                unique_dates[date] = True
            
            # 同步收集月度和时段统计
            timepat = line_data.timepat
            dt = parse_timestamp(timepat)
            if dt:
                month_key = dt.strftime('%Y-%m')
                monthly_count[month_key] += 1
                hourly_count[dt.hour] += 1
        
        active_days = len(unique_dates)
        
        # 日均消息数
        if active_days > 0:
            self.stats.daily_average = self.stats.total_messages / active_days
        
        self.stats.monthly_trend = dict(sorted(monthly_count.items()))
        
        # 高峰时段
        if hourly_count:
            max_hour_count = max(hourly_count.values())
            self.stats.hourly_peak = max_hour_count
            self.stats.peak_hours = [
                hour for hour, count in hourly_count.items() 
                if count >= max_hour_count * 0.8
            ]
            self.stats.peak_hours.sort()
    
    def _analyze_member_stratification(self) -> None:
        """T023: 实现成员分层统计 - 核心/活跃/普通/潜水成员分类"""
        # 统计每个成员的发言次数
        member_count = defaultdict(int)
        
        for line_data in self.lines_data:
            qq = line_data.qq
            if qq:
                member_count[qq] += 1
        
        if not member_count:
            return
        
        # 按消息数排序
        sorted_members = sorted(member_count.items(), key=lambda x: x[1], reverse=True)
        total_members = len(sorted_members)
        
        # 分层阈值
        top_10_idx = max(1, int(total_members * 0.1))
        top_40_idx = max(top_10_idx + 1, int(total_members * 0.4))
        top_80_idx = max(top_40_idx + 1, int(total_members * 0.8))
        
        # 构建成员信息字典，包含昵称
        def build_member_info(qq, count):
            name = self.qq_to_name.get(qq, qq)  # 如果没有昵称则用QQ
            return {
                'qq': qq,
                'name': name,
                'count': count
            }
        
        # 分层成员（包含昵称）
        self.stats.core_members = [build_member_info(m[0], m[1]) for m in sorted_members[:top_10_idx]]
        self.stats.active_members = [build_member_info(m[0], m[1]) for m in sorted_members[top_10_idx:top_40_idx]]
        self.stats.normal_members = [build_member_info(m[0], m[1]) for m in sorted_members[top_40_idx:top_80_idx]]
        self.stats.lurkers = [build_member_info(m[0], m[1]) for m in sorted_members[top_80_idx:]]
        
        # 成员消息计数（包含昵称）
        self.stats.member_message_count = {
            qq: {'name': self.qq_to_name.get(qq, qq), 'count': count} 
            for qq, count in member_count.items()
        }
    
    def _analyze_message_types(self) -> None:
        """T024: 实现消息类型分析 - 文字/图片/表情/链接/转发占比"""
        if not self.stats.total_messages:
            return
        
        text_count = 0
        image_count = 0
        emoji_count = 0
        link_count = 0
        forward_count = 0
        
        for line_data in self.lines_data:
            # 检测消息类型
            if line_data.image_count > 0:
                image_count += 1
            elif line_data.emoji_count > 0:
                emoji_count += 1
            elif line_data.has_link:
                link_count += 1
            elif line_data.is_recall:
                forward_count += 1
            elif line_data.clean_text.strip():
                text_count += 1
        
        total = text_count + image_count + emoji_count + link_count + forward_count
        if total == 0:
            total = 1
        
        self.stats.text_ratio = text_count / total
        self.stats.image_ratio = image_count / total
        self.stats.emoji_ratio = emoji_count / total
        self.stats.link_ratio = link_count / total
        self.stats.forward_ratio = forward_count / total
    
    def _extract_hot_content(self) -> None:
        """T025: 提取热词"""
        # 收集所有文本内容，排除图片等非文本
        all_text_lines = []
        emoji_count = defaultdict(int)
        
        for line_data in self.lines_data:
            if '[图片]' not in line_data.raw_text and line_data.clean_text.strip():
                all_text_lines.append(line_data.clean_text)
            
            # 同步提取表情
            content = line_data.raw_text
            emojis = EMOJI_PATTERN.findall(content)
            for emoji in emojis:
                if '表情' not in emoji and '图' not in emoji:
                    emoji_count[emoji] += 1
        
        if all_text_lines:
            # 使用 CutWords 进行分词和热词提取，使用 RemoveWords 作为停用词
            try:
                # 提取所有昵称列表
                nicknames = list(self.qq_to_name.values()) if self.qq_to_name else []
                word_counts, words_top = cut_words(all_text_lines, top_words_num=20, nicknames=nicknames)
                self.stats.hot_words = words_top
            except Exception as e:
                print(f"分词失败: {e}")
                self.stats.hot_words = []
        
        self.stats.hot_emojis = sorted(emoji_count.items(), key=lambda x: x[1], reverse=True)[:10]
    
    def _build_heatmap(self) -> None:
        """T026: 构建7*24热力图 - 按周x小时统计消息分布"""
        # 初始化热力图 (7天 * 24小时 = 168个格子)
        heatmap = defaultdict(int)
        
        for line_data in self.lines_data:
            dt = parse_timestamp(line_data.timepat)
            if dt:
                # weekday: 0=Monday, 6=Sunday
                day = dt.weekday()
                hour = dt.hour
                # 格子索引: day*24 + hour
                key = day * 24 + hour
                heatmap[key] += 1
        
        # 转换为标准格式：{day*24+hour: count}
        self.stats.heatmap = dict(heatmap)
    
    def _analyze_time_based_top_users(self) -> None:
        """分析每个时段和每天最活跃的用户，以及全年各星期几的总消息数"""
        # 统计每小时每人的消息数: {hour: {qq: count}}
        hourly_user_count = defaultdict(lambda: defaultdict(int))
        # 统计每个星期几每人的消息数: {weekday: {qq: count}}
        weekday_user_count = defaultdict(lambda: defaultdict(int))
        # 统计全年各星期几的总消息数
        weekday_totals = defaultdict(int)
        
        for line_data in self.lines_data:
            dt = parse_timestamp(line_data.timepat)
            if dt and line_data.qq:
                hour = dt.hour
                weekday = dt.weekday()  # 0=周一, 6=周日
                qq = line_data.qq
                
                hourly_user_count[hour][qq] += 1
                weekday_user_count[weekday][qq] += 1
                weekday_totals[weekday] += 1
        
        # 找出每小时最活跃的用户
        hourly_top_users = {}
        for hour in range(24):
            if hourly_user_count[hour]:
                # 找出消息最多的用户
                top_qq = max(hourly_user_count[hour].items(), key=lambda x: x[1])
                hourly_top_users[hour] = {
                    'qq': top_qq[0],
                    'name': self.qq_to_name.get(top_qq[0], top_qq[0]),
                    'count': top_qq[1]
                }
        
        # 找出每个星期几最活跃的用户
        weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        weekday_top_users = {}
        for weekday in range(7):
            if weekday_user_count[weekday]:
                top_qq = max(weekday_user_count[weekday].items(), key=lambda x: x[1])
                weekday_top_users[weekday] = {
                    'weekday_name': weekday_names[weekday],
                    'qq': top_qq[0],
                    'name': self.qq_to_name.get(top_qq[0], top_qq[0]),
                    'count': top_qq[1]
                }
        
        # 格式化星期几总消息数
        weekday_totals_formatted = {
            weekday: {
                'weekday_name': weekday_names[weekday],
                'count': weekday_totals[weekday]
            }
            for weekday in range(7)
        }
        
        self.stats.hourly_top_users = hourly_top_users
        self.stats.weekday_top_users = weekday_top_users
        self.stats.weekday_totals = weekday_totals_formatted
