"""
群体分析模块 - 分析群聊的整体特征和数据
"""

from collections import defaultdict, Counter
from datetime import datetime
from typing import Dict, List, Any

from src.chat_import.enums import ElementType

from .chat_import.txt_importer import LineData
from .txt_process import cut_words, parse_timestamp, SYSTEM_QQ_NUMBERS, EMOJI_PATTERN, has_link

# 预热 jieba
import jieba
jieba.initialize()


class GroupStats:
    """群体统计数据容器"""
    
    def __init__(self):
        # 群活跃度指标
        self.total_messages = 0
        self.daily_average = 0.0
        self.monthly_trend = {}  # {month: count}
        self.hourly_peak = 0
        self.peak_hours = []
        self.peak_hour = None  # 最活跃小时（只取 1 个，例如 21 表示 21:00）
        
        # 成员分层 - 现在包含 QQ 和昵称
        self.core_members = []      # [{'qq': qq, 'name': name, 'count': count}, ...]
        self.active_members = []    # 10%-40%
        self.normal_members = []    # 40%-80%
        self.lurkers = []           # Bottom 20%
        self.member_message_count = {}  # {qq: {'name': name, 'count': count}}
        self.total_members = 0
        
        # 消息类型分析
        self.text_ratio = 0.0
        self.image_ratio = 0.0
        self.emoji_ratio = 0.0
        self.link_ratio = 0.0
        self.forward_ratio = 0.0

        # 结构化元数据计数
        self.system_messages = 0
        self.recalled_messages = 0
        self.mention_messages = 0
        self.reply_messages = 0
        self.media_messages = 0
        self.media_breakdown = {}  # {type: count}
        
        # 热词和表情
        self.hot_words = []         # [(word, count), ...]
        self.hot_emojis = []        # [(emoji, count), ...]
        
        # 7*24热力图
        self.heatmap = {}           # {day*24+hour: count}
        
        # 时段和日期统计分析
        self.hourly_top_users = {}     # {hour: {'qq': qq, 'name': name, 'count': count}} 每小时最活跃用户
        self.weekday_top_users = {}    # {weekday: {'qq': qq, 'name': name, 'count': count}} 每日最活跃用户 (0=周一)
        self.weekday_totals = {}       # {weekday: count} 全年各星期几的总消息数 (0=周一)

        # 各类行为“最多的人”（包含数值）
        self.top_recaller = None        # {'qq': qq, 'name': name, 'count': count}
        self.top_image_sender = None
        self.top_emoji_sender = None
        self.top_forward_sender = None
        self.top_file_sender = None
        self.top_wallet_sender = None
        self.top_system_sender = None
        self.top_mention_sender = None
        self.top_reply_sender = None
        self.top_media_sender = None
        self.element_totals: Dict[int, int] = {}
        self.top_element_senders: Dict[str, Dict[str, Any]] = {}  # {'9': {qq,name,count}, ...}

        # ------------------------------
        # 各 ElementType 元素数量
        # ------------------------------
        self.element_text_count = 0
        self.element_pic_count = 0
        self.element_file_count = 0
        self.element_ptt_count = 0
        self.element_video_count = 0
        self.element_face_count = 0
        self.element_reply_count = 0
        self.element_greytip_count = 0
        self.element_wallet_count = 0
        self.element_ark_count = 0
        self.element_mface_count = 0
        self.element_livegift_count = 0
        self.element_structlongmsg_count = 0
        self.element_markdown_count = 0
        self.element_giphy_count = 0
        self.element_multiforward_count = 0
        self.element_inlinekeyboard_count = 0
        self.element_intextgift_count = 0
        self.element_calendar_count = 0
        self.element_yologameresult_count = 0
        self.element_avrecord_count = 0
        self.element_feed_count = 0
        self.element_tofurecord_count = 0
        self.element_acebubble_count = 0
        self.element_activity_count = 0
        self.element_tofu_count = 0
        self.element_facebubble_count = 0
        self.element_sharelocation_count = 0
        self.element_tasktopmsg_count = 0
        self.element_recommendedmsg_count = 0
        self.element_actionbar_count = 0
        
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            'total_messages': self.total_messages,
            'daily_average': round(self.daily_average, 2),
            'monthly_trend': self.monthly_trend,
            'hourly_peak': self.hourly_peak,
            'peak_hours': self.peak_hours,
            'peak_hour': self.peak_hour,
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

            # 结构化元数据计数
            'system_messages': int(self.system_messages),
            'recalled_messages': int(self.recalled_messages),
            'mention_messages': int(self.mention_messages),
            'reply_messages': int(self.reply_messages),
            'media_messages': int(self.media_messages),
            'media_breakdown': self.media_breakdown or {},
            # 转换热词格式: [(word, count)] -> [{word, count}]
            'hot_words': [{'word': w, 'count': c} for w, c in self.hot_words[:20]],
            'hot_emojis': [{'emoji': e, 'count': c} for e, c in self.hot_emojis[:10]],
            'heatmap': self.heatmap,
            # 新增时段分析
            'hourly_top_users': self.hourly_top_users,
            'weekday_top_users': self.weekday_top_users,
            'weekday_totals': self.weekday_totals,

            # 新增：各类行为“最多的人”
            'top_recaller': self.top_recaller,
            'top_image_sender': self.top_image_sender,
            'top_emoji_sender': self.top_emoji_sender,
            'top_forward_sender': self.top_forward_sender,
            'top_file_sender': self.top_file_sender,
            'top_wallet_sender': self.top_wallet_sender,
            'top_system_sender': self.top_system_sender,
            'top_mention_sender': self.top_mention_sender,
            'top_reply_sender': self.top_reply_sender,
            'top_media_sender': self.top_media_sender,
            'element_totals': dict(self.element_totals or {}),
            'top_element_senders': dict(self.top_element_senders or {}),
            'total_members': self.total_members,

            # ElementType 全量计数
            'element_text_count': int(self.element_text_count),
            'element_pic_count': int(self.element_pic_count),
            'element_file_count': int(self.element_file_count),
            'element_ptt_count': int(self.element_ptt_count),
            'element_video_count': int(self.element_video_count),
            'element_face_count': int(self.element_face_count),
            'element_reply_count': int(self.element_reply_count),
            'element_greytip_count': int(self.element_greytip_count),
            'element_wallet_count': int(self.element_wallet_count),
            'element_ark_count': int(self.element_ark_count),
            'element_mface_count': int(self.element_mface_count),
            'element_livegift_count': int(self.element_livegift_count),
            'element_structlongmsg_count': int(self.element_structlongmsg_count),
            'element_markdown_count': int(self.element_markdown_count),
            'element_giphy_count': int(self.element_giphy_count),
            'element_multiforward_count': int(self.element_multiforward_count),
            'element_inlinekeyboard_count': int(self.element_inlinekeyboard_count),
            'element_intextgift_count': int(self.element_intextgift_count),
            'element_calendar_count': int(self.element_calendar_count),
            'element_yologameresult_count': int(self.element_yologameresult_count),
            'element_avrecord_count': int(self.element_avrecord_count),
            'element_feed_count': int(self.element_feed_count),
            'element_tofurecord_count': int(self.element_tofurecord_count),
            'element_acebubble_count': int(self.element_acebubble_count),
            'element_activity_count': int(self.element_activity_count),
            'element_tofu_count': int(self.element_tofu_count),
            'element_facebubble_count': int(self.element_facebubble_count),
            'element_sharelocation_count': int(self.element_sharelocation_count),
            'element_tasktopmsg_count': int(self.element_tasktopmsg_count),
            'element_recommendedmsg_count': int(self.element_recommendedmsg_count),
            'element_actionbar_count': int(self.element_actionbar_count),
        }


class GroupAnalyzer:
    """群体分析器 - 分析群聊的整体特征"""
    
    def __init__(self):
        self.lines_data = []  # LineData对象列表
        self.stats = GroupStats()
        self.qq_to_name = {}  # QQ -> 昵称映射
    
    def load_messages(self, messages: List[Dict[str, Any]]) -> None:
        """
        加载消息列表（API 调用方式）
        
        Args:
            messages: 消息列表，每条消息包含: qq, time, content, sender等字段
        """
        self.lines_data = []
        self.qq_to_name = {}  # 重新初始化为 {qq: [nickname1, nickname2, ...]} 格式
        
        for msg in messages:
            qq = str(msg.get('qq', '') or '')
            content = str(msg.get('content', '') or '')

            is_system = bool(msg.get('is_system')) or (qq in SYSTEM_QQ_NUMBERS) or (qq == 'system')
            is_recall = bool(msg.get('is_recalled'))

            element_counts = msg.get('element_counts')
            if not isinstance(element_counts, dict):
                element_counts = {}

            def _n(k: int) -> int:
                try:
                    kk = int(k)
                    v = element_counts.get(kk, None)
                    if v is None:
                        v = element_counts.get(str(kk), 0)
                    return int(v or 0)
                except Exception:
                    return 0

            # 只保留 elements 体系：图片(2)、表情(6/11)
            image_count = _n(2)
            emoji_count = _n(6) + _n(11)

            # mentions：若导入层提供 mentions 列表则直接使用
            mentions = msg.get('mentions')
            if not isinstance(mentions, list):
                mentions = []
            mentions = [str(x) for x in mentions if x]

            clean_text = content.strip()

            line_data = LineData(
                raw_text=content,
                clean_text=clean_text,
                char_count=len(clean_text),
                timepat=str(msg.get('time', '') or ''),
                qq=qq,
                sender=str(msg.get('sender', '') or ''),
                image_count=image_count,
                emoji_count=emoji_count,
                mentions=mentions,
                has_link=has_link(content),
                is_recall=is_recall,
            )

            # 附加结构化信息（LineData 是轻量容器；动态扩展字段即可）
            line_data.is_system = is_system
            line_data.message_type = str(msg.get('message_type') or line_data.get_message_type() or 'unknown')
            line_data.element_counts = element_counts
            line_data.reply_to_qq = msg.get('reply_to_qq')

            self.lines_data.append(line_data)

            # 昵称映射：仅记录“非系统消息”的 sender
            if (not is_system) and qq and line_data.sender:
                if qq not in self.qq_to_name:
                    self.qq_to_name[qq] = []
                if line_data.sender not in self.qq_to_name[qq]:
                    self.qq_to_name[qq].append(line_data.sender)
    
    def analyze(self) -> GroupStats:
        """
        执行完整的群体分析

        Returns:
            GroupStats对象
        """
        if not self.lines_data:
            return self.stats

        # 预解析所有时间戳
        parsed_times = []
        for line_data in self.lines_data:
            dt = parse_timestamp(line_data.timepat)
            parsed_times.append(dt)
        
        # 单次遍历，收集所有统计数据
        self._analyze_all_in_one_pass(parsed_times)
        
        # 热词提取（独立处理，因为需要分词）
        self._extract_hot_content()

        return self.stats
    
    def _analyze_all_in_one_pass(self, parsed_times: List) -> None:
        """
        完成所有统计分析
        
        合并了以下分析：
        - 活跃度指标 (总消息、日均、月度趋势、高峰时段)
        - 成员分层统计
        - 消息类型分析
        - 7*24热力图
        - 时段和日期统计
        """
        # === 初始化所有计数器 ===
        unique_dates = set()
        monthly_count = defaultdict(int)
        hourly_count = defaultdict(int)
        member_count = defaultdict(int)
        
        # 消息类型计数
        text_count = 0
        image_count = 0
        emoji_count = 0
        link_count = 0
        forward_count = 0

        # 结构化指标
        system_count = 0
        recalled_count = 0
        mention_msg_count = 0
        reply_msg_count = 0
        media_msg_count = 0
        media_breakdown = defaultdict(int)
        
        # 热力图
        heatmap = defaultdict(int)
        
        # 时段分析
        hourly_user_count = defaultdict(lambda: defaultdict(int))
        weekday_user_count = defaultdict(lambda: defaultdict(int))
        weekday_totals = defaultdict(int)
        
        # 表情统计
        emoji_counter = defaultdict(int)

        # 各类行为的“按成员计数”
        recalled_by_user = defaultdict(int)
        image_by_user = defaultdict(int)
        emoji_by_user = defaultdict(int)
        forward_by_user = defaultdict(int)
        file_by_user = defaultdict(int)
        
        # === 单次遍历 ===
        element_totals = defaultdict(int)
        system_by_user = defaultdict(int)
        mention_by_user = defaultdict(int)
        reply_by_user = defaultdict(int)
        media_by_user = defaultdict(int)
        wallet_by_user = defaultdict(int)
        element_by_user = defaultdict(lambda: defaultdict(int))  # qq -> {ElementType(int): count}
        
        for i, line_data in enumerate(self.lines_data):
            dt = parsed_times[i]
            qq = line_data.qq

            is_system = bool(getattr(line_data, 'is_system', False))
            msg_type = str(getattr(line_data, 'message_type', '') or line_data.get_message_type() or 'unknown')
            element_counts = getattr(line_data, 'element_counts', None)
            if not isinstance(element_counts, dict):
                element_counts = {}

            is_reply = bool(getattr(line_data, 'reply_to_qq', None)) or msg_type in ('reply', 'KMSGTYPEREPLY')
            is_forward = msg_type in ('forward', 'KMSGTYPEMULTIMSGFORWARD')

            def _n(k: int) -> int:
                try:
                    kk = int(k)
                    v = element_counts.get(kk, None)
                    if v is None:
                        v = element_counts.get(str(kk), 0)
                    return int(v or 0)
                except Exception:
                    return 0

            # ElementType 全量汇总（注意：element_counts 可能是 str-key，也可能是 int-key）
            wallet_count = _n(ElementType.WALLET)
            if wallet_count and qq and (not is_system):
                wallet_by_user[qq] += wallet_count
            for key, value in element_counts.items():
                try:
                    idx = int(key)
                    cnt = int(value or 0)
                except Exception:
                    continue
                element_totals[idx] += cnt
                if qq and (not is_system) and (qq not in SYSTEM_QQ_NUMBERS) and qq != 'system':
                    element_by_user[qq][idx] += cnt

            if is_system:
                system_count += 1
            if qq:
                if is_system:
                    system_by_user[qq] += 1
            if line_data.is_recall:
                recalled_count += 1
                if qq and (not is_system):
                    recalled_by_user[qq] += 1
            if qq and line_data.is_recall and (not is_system):
                pass
            if (not is_system) and line_data.mentions:
                mention_msg_count += 1
                if qq:
                    mention_by_user[qq] += 1
            if is_reply:
                reply_msg_count += 1
                if qq:
                    reply_by_user[qq] += 1

            # 媒体统计：仅使用 elements + 链接启发式（TXT 没有 link 元素）
            media_types = set()
            if _n(2) > 0:
                media_types.add('image')
            if (_n(6) + _n(11)) > 0:
                media_types.add('emoji')
            if _n(3) > 0:
                media_types.add('file')
            if _n(4) > 0:
                media_types.add('audio')
            if _n(5) > 0:
                media_types.add('video')
            if line_data.has_link:
                media_types.add('link')
            if is_forward or _n(16) > 0:
                media_types.add('forward')

            if media_types:
                media_msg_count += 1
                for t in media_types:
                    media_breakdown[t] += 1
                if qq:
                    media_by_user[qq] += 1
            
            # 1. 活跃度指标
            date = line_data.get_date()
            if date:
                unique_dates.add(date)
            
            if dt:
                month_key = dt.strftime('%Y-%m')
                monthly_count[month_key] += 1
                hourly_count[dt.hour] += 1
                
                # 热力图
                day = dt.weekday()
                hour = dt.hour
                heatmap[day * 24 + hour] += 1
                
                # 时段分析
                if qq:
                    hourly_user_count[hour][qq] += 1
                    weekday_user_count[day][qq] += 1
                    weekday_totals[day] += 1
            
            # 2. 成员统计：系统消息不参与成员活跃度分层
            if qq and (not is_system) and (qq not in SYSTEM_QQ_NUMBERS) and qq != 'system':
                member_count[qq] += 1
            
            # 3. 消息类型分析
            if is_system or line_data.is_recall:
                pass
            else:
                # 只保留 elements 体系：图片/表情/文件/音视频 + link 启发式
                if _n(2) > 0 or msg_type == 'image':
                    image_count += 1
                    if qq:
                        image_by_user[qq] += max(1, _n(2))
                elif (_n(6) + _n(11)) > 0 or msg_type in ('emoji', 'sticker'):
                    emoji_count += 1
                    if qq:
                        emoji_by_user[qq] += max(1, (_n(6) + _n(11)))
                elif line_data.has_link or msg_type == 'link':
                    link_count += 1
                elif (
                    is_forward
                    or msg_type in ('video', 'audio', 'file', 'redpacket', 'special', 'KMSGTYPEWALLET')
                    or _n(3) > 0
                    or _n(4) > 0
                    or _n(5) > 0
                    or _n(16) > 0
                ):
                    forward_count += 1
                    if qq and is_forward:
                        forward_by_user[qq] += 1
                    if qq and (_n(3) > 0 or msg_type == 'file'):
                        file_by_user[qq] += max(1, _n(3))
                elif line_data.clean_text.strip() or msg_type == 'text':
                    text_count += 1
            
            # 4. 表情统计
            content = line_data.raw_text
            emojis = EMOJI_PATTERN.findall(content)
            for emoji in emojis:
                if '表情' not in emoji and '图' not in emoji:
                    emoji_counter[emoji] += 1
        
        # === 计算统计结果 ===
        
        # 总消息数
        self.stats.total_messages = len(self.lines_data)

        # 结构化计数
        self.stats.system_messages = system_count
        self.stats.recalled_messages = recalled_count
        self.stats.mention_messages = mention_msg_count
        self.stats.reply_messages = reply_msg_count
        self.stats.media_messages = media_msg_count
        self.stats.media_breakdown = dict(sorted(media_breakdown.items(), key=lambda x: x[0]))
        
        # 日均消息
        active_days = len(unique_dates)
        if active_days > 0:
            self.stats.daily_average = self.stats.total_messages / active_days
        
        # 月度趋势
        self.stats.monthly_trend = dict(sorted(monthly_count.items()))
        
        # 高峰时段
        if hourly_count:
            max_hour_count = max(hourly_count.values())
            self.stats.hourly_peak = max_hour_count
            self.stats.peak_hours = sorted([
                hour for hour, count in hourly_count.items() 
                if count >= max_hour_count * 0.8
            ])
            try:
                self.stats.peak_hour = int(max(hourly_count.items(), key=lambda x: x[1])[0])
            except Exception:
                self.stats.peak_hour = None
        
        # 成员分层
        self._calculate_member_stratification(member_count)
        
        # 消息类型比例
        total_typed = text_count + image_count + emoji_count + link_count + forward_count
        if total_typed == 0:
            total_typed = 1
        self.stats.text_ratio = text_count / total_typed
        self.stats.image_ratio = image_count / total_typed
        self.stats.emoji_ratio = emoji_count / total_typed
        self.stats.link_ratio = link_count / total_typed
        self.stats.forward_ratio = forward_count / total_typed
        
        # 热力图
        self.stats.heatmap = dict(heatmap)
        
        # 表情排行
        self.stats.hot_emojis = sorted(emoji_counter.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # 时段分析
        self._calculate_time_based_stats(hourly_user_count, weekday_user_count, weekday_totals)

        # 各类行为最多的人
        def build_top_item(counter: Dict[str, int]):
            if not counter:
                return None
            top_qq, top_cnt = max(counter.items(), key=lambda x: x[1])
            names = self.qq_to_name.get(top_qq, [top_qq])
            if isinstance(names, list):
                name = names[-1] if names else top_qq
            else:
                name = names if names else top_qq
            return {'qq': top_qq, 'name': name, 'count': int(top_cnt)}

        self.stats.top_recaller = build_top_item(recalled_by_user)
        self.stats.top_image_sender = build_top_item(image_by_user)
        self.stats.top_emoji_sender = build_top_item(emoji_by_user)
        self.stats.top_forward_sender = build_top_item(forward_by_user)
        self.stats.top_file_sender = build_top_item(file_by_user)
        self.stats.top_wallet_sender = build_top_item(wallet_by_user)
        self.stats.top_system_sender = build_top_item(system_by_user)
        self.stats.top_mention_sender = build_top_item(mention_by_user)
        self.stats.top_reply_sender = build_top_item(reply_by_user)
        self.stats.top_media_sender = build_top_item(media_by_user)
        self.stats.element_totals = dict(sorted(element_totals.items()))

        # ElementType 全量字段（与 personal_analyzer 对齐）
        et = lambda x: int(x)
        self.stats.element_text_count = int(element_totals.get(et(ElementType.TEXT), 0) or 0)
        self.stats.element_pic_count = int(element_totals.get(et(ElementType.PIC), 0) or 0)
        self.stats.element_file_count = int(element_totals.get(et(ElementType.FILE), 0) or 0)
        self.stats.element_ptt_count = int(element_totals.get(et(ElementType.PTT), 0) or 0)
        self.stats.element_video_count = int(element_totals.get(et(ElementType.VIDEO), 0) or 0)
        self.stats.element_face_count = int(element_totals.get(et(ElementType.FACE), 0) or 0)
        self.stats.element_reply_count = int(element_totals.get(et(ElementType.REPLY), 0) or 0)
        self.stats.element_greytip_count = int(element_totals.get(et(ElementType.GreyTip), 0) or 0)
        self.stats.element_wallet_count = int(element_totals.get(et(ElementType.WALLET), 0) or 0)
        self.stats.element_ark_count = int(element_totals.get(et(ElementType.ARK), 0) or 0)
        self.stats.element_mface_count = int(element_totals.get(et(ElementType.MFACE), 0) or 0)
        self.stats.element_livegift_count = int(element_totals.get(et(ElementType.LIVEGIFT), 0) or 0)
        self.stats.element_structlongmsg_count = int(element_totals.get(et(ElementType.STRUCTLONGMSG), 0) or 0)
        self.stats.element_markdown_count = int(element_totals.get(et(ElementType.MARKDOWN), 0) or 0)
        self.stats.element_giphy_count = int(element_totals.get(et(ElementType.GIPHY), 0) or 0)
        self.stats.element_multiforward_count = int(element_totals.get(et(ElementType.MULTIFORWARD), 0) or 0)
        self.stats.element_inlinekeyboard_count = int(element_totals.get(et(ElementType.INLINEKEYBOARD), 0) or 0)
        self.stats.element_intextgift_count = int(element_totals.get(et(ElementType.INTEXTGIFT), 0) or 0)
        self.stats.element_calendar_count = int(element_totals.get(et(ElementType.CALENDAR), 0) or 0)
        self.stats.element_yologameresult_count = int(element_totals.get(et(ElementType.YOLOGAMERESULT), 0) or 0)
        self.stats.element_avrecord_count = int(element_totals.get(et(ElementType.AVRECORD), 0) or 0)
        self.stats.element_feed_count = int(element_totals.get(et(ElementType.FEED), 0) or 0)
        self.stats.element_tofurecord_count = int(element_totals.get(et(ElementType.TOFURECORD), 0) or 0)
        self.stats.element_acebubble_count = int(element_totals.get(et(ElementType.ACEBUBBLE), 0) or 0)
        self.stats.element_activity_count = int(element_totals.get(et(ElementType.ACTIVITY), 0) or 0)
        self.stats.element_tofu_count = int(element_totals.get(et(ElementType.TOFU), 0) or 0)
        self.stats.element_facebubble_count = int(element_totals.get(et(ElementType.FACEBUBBLE), 0) or 0)
        self.stats.element_sharelocation_count = int(element_totals.get(et(ElementType.SHARELOCATION), 0) or 0)
        self.stats.element_tasktopmsg_count = int(element_totals.get(et(ElementType.TASKTOPMSG), 0) or 0)
        self.stats.element_recommendedmsg_count = int(element_totals.get(et(ElementType.RECOMMENDEDMSG), 0) or 0)
        self.stats.element_actionbar_count = int(element_totals.get(et(ElementType.ACTIONBAR), 0) or 0)

        # 每个 ElementType “谁发得最多”（成员页展示）
        top_element_senders: Dict[str, Dict[str, Any]] = {}
        for et_id, total in element_totals.items():
            if not total:
                continue
            best_qq = None
            best_cnt = 0
            for qq2, by_et in element_by_user.items():
                cnt = int(by_et.get(int(et_id), 0) or 0)
                if cnt > best_cnt:
                    best_cnt = cnt
                    best_qq = qq2
            if best_qq and best_cnt > 0:
                names = self.qq_to_name.get(best_qq, [best_qq])
                if isinstance(names, list):
                    name = names[-1] if names else best_qq
                else:
                    name = names if names else best_qq
                top_element_senders[str(int(et_id))] = {'qq': best_qq, 'name': name, 'count': int(best_cnt)}
        self.stats.top_element_senders = top_element_senders

        self.stats.total_members = len(member_count)
    
    def _calculate_member_stratification(self, member_count: Dict[str, int]) -> None:
        """计算成员分层（从单次遍历的结果中）"""
        if not member_count:
            return
        
        # 按消息数排序
        sorted_members = sorted(member_count.items(), key=lambda x: x[1], reverse=True)
        total_members = len(sorted_members)
        
        # 分层阈值
        top_10_idx = max(1, int(total_members * 0.1))
        top_40_idx = max(top_10_idx + 1, int(total_members * 0.4))
        top_80_idx = max(top_40_idx + 1, int(total_members * 0.8))
        
        # 构建成员信息 - 处理多个昵称的格式
        def build_member_info(qq, count):
            names = self.qq_to_name.get(qq, [qq])
            # 如果是列表，取最后一个（最新的昵称），否则直接使用
            if isinstance(names, list):
                name = names[-1] if names else qq
            else:
                name = names if names else qq
            return {'qq': qq, 'name': name, 'count': count}
        
        # 分层成员
        self.stats.core_members = [build_member_info(m[0], m[1]) for m in sorted_members[:top_10_idx]]
        self.stats.active_members = [build_member_info(m[0], m[1]) for m in sorted_members[top_10_idx:top_40_idx]]
        self.stats.normal_members = [build_member_info(m[0], m[1]) for m in sorted_members[top_40_idx:top_80_idx]]
        self.stats.lurkers = [build_member_info(m[0], m[1]) for m in sorted_members[top_80_idx:]]
        
        # 成员消息计数
        self.stats.member_message_count = {
            qq: {'name': build_member_info(qq, 0)['name'], 'count': count} 
            for qq, count in member_count.items()
        }
    
    def _calculate_time_based_stats(self, hourly_user_count, weekday_user_count, weekday_totals) -> None:
        """计算时段统计（从单次遍历的结果中）"""
        weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        
        # 辅助函数：获取QQ对应的最新昵称
        def get_qq_name(qq):
            names = self.qq_to_name.get(qq, [qq])
            if isinstance(names, list):
                return names[-1] if names else qq
            else:
                return names if names else qq
        
        # 每小时最活跃用户
        hourly_top_users = {}
        for hour in range(24):
            if hourly_user_count[hour]:
                top_qq = max(hourly_user_count[hour].items(), key=lambda x: x[1])
                hourly_top_users[hour] = {
                    'qq': top_qq[0],
                    'name': get_qq_name(top_qq[0]),
                    'count': top_qq[1]
                }
        
        # 每个星期几最活跃用户
        weekday_top_users = {}
        for weekday in range(7):
            if weekday_user_count[weekday]:
                top_qq = max(weekday_user_count[weekday].items(), key=lambda x: x[1])
                weekday_top_users[weekday] = {
                    'weekday_name': weekday_names[weekday],
                    'qq': top_qq[0],
                    'name': get_qq_name(top_qq[0]),
                    'count': top_qq[1]
                }
        
        # 星期几总消息数
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
    
    def _extract_hot_content(self) -> None:
        """T025: 提取热词"""
        # 收集所有文本内容，排除图片等非文本
        all_text_lines = []
        emoji_count = defaultdict(int)
        
        for line_data in self.lines_data:
            # 热词默认排除 系统/撤回
            if bool(getattr(line_data, 'is_system', False)):
                continue
            if line_data.is_recall:
                continue

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
                # 提取所有昵称列表（包括历史昵称）
                # qq_to_name 格式: {qq: [nickname1, nickname2, ...]}
                nicknames = []
                for qq, names_list in self.qq_to_name.items():
                    if isinstance(names_list, list):
                        nicknames.extend(names_list)
                    else:
                        nicknames.append(names_list)
                
                word_counts, words_top = cut_words(all_text_lines, top_words_num=20, nicknames=nicknames)
                self.stats.hot_words = words_top
            except Exception as e:
                print(f"分词失败: {e}")
                self.stats.hot_words = []
        
        self.stats.hot_emojis = sorted(emoji_count.items(), key=lambda x: x[1], reverse=True)[:10]
