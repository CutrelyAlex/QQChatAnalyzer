"""
数据修剪模块 - Token管理和稀疏切割
T040-T043: DataPruner类实现

功能:
- Token估算: 基于字符数+消息数的快速估算
- 稀疏切割: 按天均匀采样，保持上下文完整
- 修剪详情: 计算保留比例、被移除天数、采样步长
"""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any, Optional
import math


class DataPruner:
    """
    数据修剪器 - 智能Token管理和数据稀疏切割
    
    主要功能:
    1. 快速Token估算
    2. 基于天的均匀采样
    3. 保留上下文完整性
    """
    
    # Token估算系数 (经验值)
    CHARS_PER_TOKEN_CN = 1.5  # 中文字符约1.5字符/token
    CHARS_PER_TOKEN_EN = 4.0  # 英文字符约4字符/token
    MESSAGE_OVERHEAD = 4      # 每条消息的额外token开销（格式、时间戳等）
    
    def __init__(self, max_tokens: int = 100000):
        """
        初始化修剪器
        
        Args:
            max_tokens: 最大允许的token数
        """
        self.max_tokens = max_tokens
        self.messages_by_date = defaultdict(list)  # {date_str: [messages]}
        self.total_messages = 0
        self.total_tokens_estimate = 0
        
    def load_messages(self, messages: List[Dict[str, Any]]) -> None:
        """
        加载消息列表并按日期分组
        
        Args:
            messages: 消息列表，每条包含 time, content 字段
        """
        self.messages_by_date.clear()
        self.total_messages = 0
        
        for msg in messages:
            time_str = msg.get('time', '')
            try:
                # 提取日期部分 (YYYY-MM-DD)
                date_str = time_str[:10] if len(time_str) >= 10 else 'unknown'
            except:
                date_str = 'unknown'
            
            self.messages_by_date[date_str].append(msg)
            self.total_messages += 1
        
        # 计算总token估算
        self.total_tokens_estimate = self._estimate_total_tokens()
    
    def load_from_lines(self, lines: List[str], lines_data: List[Any]) -> None:
        """
        从LineProcess的输出加载消息
        
        Args:
            lines: 原始文本行
            lines_data: LineData对象列表
        """
        self.messages_by_date.clear()
        self.total_messages = 0
        
        for line_data in lines_data:
            time_str = line_data.timepat if hasattr(line_data, 'timepat') else ''
            content = line_data.raw_text if hasattr(line_data, 'raw_text') else str(line_data)
            
            try:
                date_str = time_str[:10] if len(time_str) >= 10 else 'unknown'
            except:
                date_str = 'unknown'
            
            self.messages_by_date[date_str].append({
                'time': time_str,
                'content': content,
                'qq': getattr(line_data, 'qq', ''),
                'sender': getattr(line_data, 'sender', '')
            })
            self.total_messages += 1
        
        self.total_tokens_estimate = self._estimate_total_tokens()
    
    def _estimate_total_tokens(self) -> int:
        """估算所有消息的总token数"""
        total = 0
        for date_messages in self.messages_by_date.values():
            for msg in date_messages:
                total += self._estimate_message_tokens(msg.get('content', ''))
        return total
    
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
        
        for char in content:
            if '\u4e00' <= char <= '\u9fff':  # 中文
                cn_chars += 1
            else:
                en_chars += 1
        
        tokens = (cn_chars / self.CHARS_PER_TOKEN_CN) + \
                 (en_chars / self.CHARS_PER_TOKEN_EN) + \
                 self.MESSAGE_OVERHEAD
        
        return int(math.ceil(tokens))
    
    def estimate_tokens(self) -> Dict[str, Any]:
        """
        T041: Token估算 - 返回详细的token统计
        
        Returns:
            {
                'total_tokens': int,
                'total_messages': int,
                'total_days': int,
                'avg_tokens_per_day': float,
                'avg_tokens_per_message': float,
                'needs_pruning': bool,
                'overflow_ratio': float
            }
        """
        total_days = len(self.messages_by_date)
        avg_per_day = self.total_tokens_estimate / total_days if total_days > 0 else 0
        avg_per_msg = self.total_tokens_estimate / self.total_messages if self.total_messages > 0 else 0
        
        return {
            'total_tokens': self.total_tokens_estimate,
            'total_messages': self.total_messages,
            'total_days': total_days,
            'avg_tokens_per_day': round(avg_per_day, 1),
            'avg_tokens_per_message': round(avg_per_msg, 1),
            'needs_pruning': self.total_tokens_estimate > self.max_tokens,
            'overflow_ratio': round(self.total_tokens_estimate / self.max_tokens, 2) if self.max_tokens > 0 else 0
        }
    
    def calculate_pruning_strategy(self) -> Dict[str, Any]:
        """
        T043: 计算修剪策略详情
        
        Returns:
            {
                'retention_ratio': float,  # 保留比例 0-1
                'keep_days': int,          # 保留天数
                'remove_days': int,        # 移除天数
                'sample_step': int,        # 采样步长
                'strategy': str,           # 策略描述
                'estimated_tokens_after': int
            }
        """
        total_days = len(self.messages_by_date)
        
        if self.total_tokens_estimate <= self.max_tokens:
            return {
                'retention_ratio': 1.0,
                'keep_days': total_days,
                'remove_days': 0,
                'sample_step': 1,
                'strategy': '无需修剪，数据量在限制范围内',
                'estimated_tokens_after': self.total_tokens_estimate
            }
        
        # 计算需要保留的比例
        retention_ratio = self.max_tokens / self.total_tokens_estimate
        
        # 按天采样的策略
        keep_days = max(1, int(total_days * retention_ratio))
        remove_days = total_days - keep_days
        
        # 计算采样步长 (每step天保留1天)
        sample_step = max(1, int(total_days / keep_days))
        
        # 估算修剪后的token数
        estimated_after = int(self.total_tokens_estimate * retention_ratio)
        
        strategy = f'按比例均匀采样，保留约{int(retention_ratio * 100)}%的数据'
        if sample_step > 1:
            strategy += f'，每{sample_step}天采样1天'
        
        return {
            'retention_ratio': round(retention_ratio, 3),
            'keep_days': keep_days,
            'remove_days': remove_days,
            'sample_step': sample_step,
            'strategy': strategy,
            'estimated_tokens_after': estimated_after
        }
    
    def prune(self, strategy: str = 'uniform') -> Tuple[List[Dict], Dict[str, Any]]:
        """
        T042: 执行数据修剪 - 稀疏切割算法
        
        Args:
            strategy: 修剪策略
                - 'uniform': 均匀采样（默认）
                - 'recent': 保留最近的数据
                - 'important': 保留活跃度高的日期
        
        Returns:
            (pruned_messages, pruning_info)
        """
        if self.total_tokens_estimate <= self.max_tokens:
            # 不需要修剪
            all_messages = []
            for date_messages in self.messages_by_date.values():
                all_messages.extend(date_messages)
            return all_messages, {
                'pruned': False,
                'original_messages': self.total_messages,
                'final_messages': self.total_messages,
                'original_tokens': self.total_tokens_estimate,
                'final_tokens': self.total_tokens_estimate
            }
        
        # 获取所有日期并排序
        sorted_dates = sorted(self.messages_by_date.keys())
        total_days = len(sorted_dates)
        
        # 计算保留比例
        retention_ratio = self.max_tokens / self.total_tokens_estimate
        keep_days = max(1, int(total_days * retention_ratio))
        
        # 选择要保留的日期
        if strategy == 'recent':
            # 保留最近的日期
            selected_dates = sorted_dates[-keep_days:]
        elif strategy == 'important':
            # 保留消息最多的日期
            date_counts = [(d, len(self.messages_by_date[d])) for d in sorted_dates]
            date_counts.sort(key=lambda x: x[1], reverse=True)
            selected_dates = sorted([d for d, _ in date_counts[:keep_days]])
        else:  # uniform (默认)
            # 均匀采样
            step = total_days / keep_days
            selected_indices = [int(i * step) for i in range(keep_days)]
            selected_dates = [sorted_dates[i] for i in selected_indices if i < total_days]
        
        # 收集选中日期的消息
        pruned_messages = []
        for date in selected_dates:
            pruned_messages.extend(self.messages_by_date[date])
        
        # 计算修剪后的token数
        final_tokens = sum(
            self._estimate_message_tokens(msg.get('content', ''))
            for msg in pruned_messages
        )
        
        return pruned_messages, {
            'pruned': True,
            'strategy': strategy,
            'original_messages': self.total_messages,
            'final_messages': len(pruned_messages),
            'original_tokens': self.total_tokens_estimate,
            'final_tokens': final_tokens,
            'original_days': total_days,
            'kept_days': len(selected_dates),
            'removed_days': total_days - len(selected_dates),
            'retention_ratio': round(len(pruned_messages) / self.total_messages, 3) if self.total_messages > 0 else 0
        }
    
    def get_date_distribution(self) -> List[Dict[str, Any]]:
        """
        获取按日期的消息分布（用于可视化）
        
        Returns:
            [{date: str, message_count: int, token_estimate: int}, ...]
        """
        distribution = []
        for date in sorted(self.messages_by_date.keys()):
            messages = self.messages_by_date[date]
            token_est = sum(
                self._estimate_message_tokens(msg.get('content', ''))
                for msg in messages
            )
            distribution.append({
                'date': date,
                'message_count': len(messages),
                'token_estimate': token_est
            })
        return distribution
    
    def format_messages_for_ai(self, messages: List[Dict], 
                               include_time: bool = True,
                               include_sender: bool = True) -> str:
        """
        将消息格式化为AI可读的文本
        
        Args:
            messages: 消息列表
            include_time: 是否包含时间
            include_sender: 是否包含发送者
        
        Returns:
            格式化后的文本
        """
        lines = []
        for msg in messages:
            parts = []
            if include_time and msg.get('time'):
                parts.append(f"[{msg['time']}]")
            if include_sender and (msg.get('sender') or msg.get('qq')):
                sender = msg.get('sender') or msg.get('qq')
                parts.append(f"{sender}:")
            parts.append(msg.get('content', ''))
            lines.append(' '.join(parts))
        
        return '\n'.join(lines)


# 快捷函数
def estimate_file_tokens(filepath: str, max_tokens: int = 100000) -> Dict[str, Any]:
    """
    快速估算文件的token数
    
    Args:
        filepath: 文件路径
        max_tokens: 最大token限制
    
    Returns:
        Token估算结果
    """
    try:
        from .LineProcess import process_lines_data
    except ImportError:
        from LineProcess import process_lines_data
    
    lines, lines_data, _ = process_lines_data(filepath, mode='all')
    
    pruner = DataPruner(max_tokens)
    pruner.load_from_lines(lines, lines_data)
    
    return pruner.estimate_tokens()


def prune_file_for_ai(filepath: str, max_tokens: int = 100000, 
                      strategy: str = 'uniform') -> Tuple[str, Dict[str, Any]]:
    """
    修剪文件数据以适应AI的token限制
    
    Args:
        filepath: 文件路径
        max_tokens: 最大token限制
        strategy: 修剪策略
    
    Returns:
        (formatted_text, pruning_info)
    """
    try:
        from .LineProcess import process_lines_data
    except ImportError:
        from LineProcess import process_lines_data
    
    lines, lines_data, _ = process_lines_data(filepath, mode='all')
    
    pruner = DataPruner(max_tokens)
    pruner.load_from_lines(lines, lines_data)
    
    pruned_messages, info = pruner.prune(strategy)
    formatted_text = pruner.format_messages_for_ai(pruned_messages)
    
    return formatted_text, info
