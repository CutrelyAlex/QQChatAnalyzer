"""
AI总结模块 - 使用OpenAI生成创意风格的聊天总结
"""

import os
import json
import logging
import math
from typing import Dict, List, Any, Optional
from collections import defaultdict

from .prompts import get_system_prompt

logger = logging.getLogger(__name__)

# OpenAI 客户端
_openai_client = None


def get_openai_client():
    """获取或创建OpenAI客户端"""
    global _openai_client
    
    if _openai_client is None:
        try:
            from openai import OpenAI
            
            api_key = os.environ.get('OPENAI_API_KEY', '')
            base_url = os.environ.get('OPENAI_API_BASE', '')
            
            if not api_key:
                return None
            
            kwargs = {'api_key': api_key}
            if base_url:
                kwargs['base_url'] = base_url
            
            _openai_client = OpenAI(**kwargs)
        except ImportError:
            logger.warning("OpenAI library not installed. Run: pip install openai")
            return None
        except Exception as e:
            logger.error(f"Failed to create OpenAI client: {e}")
            return None
    
    return _openai_client


class AISummarizer:
    """
    AI总结器 - 使用OpenAI生成创意风格的聊天总结
    支持完整聊天记录的智能稀疏切分
    """
    
    # Token估算系数
    CHARS_PER_TOKEN_CN = 1.5  # 中文字符约1.5字符/token
    CHARS_PER_TOKEN_EN = 4.0  # 英文字符约4字符/token
    MESSAGE_OVERHEAD = 4      # 每条消息的额外token开销
    
    # 上下文Token预算分配（基于模型最大上下文）
    DEFAULT_CONTEXT_BUDGET = 60000  # 默认聊天样本Token预算
    PROMPT_RESERVE = 5000           # 为系统提示词和统计数据保留的Token
    
    def __init__(self, model: str = None, max_tokens: int = 2000, 
                 api_key: str = None, base_url: str = None,
                 context_budget: int = None, timeout: int = None,
                 temperature: Optional[float] = None, top_p: Optional[float] = None):
        """
        初始化AI总结器
        
        Args:
            model: 使用的模型名称
            max_tokens: 生成的最大token数（输出）
            api_key: OpenAI API密钥（可选，使用环境变量如未提供）
            base_url: OpenAI API基础URL（可选，使用环境变量如未提供）
            context_budget: 聊天记录的Token预算（输入），默认60000
            timeout: API请求超时时间（秒），从请求发送到完全接收响应，默认30秒
            temperature: 生成温度参数（0-2），默认 0.8
            top_p: nucleus sampling 参数（0-1），默认 0.9
        """
        self.model = model or os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')
        self.max_tokens = max_tokens
        self.context_budget = context_budget or self.DEFAULT_CONTEXT_BUDGET
        self.timeout = timeout or int(os.environ.get('OPENAI_REQUEST_TIMEOUT', 30))

        self.temperature = self._clamp_float(
            temperature if temperature is not None else float(os.environ.get('OPENAI_TEMPERATURE', 0.8)),
            min_value=0.0,
            max_value=2.0,
            default=0.8,
        )
        self.top_p = self._clamp_float(
            top_p if top_p is not None else float(os.environ.get('OPENAI_TOP_P', 0.9)),
            min_value=0.0,
            max_value=1.0,
            default=0.9,
        )
        
        # 如果提供了自定义配置，创建新客户端；否则使用全局客户端
        if api_key or base_url:
            self.client = self._create_custom_client(api_key, base_url)
        else:
            self.client = get_openai_client()
    
    def _create_custom_client(self, api_key: str = None, base_url: str = None):
        """创建自定义OpenAI客户端"""
        try:
            from openai import OpenAI
            
            # 使用提供的或环境变量中的值
            final_api_key = api_key or os.environ.get('OPENAI_API_KEY', '')
            final_base_url = base_url or os.environ.get('OPENAI_API_BASE', '')
            
            if not final_api_key:
                return None
            
            # 设置超时参数：从请求发送到完全接收响应的总耗时
            # 处理大量聊天记录时可能需要更长时间
            kwargs = {
                'api_key': final_api_key,
                'timeout': self.timeout  # 单位：秒
            }
            if final_base_url:
                kwargs['base_url'] = final_base_url
            
            return OpenAI(**kwargs)
        except ImportError:
            logger.warning("OpenAI library not installed. Run: pip install openai")
            return None
        except Exception as e:
            logger.error(f"Failed to create OpenAI client: {e}")
            return None
    
    def is_available(self) -> bool:
        """检查AI服务是否可用"""
        return self.client is not None

    @staticmethod
    def _clamp_float(value: Any, min_value: float, max_value: float, default: float) -> float:
        """尽量将 value 转为 float 并限制到区间内；失败则返回 default。"""
        try:
            v = float(value)
        except Exception:
            return float(default)
        if v < min_value:
            return float(min_value)
        if v > max_value:
            return float(max_value)
        return float(v)
    
    def _estimate_message_tokens(self, content: str) -> int:
        """
        估算单条消息的token数
        
        使用混合策略：
        - 中文字符按 1.5 字符/token
        - 英文/数字按 4 字符/token
        - 加上消息格式开销
        """
        if not content:
            return self.MESSAGE_OVERHEAD
        
        cn_chars = 0
        en_chars = 0
        
        for char in str(content):
            if '\u4e00' <= char <= '\u9fff':  # 中文
                cn_chars += 1
            else:
                en_chars += 1
        
        tokens = (cn_chars / self.CHARS_PER_TOKEN_CN) + \
                 (en_chars / self.CHARS_PER_TOKEN_EN) + \
                 self.MESSAGE_OVERHEAD
        
        return int(math.ceil(tokens))
    
    def _sparse_sample_messages(self, messages: List[Dict[str, Any]], 
                                 target_qq: str = None) -> str:
        """
        智能稀疏采样聊天记录
        
        策略：
        1. 按日期分组消息
        2. 计算总Token数
        3. 如果超过预算，按比例均匀采样日期
        4. 在每个采样日期内，均匀采样消息
        
        Args:
            messages: 完整的消息列表 [{time, sender, qq, content}, ...]
            target_qq: 可选，如果指定则只采样该QQ的消息（用于个人分析）
        
        Returns:
            格式化后的聊天记录字符串
        """
        if not messages:
            return ""
        
        # 可用于聊天记录的Token预算
        available_budget = self.context_budget - self.PROMPT_RESERVE

        # 预算不足时直接返回空样本
        if available_budget <= 0:
            logger.warning(
                f"Context budget too small (context_budget={self.context_budget}, reserve={self.PROMPT_RESERVE}); returning empty chat sample"
            )
            return ""
        
        # 如果指定了target_qq，先过滤消息
        if target_qq:
            messages = [m for m in messages if m.get('qq') == target_qq]
        
        if not messages:
            return ""
        
        # 按日期分组
        messages_by_date = defaultdict(list)
        for msg in messages:
            time_str = msg.get('time', '')
            try:
                date_str = time_str[:10] if len(time_str) >= 10 else 'unknown'
            except:
                date_str = 'unknown'
            messages_by_date[date_str].append(msg)
        
        # 估算总Token数
        total_tokens = 0
        for date_messages in messages_by_date.values():
            for msg in date_messages:
                content = msg.get('content', '')
                sender = msg.get('sender', '')
                time_str = msg.get('time', '')
                # 估算格式化后的Token数: [time] sender: content
                formatted = f"[{time_str}] {sender}: {content}"
                total_tokens += self._estimate_message_tokens(formatted)
        
        logger.info(f"Total estimated tokens: {total_tokens}, budget: {available_budget}")
        
        # 如果在预算内，返回全部消息
        if total_tokens <= available_budget:
            return self._format_messages(messages)
        
        # 需要稀疏采样
        retention_ratio = available_budget / total_tokens if total_tokens > 0 else 0
        logger.info(f"Need to prune, retention ratio: {retention_ratio:.2%}")
        
        # 获取所有日期并排序
        sorted_dates = sorted(messages_by_date.keys())
        total_days = len(sorted_dates)
        
        # 计算保留的天数
        keep_days = max(1, int(total_days * retention_ratio))
        
        # 均匀采样日期
        if keep_days >= total_days:
            selected_dates = sorted_dates
        else:
            step = total_days / keep_days
            selected_indices = [int(i * step) for i in range(keep_days)]
            selected_dates = [sorted_dates[i] for i in selected_indices if i < total_days]
        
        # 收集采样的消息，并在每个日期内进一步采样
        sampled_messages = []
        per_day_budget = available_budget // len(selected_dates) if selected_dates else available_budget
        
        for date in selected_dates:
            day_messages = messages_by_date[date]
            day_tokens = sum(
                self._estimate_message_tokens(f"[{m.get('time', '')}] {m.get('sender', '')}: {m.get('content', '')}")
                for m in day_messages
            )
            
            if day_tokens <= per_day_budget:
                # 这一天的消息在预算内，全部保留
                sampled_messages.extend(day_messages)
            else:
                # 需要在天内进一步采样
                day_retention = per_day_budget / day_tokens
                keep_count = max(1, int(len(day_messages) * day_retention))
                step = len(day_messages) / keep_count
                indices = [int(i * step) for i in range(keep_count)]
                for idx in indices:
                    if idx < len(day_messages):
                        sampled_messages.append(day_messages[idx])
        
        logger.info(f"Sampled {len(sampled_messages)} messages from {len(messages)} total")

        # 兜底：如果采样后仍然超过预算，再做一次全局均匀采样（保证至少留 1 条）
        sampled_tokens = sum(
            self._estimate_message_tokens(
                f"[{m.get('time', '')}] {m.get('sender', '')}: {m.get('content', '')}"
            )
            for m in sampled_messages
        )

        if sampled_messages and sampled_tokens > available_budget:
            keep_ratio = available_budget / sampled_tokens if sampled_tokens > 0 else 0
            keep_count = max(1, int(len(sampled_messages) * keep_ratio))
            step = len(sampled_messages) / keep_count if keep_count > 0 else len(sampled_messages)
            indices = [int(i * step) for i in range(keep_count)]
            sampled_messages = [sampled_messages[i] for i in indices if i < len(sampled_messages)]
            logger.info(
                f"Post-prune downsample applied: kept {len(sampled_messages)} messages to better fit budget"
            )
        
        return self._format_messages(sampled_messages)
    
    def _format_messages(self, messages: List[Dict[str, Any]]) -> str:
        """
        将消息列表格式化为字符串
        
        Args:
            messages: 消息列表
        
        Returns:
            格式化的字符串
        """
        lines = []
        for msg in messages:
            time_str = msg.get('time', '')
            sender = msg.get('sender', '')
            content = msg.get('content', '')
            if content:  # 只包含有内容的消息
                lines.append(f"[{time_str}] {sender}: {content}")
        return '\n'.join(lines)
    
    def generate_personal_summary(self, stats: Dict[str, Any], 
                                   chat_sample: str = "",
                                   messages: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        T051: 生成个人总结 - 创意风格的年度报告
        
        Args:
            stats: PersonalStats.to_dict() 的结果
            chat_sample: 可选的聊天记录样本（兼容旧接口）
            messages: 完整的消息列表（推荐，会自动进行智能稀疏采样）
        
        Returns:
            {'success': bool, 'summary': str, 'error': str}
        """
        if not self.is_available():
            return {
                'success': False,
                'summary': '',
                'error': 'AI服务未配置，请设置 OPENAI_API_KEY 环境变量'
            }
        
        # 如果提供了完整消息列表，使用智能稀疏采样
        if messages:
            target_qq = stats.get('qq', '')
            chat_sample = self._sparse_sample_messages(messages, target_qq)
        
        prompt = self._build_personal_prompt(stats, chat_sample)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt('personal')},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature, 
                top_p=self.top_p
            )
            
            summary = response.choices[0].message.content
            
            return {
                'success': True,
                'summary': summary,
                'tokens_used': response.usage.total_tokens if response.usage else 0,
                'model': self.model,
                'temperature': self.temperature,
                'top_p': self.top_p
            }
        except Exception as e:
            logger.error(f"Personal summary generation failed: {e}")
            return {
                'success': False,
                'summary': '',
                'error': str(e)
            }
    
    def generate_group_summary(self, group_stats: Dict[str, Any],
                                chat_sample: str = "",
                                messages: List[Dict[str, Any]] = None,
                                network_stats: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        T057: 生成群体和社交网络融合总结
        
        合并群体分析和网络分析，生成一份综合的社交分析报告
        
        Args:
            group_stats: GroupStats.to_dict() 的结果
            chat_sample: 可选的聊天记录样本（兼容旧接口）
            messages: 完整的消息列表（推荐，会自动进行智能稀疏采样）
            network_stats: NetworkStats.to_dict() 的结果（可选）
        
        Returns:
            {'success': bool, 'summary': str, 'error': str}
        """
        if not self.is_available():
            return {
                'success': False,
                'summary': '',
                'error': 'AI服务未配置，请设置 OPENAI_API_KEY 环境变量'
            }
        
        # 如果提供了完整消息列表，使用智能稀疏采样
        if messages:
            chat_sample = self._sparse_sample_messages(messages)
        
        prompt = self._build_group_and_network_prompt(group_stats, network_stats, chat_sample)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt('group_and_network')},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                top_p=self.top_p
            )
            
            summary = response.choices[0].message.content
            
            return {
                'success': True,
                'summary': summary,
                'tokens_used': response.usage.total_tokens if response.usage else 0,
                'model': self.model,
                'temperature': self.temperature,
                'top_p': self.top_p
            }
        except Exception as e:
            logger.error(f"Group and network summary generation failed: {e}")
            return {
                'success': False,
                'summary': '',
                'error': str(e)
            }


    def build_prompts(
        self,
        *,
        summary_type: str,
        stats: Optional[Dict[str, Any]] = None,
        group_stats: Optional[Dict[str, Any]] = None,
        network_stats: Optional[Dict[str, Any]] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
        qq: Optional[str] = None,
        chat_sample: str = "",
    ) -> Dict[str, Any]:
        """统一构建 system_prompt + user_prompt。

        Args:
            summary_type: personal/group/network/group_and_network
            stats/group_stats/network_stats: 对应分析结果字典
            messages: 完整消息列表（用于自动稀疏采样）
            qq: personal 模式下的目标成员 id/qq
            chat_sample: 外部已生成的聊天样本

        Returns:
            {
              'normalized_type': 'personal'|'group_and_network',
              'system_prompt': str,
              'user_prompt': str,
              'chat_sample': str,
            }
        """
        t = (summary_type or '').strip().lower()
        normalized_type = 'personal' if t == 'personal' else 'group_and_network'

        final_chat_sample = chat_sample or ''
        if messages and not final_chat_sample:
            if normalized_type == 'personal':
                final_chat_sample = self._sparse_sample_messages(messages, target_qq=qq or '')
            else:
                final_chat_sample = self._sparse_sample_messages(messages)

        if normalized_type == 'personal':
            s = stats or {}
            user_prompt = self._build_personal_prompt(s, final_chat_sample)
            system_prompt = self._get_system_prompt('personal')
        else:
            gs = group_stats or {}
            ns = network_stats or None
            user_prompt = self._build_group_and_network_prompt(gs, ns, final_chat_sample)
            system_prompt = self._get_system_prompt('group_and_network')

        return {
            'normalized_type': normalized_type,
            'system_prompt': system_prompt,
            'user_prompt': user_prompt,
            'chat_sample': final_chat_sample,
        }
    

    def _get_system_prompt(self, summary_type: str) -> str:
        """获取系统提示词"""
        return get_system_prompt(summary_type)
    
    def _build_personal_prompt(self, stats: Dict[str, Any], 
                                chat_sample: str = "") -> str:
        """构建个人总结的用户提示词"""
        
        # 提取关键数据
        display_name = stats.get('display_name', '神秘用户')
        uin = stats.get('uin', 'unknown')
        uid = stats.get('uid', '')
        member_names = stats.get('memberNames', [])
        nick_name = stats.get('nickName', '')

        total_messages = stats.get('total_messages', 0)
        active_days = stats.get('active_days', 0)
        time_dist_12 = stats.get('time_distribution_12', [])

        at_count = stats.get('at_count', 0)
        being_at_count = stats.get('being_at_count', 0)
        reply_count = stats.get('reply_count', 0)

        avg_clean = stats.get('avg_clean_chars_per_message', 0)
        total_clean = stats.get('total_clean_chars', 0)

        image_count = stats.get('element_pic_count', 0)
        emoji_count = (stats.get('element_face_count', 0) or 0) + (stats.get('element_mface_count', 0) or 0)
        forward_count = stats.get('element_multiforward_count', 0)
        file_count = stats.get('element_file_count', 0)

        top_words = stats.get('top_words', [])
        max_streak = stats.get('max_streak_days', 0)
        monthly = stats.get('monthly_messages', {})
        
        # 找出最活跃的时段（12段，每段2小时）
        peak_time = '未知'
        try:
            arr = list(time_dist_12) if isinstance(time_dist_12, list) else []
            if arr:
                max_idx = max(range(min(12, len(arr))), key=lambda i: (arr[i] or 0))
                peak_time = f"{max_idx*2:02d}:00-{(max_idx+1)*2:02d}:00"
        except Exception:
            peak_time = '未知'
        
        # 找出最活跃的月份
        peak_month = max(monthly.items(), key=lambda x: x[1])[0] if monthly else '未知'
        
        # 热词字符串
        hot_words_str = ', '.join([w['word'] for w in top_words[:10]]) if top_words else '无'
        
        prompt = f"""
请为以下用户生成一份有趣的个人聊天报告：

## 用户数据
- **成员**: {display_name}
- **uin**: {uin}
- **uid**: {uid or '-'}
- **memberNames**: {', '.join(member_names) if member_names else '-'}
- **nickName**: {nick_name or '-'}
- **总消息数**: {total_messages} 条
- **活跃天数**: {active_days} 天
- **最长连续活跃**: {max_streak} 天
- **最活跃时段**: {peak_time}
- **最活跃月份**: {peak_month}
## 互动数据
- **@别人次数**: {at_count} 次
- **被@次数**: {being_at_count} 次
- **回复次数**: {reply_count} 次
- **平均字数(干净文本)**: {avg_clean:.1f} 字
- **总字数(干净文本)**: {total_clean} 字
- **图片元素**: {image_count} 个
- **表情元素**: {emoji_count} 个
- **转发元素**: {forward_count} 个
- **文件元素**: {file_count} 个
## 热词TOP10
{hot_words_str}
## ⏰ 时段分布
{json.dumps(time_dist_12, ensure_ascii=False, indent=2)}
## 📅 月度消息量
{json.dumps(monthly, ensure_ascii=False, indent=2)}
"""
        if chat_sample:
            # 显示采样的聊天记录（已经过稀疏采样，无需再截断）
            prompt += f"""
## 💬 聊天记录（用于分析说话风格）
{chat_sample}
"""
        prompt += """
请根据以上数据，生成一份有趣创意的个人年度总结！
"""
        return prompt
    
    def _build_group_and_network_prompt(self, group_stats: Dict[str, Any],
                                        network_stats: Dict[str, Any] = None,
                                        chat_sample: str = "") -> str:
        """
        构建群体和网络融合总结的用户提示词
        
        Args:
            group_stats: 群体统计数据
            network_stats: 网络统计数据（可选）
            chat_sample: 聊天样本
        
        Returns:
            融合的 prompt 字符串
        """
        # 群体统计数据
        total_messages = group_stats.get('total_messages', 0)
        daily_avg = group_stats.get('daily_average', 0)
        peak_hours = group_stats.get('peak_hours', [])
        core_members = group_stats.get('core_members', [])
        active_members = group_stats.get('active_members', [])
        normal_members = group_stats.get('normal_members', [])
        lurkers = group_stats.get('lurkers', [])
        hot_words = group_stats.get('hot_words', [])
        monthly_trend = group_stats.get('monthly_trend', {})
        text_ratio = group_stats.get('text_ratio', 0)
        image_ratio = group_stats.get('image_ratio', 0)
        emoji_ratio = group_stats.get('emoji_ratio', 0)
        # 结构化扩展指标
        system_messages = group_stats.get('system_messages', 0)
        recalled_messages = group_stats.get('recalled_messages', 0)
        mention_messages = group_stats.get('mention_messages', 0)
        reply_messages = group_stats.get('reply_messages', 0)
        media_messages = group_stats.get('media_messages', 0)
        media_breakdown = group_stats.get('media_breakdown', {})
        if not isinstance(media_breakdown, dict):
            media_breakdown = {}
        # 新增的时间统计数据
        hourly_top_users = group_stats.get('hourly_top_users', {})
        weekday_top_users = group_stats.get('weekday_top_users', {})
        weekday_totals = group_stats.get('weekday_totals', {})
        # 核心成员信息
        core_info = []
        for m in core_members[:5]:
            if isinstance(m, dict):
                core_info.append(f"{m.get('name', m.get('qq', '?'))} ({m.get('count', 0)}条)")
            else:
                core_info.append(str(m))
        
        # 热词
        hot_words_str = ', '.join([w['word'] for w in hot_words[:15]]) if hot_words else '无'
        
        # 峰值时间
        peak_str = ', '.join([f"{h}:00" for h in peak_hours[:3]]) if peak_hours else '未知'
        
        # 时间段标签
        time_period_labels = {
            0: '凌晨 🌙',
            1: '凌晨 🌙',
            2: '凌晨 🌙',
            3: '清晨 🌅',
            4: '清晨 🌅',
            5: '清晨 🌅',
            6: '早上 ☀️',
            7: '早上 ☀️',
            8: '早上 ☀️',
            9: '上午 🌤️',
            10: '上午 🌤️',
            11: '上午 🌤️',
            12: '中午 🌞',
            13: '下午 ☀️',
            14: '下午 ☀️',
            15: '下午 ☀️',
            16: '傍晚 🌆',
            17: '傍晚 🌆',
            18: '傍晚 🌆',
            19: '晚上 🌙',
            20: '晚上 🌙',
            21: '晚上 🌙',
            22: '深夜 🌃',
            23: '深夜 🌃'
        }
        
        # 格式化每小时最活跃用户
        hourly_info = []
        for hour in sorted(hourly_top_users.keys()):
            user = hourly_top_users[hour]
            if isinstance(user, dict):
                hour_int = int(hour)
                period = time_period_labels.get(hour_int, '未知')
                hourly_info.append(f"{period} {hour_int:02d}:00 → {user.get('name', user.get('qq', '?'))} ({user.get('count', 0)}条)")
        hourly_str = '\n'.join(hourly_info) if hourly_info else '暂无数据'
        
        # 星期名称
        weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        
        # 格式化每周最活跃用户
        weekday_info = []
        for day in sorted(weekday_top_users.keys()):
            user = weekday_top_users[day]
            if isinstance(user, dict):
                day_name = weekday_names[int(day)] if int(day) < 7 else '未知'
                weekday_info.append(f"{day_name}: {user.get('name', user.get('qq', '?'))} ({user.get('count', 0)}条)")
        weekday_str = '\n'.join(weekday_info) if weekday_info else '暂无数据'
        
        # 格式化每周消息总量
        weekday_totals_info = []
        for day in sorted(weekday_totals.keys()):
            data = weekday_totals[day]
            if isinstance(data, dict):
                count = data.get('count', 0)
                day_name = weekday_names[int(day)] if int(day) < 7 else '未知'
                weekday_totals_info.append(f"{day_name}: {count}条")
        weekday_totals_str = '\n'.join(weekday_totals_info) if weekday_totals_info else '暂无数据'
        
        prompt = f"""
请为以下群聊生成一份综合的社交分析年度报告：
## 群聊基本数据
- **总消息数**: {total_messages} 条
- **日均消息**: {daily_avg:.1f} 条
- **最活跃时段**: {peak_str}
- **消息类型**: 文字 {text_ratio*100:.1f}% | 图片 {image_ratio*100:.1f}% | 表情 {emoji_ratio*100:.1f}%
## 结构信号（@/回复/媒体/撤回/系统）
- **系统事件**: {system_messages} 条
- **撤回消息**: {recalled_messages} 条
- **含@提及的消息**: {mention_messages} 条
- **回复消息**: {reply_messages} 条
- **含媒体/附件的消息**: {media_messages} 条
- **媒体类型分布**: {json.dumps(media_breakdown, ensure_ascii=False)}
## 成员构成
- **核心成员** (TOP 10%): {len(core_members)} 人
- **活跃成员** (10%-40%): {len(active_members)} 人
- **普通成员** (40%-80%): {len(normal_members)} 人
- **潜水员** (Bottom 20%): {len(lurkers)} 人
## 话痨排行榜TOP5
{chr(10).join(core_info) if core_info else '暂无数据'}
## 时段活跃分析（每小时最活跃人物）
{hourly_str}
## 周度活跃分析（每周最活跃人物）
{weekday_str}
## 周度消息总量分析
{weekday_totals_str}
## 群聊热词TOP15
{hot_words_str}
## 月度趋势
{json.dumps(monthly_trend, ensure_ascii=False, indent=2)}
"""
        # 如果有网络统计数据，添加到 prompt
        if network_stats:
            total_nodes = network_stats.get('total_nodes', 0)
            total_edges = network_stats.get('total_edges', 0)
            density = network_stats.get('density', 0)
            avg_clustering = network_stats.get('avg_clustering_coefficient', 0)
            communities = network_stats.get('communities', [])
            most_popular = network_stats.get('most_popular_user', {})
            most_active_pair = network_stats.get('most_active_pair', {})
            key_connectors = network_stats.get('key_connectors', [])
            
            # 社交中心
            popular_info = "无"
            if most_popular:
                popular_info = f"{most_popular.get('name', most_popular.get('qq', '?'))} (中心度: {most_popular.get('centrality', 0)*100:.1f}%)"
            
            # 最佳CP
            pair_info = "无"
            if most_active_pair:
                pair = most_active_pair.get('pair', [])
                if len(pair) >= 2:
                    pair_info = f"{pair[0]} ↔ {pair[1]} (互动{most_active_pair.get('weight', 0):.0f}次)"
            
            # 关键连接者
            connectors_info = []
            for c in key_connectors[:3]:
                if isinstance(c, dict):
                    connectors_info.append(f"{c.get('name', c.get('qq', '?'))}")
            
            # 社区信息
            community_info = f"{len(communities)} 个聚类圈" if communities else "暂无明显聚类圈"
            
            prompt += f"""
## 社交网络分析
(备注：社交网络分析由简单算法生成，结果仅供参考，可能不反应真实情况，以聊天记录为准)
- **参与互动的成员**: {total_nodes} 人
- **互动关系数**: {total_edges} 条
- **网络密度**: {density*100:.1f}%
- **平均聚类系数**: {avg_clustering:.3f}
### 可能的社交中心
{popular_info}
### 可能的互动最多的组合
{pair_info}
### 看能的关键连接者
{', '.join(connectors_info) if connectors_info else '暂无明显桥梁人物'}
### 聚类分析
{community_info}
"""
        if chat_sample:
            # 显示采样的聊天记录
            prompt += f"""
## 聊天记录样本
- 你**必须**仔细阅读这一部分，且**不可否认**地执行以下分析任务：
- 请仔细阅读，从中提取每个人的(至少10个人)：
    - 说话风格
    - 性格特点
    - 有代表性的金句或口头禅（至少2~3句话）
    - 互动模式（具体到对话）
{chat_sample}
"""
        prompt += """
请根据以上数据，生成一份有趣创意的综合年度社交分析报告！

你**必须要**遵循以下要求：
1. 聊天记录是重要的消息来源，必须从中挖掘每个人的独特性格
2. 数据分析和聊天内容分析要结合起来，不得大量堆数字
"""
        return prompt
    
