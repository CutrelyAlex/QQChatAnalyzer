"""
AI总结模块 - 使用OpenAI生成创意风格的聊天总结
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

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
    """
    
    def __init__(self, model: str = None, max_tokens: int = 2000, 
                 api_key: str = None, base_url: str = None):
        """
        初始化AI总结器
        
        Args:
            model: 使用的模型名称
            max_tokens: 生成的最大token数
            api_key: OpenAI API密钥（可选，使用环境变量如未提供）
            base_url: OpenAI API基础URL（可选，使用环境变量如未提供）
        """
        self.model = model or os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')
        self.max_tokens = max_tokens
        
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
            
            kwargs = {'api_key': final_api_key}
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
    
    def generate_personal_summary(self, stats: Dict[str, Any], 
                                   chat_sample: str = "") -> Dict[str, Any]:
        """
        T051: 生成个人总结 - 创意风格的年度报告
        
        Args:
            stats: PersonalStats.to_dict() 的结果
            chat_sample: 可选的聊天记录样本
        
        Returns:
            {'success': bool, 'summary': str, 'error': str}
        """
        if not self.is_available():
            return {
                'success': False,
                'summary': '',
                'error': 'AI服务未配置，请设置 OPENAI_API_KEY 环境变量'
            }
        
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
    
    def generate_group_summary(self, stats: Dict[str, Any],
                                chat_sample: str = "") -> Dict[str, Any]:
        """
        生成群体总结
        
        Args:
            stats: GroupStats.to_dict() 的结果
            chat_sample: 可选的聊天记录样本
        
        Returns:
            {'success': bool, 'summary': str, 'error': str}
        """
        if not self.is_available():
            return {
                'success': False,
                'summary': '',
                'error': 'AI服务未配置，请设置 OPENAI_API_KEY 环境变量'
            }
        
        prompt = self._build_group_prompt(stats, chat_sample)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt('group')},
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
            logger.error(f"Group summary generation failed: {e}")
            return {
                'success': False,
                'summary': '',
                'error': str(e)
            }
    
    def generate_network_summary(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成社交网络总结
        
        Args:
            stats: NetworkStats.to_dict() 的结果
        
        Returns:
            {'success': bool, 'summary': str, 'error': str}
        """
        if not self.is_available():
            return {
                'success': False,
                'summary': '',
                'error': 'AI服务未配置，请设置 OPENAI_API_KEY 环境变量'
            }
        
        prompt = self._build_network_prompt(stats)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt('network')},
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
            logger.error(f"Network summary generation failed: {e}")
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
5. **年度金句** - 如果有聊天样本，挑一句最有代表性的
6. **毒舌吐槽** - 一小段友善的吐槽
""",
            'group': """
## 群体报告特殊要求：

生成一份群聊的"年度群像报告"，像是给这个群颁发的年度大奖，包含：

1. **群聊档案** - 一句话概括这个群的气质
2. **群活力指数** - 根据消息量评级，给个有趣的评语如：
   - 🔥🔥🔥🔥🔥 "比春晚弹幕还热闹"
   - 🔥🔥🔥 "三天不看就999+"
   - 🔥 "安静得像个学习群"

3. **年度MVP榜单** - 给核心成员颁奖：
   - 👑 话痨之王
   - 🌙 深夜守护者
   - 🌅 早起卷王
   - 📸 表情包大户
   
4. **群聊热词云** - 分析热词，吐槽群聊画风
5. **活跃时间段分析** - 这个群什么时候最活跃，给个有趣的解读
6. **年度大事记** - 根据月度趋势猜测群里发生过什么
7. **群聊画风鉴定** - 这是个什么类型的群
""",
            'network': """
## 社交网络报告特殊要求：

生成一份"群聊社交图谱报告"，揭秘群里的人际关系，包含：

1. **社交图谱总览** - 一句话概括这个群的社交特点
2. **社交中心** - 谁是群里的社交达人，给ta一个称号
3. **最佳CP** - 互动最多的组合，给他们一个CP名
4. **小圈子分析** - 群里有哪些小团体
5. **社交冷知识** - 一些有趣的互动数据
6. **人际关系图鉴** - 根据网络特征分析群的社交氛围
7. **社交达人建议** - 给潜水党的社交建议（调侃向）
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
            prompt += f"""
## 💬 聊天样本（用于分析说话风格）
{chat_sample[:2000]}
"""
        
        prompt += """
请根据以上数据，生成一份有趣创意的个人年度总结！
"""
        
        return prompt
    
    def _build_group_prompt(self, stats: Dict[str, Any],
                             chat_sample: str = "") -> str:
        """构建群体总结的用户提示词"""
        
        total_messages = stats.get('total_messages', 0)
        daily_avg = stats.get('daily_average', 0)
        peak_hours = stats.get('peak_hours', [])
        core_members = stats.get('core_members', [])
        active_members = stats.get('active_members', [])
        normal_members = stats.get('normal_members', [])
        lurkers = stats.get('lurkers', [])
        hot_words = stats.get('hot_words', [])
        monthly_trend = stats.get('monthly_trend', {})
        text_ratio = stats.get('text_ratio', 0)
        image_ratio = stats.get('image_ratio', 0)
        emoji_ratio = stats.get('emoji_ratio', 0)
        
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
        
        prompt = f"""
请为以下群聊生成一份有趣的群体年度报告：

## 📊 群聊数据

- **总消息数**: {total_messages} 条
- **日均消息**: {daily_avg:.1f} 条
- **最活跃时段**: {peak_str}

## 👥 成员构成
- **核心成员** (TOP 10%): {len(core_members)} 人
- **活跃成员** (10%-40%): {len(active_members)} 人
- **普通成员** (40%-80%): {len(normal_members)} 人
- **潜水员** (Bottom 20%): {len(lurkers)} 人

## 👑 话痨排行榜TOP5
{chr(10).join(core_info) if core_info else '暂无数据'}

## 💬 消息类型占比
- 文字消息: {text_ratio*100:.1f}%
- 图片消息: {image_ratio*100:.1f}%
- 表情消息: {emoji_ratio*100:.1f}%

## 🔥 群聊热词TOP15
{hot_words_str}

## 📅 月度趋势
{json.dumps(monthly_trend, ensure_ascii=False, indent=2)}
"""
        
        if chat_sample:
            prompt += f"""
## 💬 聊天样本（用于分析群聊画风）
{chat_sample[:2000]}
"""
        
        prompt += """
请根据以上数据，生成一份有趣创意的群聊年度总结！
"""
        
        return prompt
    
    def _build_network_prompt(self, stats: Dict[str, Any]) -> str:
        """构建社交网络总结的用户提示词"""
        
        total_nodes = stats.get('total_nodes', 0)
        total_edges = stats.get('total_edges', 0)
        density = stats.get('density', 0)
        avg_clustering = stats.get('avg_clustering_coefficient', 0)
        communities = stats.get('communities', [])
        most_popular = stats.get('most_popular_user', {})
        most_active_pair = stats.get('most_active_pair', {})
        key_connectors = stats.get('key_connectors', [])
        
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
        
        prompt = f"""
请为以下群聊社交网络生成一份有趣的社交图谱报告：

## 🕸️ 网络概况

- **参与互动的成员**: {total_nodes} 人
- **互动关系数**: {total_edges} 条
- **网络密度**: {density*100:.1f}%
- **平均聚类系数**: {avg_clustering:.3f}

## 👑 社交中心（人气王）
{popular_info}

## 💕 最佳CP（互动最多的组合）
{pair_info}

## 🌉 关键连接者（社交桥梁）
{', '.join(connectors_info) if connectors_info else '暂无明显桥梁人物'}

## 👥 小圈子分析
{community_info}

请根据以上数据，生成一份年度报告风格的社交网络分析！
揭秘群里的人际关系，给CP起名，分析小圈子，最后给社恐/潜水党一些调侃建议。
"""
        
        return prompt


# 快捷函数
def generate_summary(summary_type: str, stats: Dict[str, Any], 
                     chat_sample: str = "") -> Dict[str, Any]:
    """
    快速生成AI总结
    
    Args:
        summary_type: 'personal', 'group', 或 'network'
        stats: 对应的统计数据
        chat_sample: 可选的聊天样本
    
    Returns:
        {'success': bool, 'summary': str, 'error': str}
    """
    summarizer = AISummarizer()
    
    if summary_type == 'personal':
        return summarizer.generate_personal_summary(stats, chat_sample)
    elif summary_type == 'group':
        return summarizer.generate_group_summary(stats, chat_sample)
    elif summary_type == 'network':
        return summarizer.generate_network_summary(stats)
    else:
        return {
            'success': False,
            'summary': '',
            'error': f'Unknown summary type: {summary_type}'
        }
