"""
AI总结模块 - 使用OpenAI生成创意风格的聊天总结
"""

import os
import json
import logging
import math
from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import defaultdict

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
                 context_budget: int = None, timeout: int = None):
        """
        初始化AI总结器
        
        Args:
            model: 使用的模型名称
            max_tokens: 生成的最大token数（输出）
            api_key: OpenAI API密钥（可选，使用环境变量如未提供）
            base_url: OpenAI API基础URL（可选，使用环境变量如未提供）
            context_budget: 聊天记录的Token预算（输入），默认60000
            timeout: API请求超时时间（秒），从请求发送到完全接收响应，默认30秒
        """
        self.model = model or os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')
        self.max_tokens = max_tokens
        self.context_budget = context_budget or self.DEFAULT_CONTEXT_BUDGET
        self.timeout = timeout or int(os.environ.get('OPENAI_REQUEST_TIMEOUT', 30))
        
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
        retention_ratio = available_budget / total_tokens
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
                temperature=0.8  # 增加创意性
            )
            
            summary = response.choices[0].message.content
            
            return {
                'success': True,
                'summary': summary,
                'tokens_used': response.usage.total_tokens if response.usage else 0,
                'model': self.model
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
                temperature=0.8
            )
            
            summary = response.choices[0].message.content
            
            return {
                'success': True,
                'summary': summary,
                'tokens_used': response.usage.total_tokens if response.usage else 0,
                'model': self.model
            }
        except Exception as e:
            logger.error(f"Group and network summary generation failed: {e}")
            return {
                'success': False,
                'summary': '',
                'error': str(e)
            }
    

    def _get_system_prompt(self, summary_type: str) -> str:
        """获取系统提示词"""
        
        base_style = """
你是一个超级有趣的聊天记录分析师，风格包含：
- 🎮 辣评：毒舌但不伤人，吐槽中带着爱
- 🎵 温情脉脉：充满仪式感和人情味
- 📱 数据可视化风格：用数据讲故事

写作要求：
1. 使用有趣的语言，让报告生动有趣
2. 创造针对单个用户（昵称称呼，但用QQ号区分）个性化的"称号"和"成就徽章"
3. 用网络热梗和流行语，但不要太过时
4. 数据要具体，但表达要有趣
5. 适度毒舌吐槽，但要让人会心一笑而不是生气
6. 最后给一个总结

输出格式：使用Markdown格式，包含标题、加粗等
"""
        
        type_specific = {
            'personal': """
## 个人报告特殊要求：

根据用户的聊天数据，生成一份个性化的"年度人设报告"，包含：

1. **开场白** - 用一句话概括这个人的群聊人设
2. **专属称号** - 根据数据给出2-3个有趣的称号，例如：
   - 🌙 "凌晨三点の群聊守护者" (如果深夜活跃)
   - 🐔 "早起打卡第一人" (如果早起活跃)  
   - 💬 "日均999+消息の话痨" (如果消息多)
   - 🤫 "神秘潜水员" (如果消息少)
   - 📸 "表情包の传教士" (如果表情多)

3. **数据亮点** - 挑选最有趣的2-3个数据点，用有趣的方式呈现
4. **群聊画风分析** - 根据热词和消息特点分析ta的说话风格
5. **年度金句** - 写一段性格分析：
   - 🎯 **专属人设标签** - 一句话概括这个人的群聊形象
   - 💬 **说话风格** - ta通常怎么说话？是简洁还是啰嗦？正经还是搞怪？
   - 🎭 **性格特点** - 从聊天内容分析ta的性格：热情/冷淡、话多/话少、爱吐槽/正能量等
   - 📝 **代表性金句** - 从聊天样本中找出最能代表ta风格的一句话（如果有的话）
   - 🏆 **专属成就** - 给ta一个量身定制的搞笑成就/头衔
6. **毒舌吐槽** - 一小段友善的吐槽
""",
            'group_and_network': """
## 群体和社交网络融合报告特殊要求：

生成一份综合的"年度社交分析报告"，融合群体活力和人际关系，**重点关注聊天记录内容，深入分析每个人的性格特点**。

### 📊 第一部分：群聊档案与活力指数
1. **群聊档案** - 一句话概括这个群的气质
2. **群活力指数** - 根据消息量评级，给个有趣的评语如：
   - 🔥🔥🔥🔥🔥 "比春晚弹幕还热闹"
   - 🔥🔥🔥 "三天不看就999+"
   - 🔥 "安静得像个学习群"
3. **年度MVP榜单** - 给核心成员颁奖（话痨之王、深夜守护者、早起卷王、表情包大户等）

### 👤 第二部分：群友性格画像（核心内容！）
**这是报告的重点！** 根据聊天记录，为每个活跃成员生成独特的性格分析：

4. **群友性格大赏** - 为排名前5-8位的活跃成员分别写一段性格分析：
   - 🎯 **专属人设标签** - 一句话概括这个人的群聊形象
   - 💬 **说话风格** - ta通常怎么说话？是简洁还是啰嗦？正经还是搞怪？
   - 🎭 **性格特点** - 从聊天内容分析ta的性格：热情/冷淡、话多/话少、爱吐槽/正能量等
   - 📝 **代表性金句** - 从聊天样本中找出最能代表ta风格的一句话（如果有的话）
   - 🏆 **专属成就** - 给ta一个量身定制的搞笑成就/头衔

5. **群友CP速配榜** - 根据互动关系，给互动最多的几对组合起CP名，分析他们的互动模式

### 👥 第三部分：人际关系与社交网络
6. **社交中心（人气王）** - 谁是群里的社交达人，给ta一个有趣的称号
7. **最佳CP** - 互动最多的组合，给他们起个CP名，吐槽他们的互动风格
8. **小圈子分析** - 群里有哪些小团体或派系，简单描述他们的特点
9. **社交达人建议** - 给潜水党或冷场人的友好建议（调侃向，不要太扎心）

### 🎯 第四部分：综合分析与总结
10. **群聊热词云** - TOP 热词体现的群文化
11. **活跃时间段分析** - 这个群什么时候最活跃，给个有趣的解读
12. **年度大事记** - 根据月度趋势和聊天记录猜测群里发生过什么有趣的事
13. **群聊画风鉴定与社交氛围总结** - 这是个什么类型的群，社交氛围如何

### ✨ 整体风格要求：
- **聊天记录是核心素材**：仔细阅读聊天样本，从中挖掘每个人的说话风格和性格
- **个性化分析**：不要泛泛而谈，要针对具体的人说具体的话
- 融合群体热度和人际温度，既要体现活力指数，也要挖掘人情味
- 避免冷冰冰的数据分析，用故事和趣事来诠释数据
- 对每个人和派系的描述要有个性，让人看了会心一笑
"""
      }
        
        return base_style + type_specific.get(summary_type, '')
    
    def _build_personal_prompt(self, stats: Dict[str, Any], 
                                chat_sample: str = "") -> str:
        """构建个人总结的用户提示词"""
        
        # 提取关键数据
        nickname = stats.get('nickname', '神秘用户')
        qq = stats.get('qq', 'unknown')
        total_messages = stats.get('total_messages', 0)
        active_days = stats.get('active_days', 0)
        time_dist = stats.get('time_distribution', {})
        user_type = stats.get('user_type', '普通用户')
        at_count = stats.get('at_count', 0)
        being_at_count = stats.get('being_at_count', 0)
        avg_length = stats.get('avg_message_length', 0)
        image_count = stats.get('image_count', 0)
        emoji_count = stats.get('emoji_count', 0)
        top_words = stats.get('top_words', [])
        max_streak = stats.get('max_streak_days', 0)
        monthly = stats.get('monthly_messages', {})
        
        # 找出最活跃的时段
        peak_time = max(time_dist.items(), key=lambda x: x[1])[0] if time_dist else '未知'
        
        # 找出最活跃的月份
        peak_month = max(monthly.items(), key=lambda x: x[1])[0] if monthly else '未知'
        
        # 热词字符串
        hot_words_str = ', '.join([w['word'] for w in top_words[:10]]) if top_words else '无'
        
        prompt = f"""
请为以下用户生成一份有趣的个人聊天报告：

## 📊 用户数据

- **昵称**: {nickname}
- **QQ号**: {qq}
- **总消息数**: {total_messages} 条
- **活跃天数**: {active_days} 天
- **最长连续活跃**: {max_streak} 天
- **用户类型**: {user_type}
- **最活跃时段**: {peak_time}
- **最活跃月份**: {peak_month}

## 📈 互动数据
- **@别人次数**: {at_count} 次
- **被@次数**: {being_at_count} 次
- **平均消息长度**: {avg_length:.1f} 字
- **发送图片**: {image_count} 张
- **发送表情**: {emoji_count} 个

## 🔥 热词TOP10
{hot_words_str}

## ⏰ 时段分布
{json.dumps(time_dist, ensure_ascii=False, indent=2)}

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
        
        # 新增的时间统计数据（非常重要！）
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

## 📊 群聊活力数据

- **总消息数**: {total_messages} 条
- **日均消息**: {daily_avg:.1f} 条
- **最活跃时段**: {peak_str}
- **消息类型**: 文字 {text_ratio*100:.1f}% | 图片 {image_ratio*100:.1f}% | 表情 {emoji_ratio*100:.1f}%

## 👥 成员构成
- **核心成员** (TOP 10%): {len(core_members)} 人
- **活跃成员** (10%-40%): {len(active_members)} 人
- **普通成员** (40%-80%): {len(normal_members)} 人
- **潜水员** (Bottom 20%): {len(lurkers)} 人

## 👑 话痨排行榜TOP5
{chr(10).join(core_info) if core_info else '暂无数据'}

## ⏰ 时段活跃分析（每小时最活跃人物）
{hourly_str}

## 📅 周度活跃分析（每周最活跃人物）
{weekday_str}

## 📊 周度消息总量分析
{weekday_totals_str}

## 🔥 群聊热词TOP15
{hot_words_str}

## 📈 月度趋势
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
            community_info = f"{len(communities)} 个小圈子" if communities else "暂无明显小圈子"
            
            prompt += f"""
## 🕸️ 社交网络分析

- **参与互动的成员**: {total_nodes} 人
- **互动关系数**: {total_edges} 条
- **网络密度**: {density*100:.1f}%
- **平均聚类系数**: {avg_clustering:.3f}

### 社交中心（人气王）
{popular_info}

### 最佳CP（互动最多的组合）
{pair_info}

### 关键连接者（社交桥梁）
{', '.join(connectors_info) if connectors_info else '暂无明显桥梁人物'}

### 小圈子分析
{community_info}
"""
        
        if chat_sample:
            # 显示采样的聊天记录（已经过稀疏采样，无需再截断）
            prompt += f"""
## 💬 聊天记录样本（核心素材！用于分析群友性格和说话风格）

⚠️ **重要提示**：以下聊天记录是分析的核心素材！请仔细阅读，从中提取每个人的：
- 说话风格（正式/随意、简洁/啰嗦、搞笑/严肃等）
- 性格特点（外向/内向、活泼/稳重、吐槽系/正能量等）
- 有代表性的金句或口头禅
- 互动模式（爱接话茬/爱发起话题/爱回应别人等）

{chat_sample}
"""
        
        prompt += """
请根据以上数据，生成一份有趣创意的综合年度社交分析报告！

**特别要求**：
1. 聊天记录是报告的灵魂，务必从中挖掘每个人的独特性格
2. 对活跃成员的描写要具体生动，让群友看了能会心一笑
3. 融合群体热度和人际温度，既体现活力指数，也要挖掘人情味
4. 数据分析和聊天内容分析要结合起来，不要只堆数字
"""
        
        return prompt
    
