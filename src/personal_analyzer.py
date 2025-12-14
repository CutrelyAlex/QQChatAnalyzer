"""
个人分析模块 - 分析单个用户的聊天行为
"""

import re
from datetime import datetime
from collections import defaultdict, Counter

from .CutWords import cut_words
from .RemoveWords import remove_words
from .LineProcess import process_lines_data, LineData
from .utils import (
    TIME_LINE_PATTERN,
    MENTION_PATTERN,
    HTTP_PATTERN,
    SYSTEM_QQ_NUMBERS,
    parse_hour_from_time,
    clean_message_content,
)

# 局部别名（避免重复属性查找/保持现有代码结构）
_TIME_PATTERN = TIME_LINE_PATTERN
_MENTION_PATTERN = MENTION_PATTERN
_HTTP_PATTERN = HTTP_PATTERN
_AT_NAME_PATTERN = re.compile(r'@(\S+)')


class PersonalStats:
    """个人统计数据类"""
    
    def __init__(self, qq, nickname=None):
        self.qq = qq
        self.nickname = nickname or qq
        
        # 基本统计
        self.total_messages = 0
        self.active_days = set()
        self.first_message_date = None
        self.last_message_date = None
        
        # 月度和周统计
        self.monthly_messages = defaultdict(int)  # {YYYY-MM: count}
        self.weekly_messages = [0] * 7  # 0=周一, 6=周日
        
        # 时段分布 (6个时段)
        self.time_distribution = {
            'night': 0,      # 00:00-06:00
            'early_morning': 0,  # 06:00-09:00
            'morning': 0,    # 09:00-12:00
            'afternoon': 0,  # 12:00-18:00
            'evening': 0,    # 18:00-21:00
            'night_late': 0  # 21:00-24:00
        }
        self.user_type = None  # 夜猫子/早起鸟/活跃/普通
        
        # 互动指标
        self.at_count = 0  # @他人次数
        self.being_at_count = 0  # 被@次数
        self.reply_count = 0  # 回复次数
        self.top_interactions = []  # [(qq, count), ...]
        
        # 内容特征
        self.avg_message_length = 0
        self.image_count = 0
        self.emoji_count = 0
        self.link_count = 0
        self.forward_count = 0
        self.file_count = 0
        self.recall_count = 0
        self.system_count = 0
        
        # 关键词
        self.top_words = []  # [(word, count), ...]
        
        # 连续发言记录
        self.max_streak_days = 0
        self.current_streak_days = 0
        self.message_dates = []
    
    def to_dict(self):
        """转换为字典"""
        return {
            'qq': self.qq,
            'nickname': self.nickname,
            'total_messages': self.total_messages,
            'active_days': len(self.active_days),
            'first_message_date': self.first_message_date,
            'last_message_date': self.last_message_date,
            'monthly_messages': dict(self.monthly_messages),
            'time_distribution': self.time_distribution,
            'user_type': self.user_type,
            'at_count': self.at_count,
            'being_at_count': self.being_at_count,
            'reply_count': self.reply_count,
            'top_interactions': self.top_interactions[:5],
            'avg_message_length': round(self.avg_message_length, 2),
            'image_count': self.image_count,
            'emoji_count': self.emoji_count,
            'link_count': self.link_count,
            'forward_count': self.forward_count,
            'file_count': self.file_count,
            'recall_count': self.recall_count,
            'system_count': self.system_count,
            # 转换热词格式: [(word, count)] -> [{word, count}]
            'top_words': [{'word': w, 'count': c} for w, c in self.top_words[:20]],
            'max_streak_days': self.max_streak_days
        }


class PersonalAnalyzer:
    """个人分析器"""
    
    def __init__(self):
        # 使用 RemoveWords 作为停用词
        self.stopwords = set(remove_words)
    
    def analyze_file(self, filepath, qq_list=None):
        """
        分析聊天记录文件

        Args:
            filepath: 文件路径
            qq_list: 要分析的QQ号列表，如果为None则分析所有

        Returns:
            {qq: PersonalStats}
        """
        stats_dict = {}

        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 第一遍：收集所有QQ和基本信息
        qq_names = {}  # {qq: name}
        name_to_qq = {}  # {name: qq} 用于@检测
        for line in lines:
            line = line.strip()
            m = _TIME_PATTERN.match(line)
            if m:
                sender = m.group(2)
                qq = m.group(3)
                # 过滤系统QQ
                if qq not in SYSTEM_QQ_NUMBERS:
                    qq_names[qq] = sender
                    name_to_qq[sender] = qq
        
        # 初始化统计对象
        if qq_list:
            for qq in qq_list:
                stats_dict[qq] = PersonalStats(qq, qq_names.get(qq, qq))
        else:
            for qq, name in qq_names.items():
                stats_dict[qq] = PersonalStats(qq, name)
        
        # 第二遍：收集消息数据
        all_messages = []  # 用于后续分析
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            m = _TIME_PATTERN.match(line)
            if m:
                timestamp = m.group(1)
                sender = m.group(2)
                qq = m.group(3)
                content = ""
                
                # 过滤系统QQ
                if qq in SYSTEM_QQ_NUMBERS:
                    # 跳过系统消息的内容行
                    if i + 1 < len(lines) and not _TIME_PATTERN.match(lines[i + 1].strip()):
                        i += 1
                    i += 1
                    continue
                
                # 获取消息内容
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if not _TIME_PATTERN.match(next_line):
                        content = next_line
                        i += 1
                
                # 跳过不在qq_list中的QQ
                if qq not in stats_dict:
                    i += 1
                    continue
                
                all_messages.append({
                    'timestamp': timestamp,
                    'sender': sender,
                    'qq': qq,
                    'content': content
                })
            i += 1
        
        # 处理消息
        for msg in all_messages:
            self._process_message(msg, stats_dict, name_to_qq)
        
        # 后处理（计算派生指标）
        for qq, stats in stats_dict.items():
            self._post_process_stats(stats, all_messages, name_to_qq)
        
        return stats_dict    

    def analyze_messages(self, messages, qq_list=None, qq_names=None):
        """基于消息列表进行个人分析。

        说明：
        - 用于支持 JSON 导入后的统一分析流程（消息来自导入/归一化层）
        - messages 期望形态：[{time/sender/qq/content}, ...]
        - 为兼容旧内部实现，会把 time 映射为 timestamp

        Args:
            messages: 消息列表
            qq_list: 仅分析这些账号ID（为空则分析所有）
            qq_names: 可选的账号ID到显示名映射 {qq: name}

        Returns:
            {qq: PersonalStats}
        """
        stats_dict = {}

        if not messages:
            return stats_dict

        # 第一遍：收集所有账号与基本信息
        collected_qq_names = {}
        name_to_qq = {}
        for m in messages:
            qq = (m.get('qq') or '').strip()
            sender = (m.get('sender') or '').strip()
            if not qq:
                continue
            if qq in SYSTEM_QQ_NUMBERS:
                continue
            if sender:
                collected_qq_names[qq] = sender
                # 同名可能对应多个账号，优先保留首次出现
                if sender not in name_to_qq:
                    name_to_qq[sender] = qq

        # 合并外部提供的名称映射
        if isinstance(qq_names, dict):
            for k, v in qq_names.items():
                if k and v and k not in collected_qq_names:
                    collected_qq_names[str(k)] = str(v)

        # 初始化统计对象
        if qq_list:
            for qq in qq_list:
                qq = str(qq)
                stats_dict[qq] = PersonalStats(qq, collected_qq_names.get(qq, qq))
        else:
            for qq, name in collected_qq_names.items():
                stats_dict[qq] = PersonalStats(qq, name)

        # 第二遍：收集消息数据（对齐内部字段名 timestamp）
        all_messages = []
        for m in messages:
            qq = (m.get('qq') or '').strip()
            if not qq or qq in SYSTEM_QQ_NUMBERS:
                continue

            content = str(m.get('content', '') or '')
            is_system = bool(m.get('is_system'))
            is_recalled = bool(m.get('is_recalled')) or ('撤回了一条消息' in content)
            if is_system and (not is_recalled):
                continue

            if qq_list and qq not in stats_dict:
                continue

            ts = m.get('timestamp') or m.get('time') or ''
            all_messages.append({
                'timestamp': ts,
                'time': ts,
                'sender': m.get('sender', ''),
                'qq': qq,
                'content': content,

                # 结构化字段（可能为空）
                'is_system': is_system,
                'is_recalled': is_recalled,
                'message_type': m.get('message_type'),
                'resource_types': m.get('resource_types') if isinstance(m.get('resource_types'), list) else [],
                'mentions': m.get('mentions') if isinstance(m.get('mentions'), list) else [],
                'mention_count': int(m.get('mention_count') or 0),
                'reply_to_qq': m.get('reply_to_qq'),
            })

        # 处理消息
        for msg in all_messages:
            self._process_message(msg, stats_dict, name_to_qq)

        # 后处理（计算派生指标）
        for qq, stats in stats_dict.items():
            self._post_process_stats(stats, all_messages, name_to_qq)

        return stats_dict
    

    def _process_message(self, msg, stats_dict, name_to_qq=None):
        """处理单条消息
        
        Args:
            msg: 消息字典 {timestamp, sender, qq, content}
            stats_dict: 统计对象字典
            name_to_qq: 用户名到QQ的映射关系，用于检测@
        """
        qq = msg['qq']
        stats = stats_dict[qq]
        content = msg['content']
        timestamp = msg.get('timestamp') or msg.get('time') or ''
        
        # 基本统计
        stats.total_messages += 1
        
        # 日期处理
        if ' ' in timestamp:
            date_str, time_str = timestamp.split(' ', 1)
        else:
            # 时间格式异常时兜底
            date_str, time_str = (timestamp[:10] or 'unknown'), (timestamp[11:] if len(timestamp) > 11 else '00:00:00')
        stats.active_days.add(date_str)
        stats.message_dates.append(date_str)
        
        if not stats.first_message_date or date_str < stats.first_message_date:
            stats.first_message_date = date_str
        if not stats.last_message_date or date_str > stats.last_message_date:
            stats.last_message_date = date_str
        
        # 月度统计
        month_key = date_str[:7]  # YYYY-MM
        stats.monthly_messages[month_key] += 1
        
        # 周统计
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            weekday = (date_obj.weekday() + 1) % 7  # 转换为0=周日
            stats.weekly_messages[weekday] += 1
        except ValueError:
            pass
        
        # 时段分布 - 兼容 "0:30:00" 和 "00:30:00" 两种格式
        hour = parse_hour_from_time(time_str)
        if 0 <= hour < 6:
            stats.time_distribution['night'] += 1
        elif 6 <= hour < 9:
            stats.time_distribution['early_morning'] += 1
        elif 9 <= hour < 12:
            stats.time_distribution['morning'] += 1
        elif 12 <= hour < 18:
            stats.time_distribution['afternoon'] += 1
        elif 18 <= hour < 21:
            stats.time_distribution['evening'] += 1
        else:  # 21-24
            stats.time_distribution['night_late'] += 1
        
        # 内容特征
        # 统一清理逻辑：复用 utils.clean_message_content()
        # 说明：content 来源于 lines[i+1].strip()，不包含原始换行符，因此与旧 replace 逻辑结果一致。
        clean_content = clean_message_content(content)
        stats.avg_message_length += len(clean_content)
        rtypes = msg.get('resource_types')
        if not isinstance(rtypes, list):
            rtypes = []
        rtypes = [str(t) for t in rtypes if t]

        # media/link 优先用结构化资源类型
        if rtypes:
            stats.image_count += sum(1 for t in rtypes if t == 'image')
            stats.emoji_count += sum(1 for t in rtypes if t in ('emoji', 'sticker'))
            stats.link_count += 1 if ('link' in rtypes) else 0
            stats.forward_count += 1 if ('forward' in rtypes) else 0
            stats.file_count += sum(1 for t in rtypes if t == 'file')
        else:
            stats.image_count += content.count('[图片]')
            stats.emoji_count += content.count('[表情]')
            stats.link_count += len(_HTTP_PATTERN.findall(content))

        is_recalled = bool(msg.get('is_recalled')) or ('撤回了一条消息' in content)
        stats.recall_count += 1 if is_recalled else 0

        if bool(msg.get('is_system')):
            stats.system_count += 1

        # reply 次数
        if msg.get('reply_to_qq') or str(msg.get('message_type') or '') == 'reply':
            stats.reply_count += 1
        
        # @检测：优先用结构化 mentions
        mention_count = 0
        if isinstance(msg.get('mentions'), list) and msg.get('mentions'):
            mention_count = len([x for x in msg.get('mentions') if x])
        elif msg.get('mention_count'):
            try:
                mention_count = int(msg.get('mention_count') or 0)
            except Exception:
                mention_count = 0
        else:
            mentions = _MENTION_PATTERN.findall(content)
            mention_count = len(mentions)

        stats.at_count += mention_count
    
    def _post_process_stats(self, stats, all_messages, name_to_qq=None):
        """后处理统计数据
        
        Args:
            stats: 单个用户的统计对象
            all_messages: 所有消息列表
            name_to_qq: 用户名到QQ的映射
        """
        
        # 平均消息长度
        if stats.total_messages > 0:
            stats.avg_message_length = stats.avg_message_length / stats.total_messages
        
        # 识别用户类型
        total_time = sum(stats.time_distribution.values())
        if total_time > 0:
            night_ratio = (stats.time_distribution['night'] + stats.time_distribution['night_late']) / total_time
            early_ratio = stats.time_distribution['early_morning'] / total_time
            
            if night_ratio > 0.4:
                stats.user_type = '夜猫子'
            elif early_ratio > 0.15:
                stats.user_type = '早起鸟'
            else:
                stats.user_type = '活跃' if stats.total_messages > 100 else '普通'
        
        # 计算连续发言记录
        if stats.message_dates:
            sorted_dates = sorted(set(stats.message_dates))
            max_streak = 1
            current_streak = 1
            
            for i in range(1, len(sorted_dates)):
                current_date = datetime.strptime(sorted_dates[i], '%Y-%m-%d')
                prev_date = datetime.strptime(sorted_dates[i-1], '%Y-%m-%d')
                
                if (current_date - prev_date).days == 1:
                    current_streak += 1
                    max_streak = max(max_streak, current_streak)
                else:
                    current_streak = 1
            
            stats.max_streak_days = max_streak
        
        # 互动对象分析 - 统计此用户@了谁（结构化 mentions）
        interactions = Counter()
        for msg in all_messages:
            if msg['qq'] == stats.qq:
                if isinstance(msg.get('mentions'), list) and msg.get('mentions'):
                    for target in msg.get('mentions'):
                        if target:
                            interactions[str(target)] += 1
                else:
                    # 旧兜底：从文本里抓 @昵称
                    mentions = _AT_NAME_PATTERN.findall(msg['content'])
                    for mention_name in mentions:
                        if name_to_qq and mention_name in name_to_qq:
                            interactions[name_to_qq[mention_name]] += 1
                        else:
                            interactions[mention_name] += 1
        
        stats.top_interactions = interactions.most_common(10)
        
        # 计算此用户被@的次数（优先结构化 mentions）
        being_at_count = 0
        for msg in all_messages:
            if msg.get('qq') == stats.qq:
                continue
            if isinstance(msg.get('mentions'), list) and msg.get('mentions'):
                if stats.qq in [str(x) for x in msg.get('mentions') if x]:
                    being_at_count += 1
            else:
                mentions = _AT_NAME_PATTERN.findall(msg['content'])
                for mention_name in mentions:
                    if name_to_qq and mention_name in name_to_qq:
                        if name_to_qq[mention_name] == stats.qq:
                            being_at_count += 1
                    elif mention_name == stats.nickname:
                        being_at_count += 1
        
        stats.being_at_count = being_at_count
        
        # 热词提取 - 使用 CutWords 进行分词（默认排除系统/撤回）
        user_messages = []
        for msg in all_messages:
            if msg['qq'] == stats.qq:
                if msg.get('is_system') or msg.get('is_recalled'):
                    continue
                content = msg['content']
                # 清理内容
                clean = clean_message_content(content).strip()
                if clean and len(clean) > 1:
                    user_messages.append(clean)
        
        if user_messages:
            try:
                # 提取所有昵称列表
                nicknames = list(name_to_qq.keys()) if name_to_qq else []
                _, words_top = cut_words(user_messages, top_words_num=20, nicknames=nicknames)
                stats.top_words = words_top
            except Exception as e:
                print(f"个人热词分析失败: {e}")
                stats.top_words = []
    
    def get_user_stats(self, filepath, qq):
        """获取单个用户的统计"""
        stats_dict = self.analyze_file(filepath, [qq])
        return stats_dict.get(qq)

    def get_user_stats_from_messages(self, messages, qq, qq_names=None):
        """从消息列表获取单个用户的统计（用于 JSON/统一导入层）。"""
        stats_dict = self.analyze_messages(messages, [qq], qq_names=qq_names)
        return stats_dict.get(str(qq))
    
    def get_all_stats(self, filepath):
        """获取所有用户的统计"""
        return self.analyze_file(filepath)
