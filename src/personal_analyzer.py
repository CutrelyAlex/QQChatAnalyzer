"""个人分析模块 - 分析单个用户的聊天行为。

要求（2025-12）：
- 使用新的 chat_import.schema.Conversation/Message 数据结构
- 统计维度：uin/群昵称列表(memberNames)/QQ名(nickName)、消息量/活跃天/首末发言、月统计、星期统计、12段时段分布
- 互动：@次数、被@次数、回复次数，并输出互动次数字典
- ElementType 全量计数（分离为多个变量，并在代码中给出中文注释）
- 文本统计严格使用“干净文本”（Message.text）
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

from src.config import Config
from src.chat_import.enums import ElementType
from src.chat_import.schema import Conversation, Mention, Message, Participant

from .txt_process import HTTP_PATTERN, SYSTEM_QQ_NUMBERS, cut_words


def _use_utc_for_conversation(conv: Conversation) -> bool:
    """与 web/services/conversation_loader.py 的展示时间语义保持一致。"""

    try:
        if not (conv and str(conv.conversation_id or '').startswith('json:')):
            return False
        mode = (getattr(Config, 'JSON_TIMESTAMP_MODE', None) or 'utc_to_local').strip().lower()
        return mode == 'wysiwyg'
    except Exception:
        return False


def _dt_from_ts_ms(ts_ms: int, *, use_utc: bool) -> datetime:
    if use_utc:
        return datetime.fromtimestamp((ts_ms or 0) / 1000, tz=timezone.utc)
    return datetime.fromtimestamp((ts_ms or 0) / 1000)


def _append_unique_str(lst: List[str], value: Optional[str]) -> None:
    v = (value or '').strip()
    if not v:
        return
    if v in lst:
        return
    lst.append(v)


class PersonalStats:
    """个人统计数据类（面向 JSON 输出）。"""

    def __init__(
        self,
        *,
        participant_id: str,
        uid: Optional[str],
        uin: Optional[str],
        member_names: Iterable[str] | None,
        nick_name: Optional[str],
        display_name: Optional[str],
    ):
        # 身份
        self.participant_id = str(participant_id)
        self.uid = str(uid) if uid else ''
        self.uin = str(uin) if uin else ''
        self.display_name = (display_name or self.uin or self.uid or self.participant_id)

        self.member_names = list(member_names or [])
        self.nick_name = (nick_name or '').strip()

        # 基本统计
        self.total_messages = 0
        self.active_days_set: set[str] = set()
        self.first_message_date: Optional[str] = None
        self.last_message_date: Optional[str] = None

        # 月度与星期统计
        self.monthly_messages: Dict[str, int] = defaultdict(int)  # {YYYY-MM: count}
        self.weekday_messages: List[int] = [0] * 7  # 0=周一 ... 6=周日

        # 时段分布（新增：12 段，每段 2 小时）
        self.time_distribution_12: List[int] = [0] * 12

        # 互动指标
        self.at_count = 0  # @他人次数（按 mentions 条目计数）
        self.being_at_count = 0  # 被@次数（按 mentions 条目计数）
        self.reply_count = 0  # 回复次数（ElementType=7 或 reply_to）
        self.interaction_counts = {
            'at': 0,
            'mentioned': 0,
            'reply': 0,
        }
        self.top_interactions: List[tuple[str, int]] = []

        # 结构化事件计数（非 ElementType 统计；来自 Message.is_system/is_recalled）
        self.link_count = 0
        self.recall_count = 0
        self.system_count = 0

        # ------------------------------
        # 各 ElementType 元素数量（来自 Message.element_counts）
        # 注意：文本分析/字数统计使用“干净文本”Message.text，而不是 element_counts[TEXT]
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

        # 字数统计（干净文本）
        self.total_clean_chars = 0
        self.clean_text_message_count = 0  # 干净文本非空的消息条数
        self.avg_clean_chars_per_message = 0.0

        # 连续发言最大天数
        self.max_streak_days = 0

        # 关键词/热词
        self.top_words: List[tuple[str, int]] = []

    def to_dict(self):
        """转换为字典（供 API/UI）。"""

        return {
            # 身份
            'participant_id': self.participant_id,
            'uid': self.uid,
            'uin': self.uin,
            'display_name': self.display_name,
            'memberNames': list(self.member_names),
            'nickName': self.nick_name,

            # 统计
            'total_messages': self.total_messages,
            'active_days': len(self.active_days_set),
            'first_message_date': self.first_message_date,
            'last_message_date': self.last_message_date,
            'monthly_messages': dict(self.monthly_messages),
            'weekday_messages': list(self.weekday_messages),
            'time_distribution_12': list(self.time_distribution_12),

            # 互动
            'at_count': self.at_count,
            'being_at_count': self.being_at_count,
            'reply_count': self.reply_count,
            'interaction_counts': dict(self.interaction_counts),
            'top_interactions': self.top_interactions[:10],

            'link_count': self.link_count,
            'recall_count': self.recall_count,
            'system_count': self.system_count,

            # ElementType 全量计数
            'element_text_count': self.element_text_count,
            'element_pic_count': self.element_pic_count,
            'element_file_count': self.element_file_count,
            'element_ptt_count': self.element_ptt_count,
            'element_video_count': self.element_video_count,
            'element_face_count': self.element_face_count,
            'element_reply_count': self.element_reply_count,
            'element_greytip_count': self.element_greytip_count,
            'element_wallet_count': self.element_wallet_count,
            'element_ark_count': self.element_ark_count,
            'element_mface_count': self.element_mface_count,
            'element_livegift_count': self.element_livegift_count,
            'element_structlongmsg_count': self.element_structlongmsg_count,
            'element_markdown_count': self.element_markdown_count,
            'element_giphy_count': self.element_giphy_count,
            'element_multiforward_count': self.element_multiforward_count,
            'element_inlinekeyboard_count': self.element_inlinekeyboard_count,
            'element_intextgift_count': self.element_intextgift_count,
            'element_calendar_count': self.element_calendar_count,
            'element_yologameresult_count': self.element_yologameresult_count,
            'element_avrecord_count': self.element_avrecord_count,
            'element_feed_count': self.element_feed_count,
            'element_tofurecord_count': self.element_tofurecord_count,
            'element_acebubble_count': self.element_acebubble_count,
            'element_activity_count': self.element_activity_count,
            'element_tofu_count': self.element_tofu_count,
            'element_facebubble_count': self.element_facebubble_count,
            'element_sharelocation_count': self.element_sharelocation_count,
            'element_tasktopmsg_count': self.element_tasktopmsg_count,
            'element_recommendedmsg_count': self.element_recommendedmsg_count,
            'element_actionbar_count': self.element_actionbar_count,

            # 字数
            'total_clean_chars': self.total_clean_chars,
            'clean_text_message_count': self.clean_text_message_count,
            'avg_clean_chars_per_message': round(float(self.avg_clean_chars_per_message or 0.0), 2),

            # 连续天数
            'max_streak_days': self.max_streak_days,

            # 热词
            'top_words': [{'word': w, 'count': c} for w, c in (self.top_words or [])[:20]],
        }


class PersonalAnalyzer:
    """个人分析器"""

    def get_user_stats(self, conv: Conversation, user_key: str) -> Optional[PersonalStats]:
        """从 Conversation 获取单个用户统计。

        user_key 可以是：participant_id / uid / uin / 显示名。
        """

        p = self._resolve_participant(conv, user_key)
        if p is None:
            return None
        return self._analyze_participant(conv, p)

    def _resolve_participant(self, conv: Conversation, user_key: str) -> Optional[Participant]:
        key = (user_key or '').strip()
        if not key:
            return None

        participants = list(getattr(conv, 'participants', None) or [])

        # 1) participant_id 精确匹配
        for p in participants:
            if str(p.participant_id) == key:
                return p

        # 2) uin / uid 精确匹配
        for p in participants:
            if getattr(p, 'uin', None) and str(p.uin) == key:
                return p
            if getattr(p, 'uid', None) and str(p.uid) == key:
                return p

        # 3) 显示名匹配（尽量避免误匹配：仅在唯一时返回）
        matches = [p for p in participants if (getattr(p, 'display_name', None) or '') == key]
        if len(matches) == 1:
            return matches[0]

        return None

    def _analyze_participant(self, conv: Conversation, p: Participant) -> PersonalStats:
        use_utc = _use_utc_for_conversation(conv)

        # nickname: 更偏向群昵称（memberName）
        member_names = list(getattr(p, 'member_names', None) or [])
        nick_name = getattr(p, 'nick_name', None)

        # 若 member_names 为空，尝试从 display_name_history/display_name 补齐
        if not member_names:
            for v in (getattr(p, 'display_name_history', None) or ()):  # 兼容旧数据
                _append_unique_str(member_names, v)
        _append_unique_str(member_names, getattr(p, 'display_name', None))

        stats = PersonalStats(
            participant_id=str(p.participant_id),
            uid=getattr(p, 'uid', None),
            uin=getattr(p, 'uin', None),
            member_names=member_names,
            nick_name=nick_name,
            display_name=(member_names[-1] if member_names else getattr(p, 'display_name', None)),
        )

        pid_to_participant: Dict[str, Participant] = {str(x.participant_id): x for x in (conv.participants or [])}
        uin_to_pid: Dict[str, str] = {
            str(x.uin): str(x.participant_id)
            for x in (conv.participants or [])
            if getattr(x, 'uin', None)
        }

        # 为热词过滤准备：所有昵称候选（群昵称/显示名）
        all_nicknames: List[str] = []
        for it in (conv.participants or []):
            _append_unique_str(all_nicknames, getattr(it, 'display_name', None))
            for h in (getattr(it, 'display_name_history', None) or ()):
                _append_unique_str(all_nicknames, h)
            for mn in (getattr(it, 'member_names', None) or ()):
                _append_unique_str(all_nicknames, mn)

        # 互动对象计数：@了谁
        outgoing = Counter()

        # 热词文本
        clean_lines_for_hotwords: List[str] = []

        # 先遍历本人发言
        for m in (conv.messages or []):
            if not m.sender_participant_id:
                continue
            if str(m.sender_participant_id) != str(p.participant_id):
                continue

            # 过滤系统账号（防御性）
            if stats.uin and stats.uin in SYSTEM_QQ_NUMBERS:
                continue

            stats.total_messages += 1

            dt = _dt_from_ts_ms(int(m.timestamp_ms or 0), use_utc=use_utc)
            date_str = dt.strftime('%Y-%m-%d')
            month_key = dt.strftime('%Y-%m')
            stats.active_days_set.add(date_str)

            if (stats.first_message_date is None) or (date_str < stats.first_message_date):
                stats.first_message_date = date_str
            if (stats.last_message_date is None) or (date_str > stats.last_message_date):
                stats.last_message_date = date_str

            stats.monthly_messages[month_key] += 1
            stats.weekday_messages[dt.weekday()] += 1

            hour = dt.hour

            # 时段 12 段（每 2 小时）
            bucket = max(0, min(11, hour // 2))
            stats.time_distribution_12[bucket] += 1

            # 系统/撤回
            if bool(getattr(m, 'is_system', False)):
                stats.system_count += 1
            if bool(getattr(m, 'is_recalled', False)):
                stats.recall_count += 1

            # element_counts 统计
            ec = getattr(m, 'element_counts', None) or {}

            def _n(et: ElementType) -> int:
                try:
                    return int(ec.get(int(et), 0) or 0)
                except Exception:
                    return 0

            stats.element_text_count += _n(ElementType.TEXT)
            stats.element_pic_count += _n(ElementType.PIC)
            stats.element_file_count += _n(ElementType.FILE)
            stats.element_ptt_count += _n(ElementType.PTT)
            stats.element_video_count += _n(ElementType.VIDEO)
            stats.element_face_count += _n(ElementType.FACE)
            stats.element_reply_count += _n(ElementType.REPLY)
            stats.element_greytip_count += _n(ElementType.GreyTip)
            stats.element_wallet_count += _n(ElementType.WALLET)
            stats.element_ark_count += _n(ElementType.ARK)
            stats.element_mface_count += _n(ElementType.MFACE)
            stats.element_livegift_count += _n(ElementType.LIVEGIFT)
            stats.element_structlongmsg_count += _n(ElementType.STRUCTLONGMSG)
            stats.element_markdown_count += _n(ElementType.MARKDOWN)
            stats.element_giphy_count += _n(ElementType.GIPHY)
            stats.element_multiforward_count += _n(ElementType.MULTIFORWARD)
            stats.element_inlinekeyboard_count += _n(ElementType.INLINEKEYBOARD)
            stats.element_intextgift_count += _n(ElementType.INTEXTGIFT)
            stats.element_calendar_count += _n(ElementType.CALENDAR)
            stats.element_yologameresult_count += _n(ElementType.YOLOGAMERESULT)
            stats.element_avrecord_count += _n(ElementType.AVRECORD)
            stats.element_feed_count += _n(ElementType.FEED)
            stats.element_tofurecord_count += _n(ElementType.TOFURECORD)
            stats.element_acebubble_count += _n(ElementType.ACEBUBBLE)
            stats.element_activity_count += _n(ElementType.ACTIVITY)
            stats.element_tofu_count += _n(ElementType.TOFU)
            stats.element_facebubble_count += _n(ElementType.FACEBUBBLE)
            stats.element_sharelocation_count += _n(ElementType.SHARELOCATION)
            stats.element_tasktopmsg_count += _n(ElementType.TASKTOPMSG)
            stats.element_recommendedmsg_count += _n(ElementType.RECOMMENDEDMSG)
            stats.element_actionbar_count += _n(ElementType.ACTIONBAR)

            # 回复次数：ElementType.REPLY 或 reply_to
            if _n(ElementType.REPLY) > 0 or getattr(m, 'reply_to', None) is not None:
                stats.reply_count += 1

            # @次数：按 mentions 条目计数
            mentions = list(getattr(m, 'mentions', None) or [])
            if mentions:
                stats.at_count += len(mentions)
                for it in mentions:
                    label = self._format_mention_target(it, pid_to_participant, uin_to_pid)
                    if label:
                        outgoing[label] += 1

            # link：在干净文本里检测（按出现次数）
            text_clean = str(getattr(m, 'text', '') or '')
            stats.link_count += len(HTTP_PATTERN.findall(text_clean))

            # 字数：干净文本
            if text_clean.strip():
                stats.total_clean_chars += len(text_clean)
                stats.clean_text_message_count += 1
                # 热词文本（排除系统/撤回）
                if not getattr(m, 'is_system', False) and not getattr(m, 'is_recalled', False):
                    if len(text_clean.strip()) > 1:
                        clean_lines_for_hotwords.append(text_clean.strip())

        # 被@次数：遍历他人消息的 mentions
        being = 0
        for m in (conv.messages or []):
            if not m.sender_participant_id:
                continue
            if str(m.sender_participant_id) == str(p.participant_id):
                continue
            for it in (getattr(m, 'mentions', None) or []):
                if self._mention_hits_user(it, p):
                    being += 1
        stats.being_at_count = being

        # 互动字典
        stats.interaction_counts['at'] = int(stats.at_count)
        stats.interaction_counts['mentioned'] = int(stats.being_at_count)
        stats.interaction_counts['reply'] = int(stats.reply_count)

        # top_interactions
        stats.top_interactions = outgoing.most_common(10)

        # 平均单条（按“干净文本数量”）
        if stats.clean_text_message_count > 0:
            stats.avg_clean_chars_per_message = float(stats.total_clean_chars) / float(stats.clean_text_message_count)
        else:
            stats.avg_clean_chars_per_message = 0.0

        # 连续发言最大天数
        stats.max_streak_days = self._compute_max_streak(stats.active_days_set)

        # 个人热词
        if clean_lines_for_hotwords:
            try:
                _, words_top = cut_words(clean_lines_for_hotwords, top_words_num=50, nicknames=all_nicknames)
                stats.top_words = words_top
            except Exception:
                stats.top_words = []

        return stats

    def _mention_hits_user(self, mention: Mention, user: Participant) -> bool:
        """判断一个 mention 是否命中目标用户。"""

        try:
            # 优先uid / participant_id（JSON 场景 participant_id=uid）
            tuid = getattr(mention, 'target_uid', None)
            if tuid and getattr(user, 'uid', None) and str(tuid) == str(user.uid):
                return True

            tpid = getattr(mention, 'target_participant_id', None)
            if tpid and str(tpid) == str(user.participant_id):
                return True

            tuin = getattr(mention, 'target_uin', None)
            if tuin and getattr(user, 'uin', None) and str(tuin) == str(user.uin):
                return True
        except Exception:
            return False

        return False

    def _format_mention_target(
        self,
        mention: Mention,
        pid_to_participant: Dict[str, Participant],
        uin_to_pid: Dict[str, str],
    ) -> str:
        """把 mention 目标格式化为可读标签，用于 top_interactions。"""

        try:
            pid = getattr(mention, 'target_participant_id', None)
            uid = getattr(mention, 'target_uid', None)
            uin = getattr(mention, 'target_uin', None)
            name = getattr(mention, 'target_name', None)

            if pid and str(pid) in pid_to_participant:
                return pid_to_participant[str(pid)].display_name
            if uid and str(uid) in pid_to_participant:
                return pid_to_participant[str(uid)].display_name
            if uin and str(uin) in uin_to_pid and uin_to_pid[str(uin)] in pid_to_participant:
                return pid_to_participant[uin_to_pid[str(uin)]].display_name
            if name:
                return str(name)
        except Exception:
            return ''

        return ''

    def _compute_max_streak(self, dates: set[str]) -> int:
        if not dates:
            return 0

        sorted_dates = sorted(dates)
        max_streak = 1
        cur = 1
        for i in range(1, len(sorted_dates)):
            try:
                d1 = datetime.strptime(sorted_dates[i - 1], '%Y-%m-%d')
                d2 = datetime.strptime(sorted_dates[i], '%Y-%m-%d')
            except Exception:
                continue

            if (d2 - d1).days == 1:
                cur += 1
                if cur > max_streak:
                    max_streak = cur
            else:
                cur = 1
        return max_streak
