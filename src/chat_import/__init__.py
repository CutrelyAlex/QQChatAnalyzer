"""聊天导入与归一化层。

提供一个统一入口：把不同来源（TXT/JSON）的聊天记录加载为统一结构，
并输出可供分析器使用的数据。
"""

from .loader import load_chat_file

__all__ = [
    "load_chat_file",
]
