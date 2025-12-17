from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import Config
from src.chat_import import load_chat_file


# texts 目录与允许的输入文件类型
TEXTS_DIR = Path('texts')
ALLOWED_SUFFIXES = {'.txt', '.json'}


_CONV_CACHE: dict[tuple[str, str], dict[str, Any]] = {}


def _freeze_options(options: dict | None) -> str:
    """把 options 转成缓存 key"""

    if not options:
        return ""
    try:
        items = sorted((str(k), repr(v)) for k, v in options.items())
        return "|".join([f"{k}={v}" for k, v in items])
    except Exception:
        return repr(options)


def safe_texts_file_path(filename: str) -> Path:
    """把用户输入的文件名映射到 texts/ 下，仅允许 .txt/.json。"""
    if not filename or not isinstance(filename, str):
        raise ValueError('未指定文件名')

    texts_dir = TEXTS_DIR.resolve()
    candidate = (TEXTS_DIR / filename).resolve()

    if texts_dir not in candidate.parents and candidate != texts_dir:
        raise ValueError('非法文件路径')

    if candidate.suffix.lower() not in ALLOWED_SUFFIXES:
        raise ValueError('不支持的文件类型')

    return candidate


def format_time_from_ts_ms(ts_ms: int, *, use_utc: bool = False) -> str:
    """把 epoch ms 转为时间字符串。

    - JSON：timestamp epoch 以 UTC 计算；展示也用 UTC（wysiwyg 模式）
    - TXT：保持旧语义（本地时间）。
    """
    try:
        if not ts_ms:
            return ''
        if use_utc:
            return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        return datetime.fromtimestamp(ts_ms / 1000).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return ''


def parse_bool_query(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    s = str(value).strip().lower()
    if s in ('1', 'true', 'yes', 'on'):
        return True
    if s in ('0', 'false', 'no', 'off'):
        return False
    return default


def load_conversation_and_messages(filename: str, *, options=None):
    """从 texts/ 加载归一化会话，并返回适配现有分析/AI 的消息字典列表。"""
    options = options or {}
    filepath = safe_texts_file_path(filename)
    if not filepath.exists():
        raise FileNotFoundError('文件不存在')

    # cache hit
    cache_key = (str(filename), _freeze_options(options))
    file_mtime = filepath.stat().st_mtime
    cached = _CONV_CACHE.get(cache_key)
    if cached and cached.get('mtime') == file_mtime:
        return cached['conv'], cached['messages'], cached['warnings']

    result = load_chat_file(str(filepath), options=options)
    conv = result.conversation

    # participantId -> displayName
    pid_to_name = {p.participant_id: p.display_name for p in (conv.participants or [])}

    # message_id -> sender_participant_id，用于把 reply 引用解析到“回复了谁”
    message_id_to_sender: dict[str, str] = {}
    for m in conv.messages:
        if m.message_id and m.sender_participant_id:
            message_id_to_sender[str(m.message_id)] = str(m.sender_participant_id)

    messages = []
    use_utc_time = False
    if filepath.suffix.lower() == '.json':
        mode = (getattr(Config, 'JSON_TIMESTAMP_MODE', None) or 'utc_to_local').strip().lower()
        # - utc_to_local: epoch 是 UTC，展示用本地时间
        # - wysiwyg: epoch 固定按 UTC 计算，展示也用 UTC（避免本机时区影响）
        use_utc_time = (mode == 'wysiwyg')
    for m in conv.messages:
        time_str = format_time_from_ts_ms(m.timestamp_ms, use_utc=use_utc_time)

        qq = m.sender_participant_id or 'system'
        sender = m.sender_name or pid_to_name.get(qq, qq) or ('系统' if qq == 'system' else qq)

        mention_targets = []
        for it in (m.mentions or []):
            try:
                pid = getattr(it, 'target_participant_id', None)
                name = getattr(it, 'target_name', None)
                uin = getattr(it, 'target_uin', None)
                uid = getattr(it, 'target_uid', None)
                mention_targets.append(pid or uin or uid or name)
            except Exception:
                continue
        mention_targets = [str(x) for x in mention_targets if x]

        reply_to_mid = None
        if m.reply_to is not None:
            reply_to_mid = getattr(m.reply_to, 'target_message_id', None)
            if reply_to_mid is not None:
                reply_to_mid = str(reply_to_mid)

        reply_to_qq = message_id_to_sender.get(reply_to_mid) if reply_to_mid else None


        content_clean = m.text or ''
        content_raw = m.content_text or content_clean

        messages.append({
            'time': time_str,
            'sender': sender,
            'qq': str(qq),
            'content': content_clean,
            'content_raw': content_raw,

            # structured meta
            'timestamp_ms': int(m.timestamp_ms or 0),
            'message_id': str(m.message_id) if m.message_id is not None else None,
            'is_system': bool(m.is_system),
            'is_recalled': bool(m.is_recalled),
            'message_type': str(m.message_type or 'unknown'),
            'element_counts': dict(getattr(m, 'element_counts', None) or {}),
            'mention_count': int(len(mention_targets)),
            'mentions': mention_targets,
            'reply_to_message_id': reply_to_mid,
            'reply_to_qq': reply_to_qq,
        })

    _CONV_CACHE[cache_key] = {
        'mtime': file_mtime,
        'conv': conv,
        'messages': messages,
        'warnings': result.warnings,
    }

    return conv, messages, result.warnings
