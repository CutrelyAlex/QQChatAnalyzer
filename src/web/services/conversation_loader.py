from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.config import Config
from src.chat_import import load_chat_file


# texts 目录与允许的输入文件类型
TEXTS_DIR = Path('texts')
ALLOWED_SUFFIXES = {'.txt', '.json'}


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


def legacy_placeholders_for_message(message_type: str, resource_types: list[str] | None, *, is_recalled: bool) -> str:
    """为旧分析器生成可读占位符。"""

    if is_recalled:
        return '撤回了一条消息'

    rt = [str(x) for x in (resource_types or []) if x]
    tokens: list[str] = []

    # 旧的
    if 'image' in rt:
        tokens.append('[图片]')
    if 'emoji' in rt or 'sticker' in rt:
        tokens.append('[表情]')

    # 新类型占位
    for t in rt:
        if t in ('image', 'emoji', 'sticker'):
            continue
        tokens.append(f'[{t}]')

    if not tokens and message_type and message_type not in ('text', 'unknown'):
        tokens.append(f'[{message_type}]')

    return ' '.join(tokens).strip()


def _resource_types_from_element_counts(element_counts: dict | None) -> list[str]:
    """从 element_counts 推断资源类型列表（用于旧分析器/前端占位符）。

    ElementType（来自 QQChatExporter V4）：
    - 2: 图片 -> image
    - 3: 文件 -> file
    - 4: 语音 -> audio
    - 5: 视频 -> video
    - 6/11: 表情 -> emoji/sticker（这里统一记为 emoji）
    """

    if not isinstance(element_counts, dict):
        return []

    def _n(k: int) -> int:
        try:
            return int(element_counts.get(k, 0) or 0)
        except Exception:
            return 0

    out: list[str] = []
    out += ['image'] * _n(2)
    out += ['file'] * _n(3)
    out += ['audio'] * _n(4)
    out += ['video'] * _n(5)
    # 这里不区分 sticker/emoji，保持简单
    out += ['emoji'] * (_n(6) + _n(11))
    return out


def load_conversation_and_messages(filename: str, *, options=None):
    """从 texts/ 加载归一化会话，并返回适配现有分析/AI 的消息字典列表。"""
    options = options or {}
    filepath = safe_texts_file_path(filename)
    if not filepath.exists():
        raise FileNotFoundError('文件不存在')

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

        # 系统类事件可能没有 sender，这里用兜底身份承载
        qq = m.sender_participant_id or 'system'
        sender = m.sender_name or pid_to_name.get(qq, qq) or ('系统' if qq == 'system' else qq)

        resource_types = _resource_types_from_element_counts(getattr(m, 'element_counts', None))

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

        content = m.text or ''
        if not content:
            content = legacy_placeholders_for_message(
                m.message_type,
                resource_types,
                is_recalled=bool(m.is_recalled),
            )

        messages.append({
            # legacy fields（现有分析器/AI/预览依赖）
            'time': time_str,
            'sender': sender,
            'qq': str(qq),
            'content': content,

            # structured meta
            'timestamp_ms': int(m.timestamp_ms or 0),
            'message_id': str(m.message_id) if m.message_id is not None else None,
            'is_system': bool(m.is_system),
            'is_recalled': bool(m.is_recalled),
            'message_type': str(m.message_type or 'unknown'),
            'resource_types': resource_types,
            'mention_count': int(len(mention_targets)),
            'mentions': mention_targets,
            'reply_to_message_id': reply_to_mid,
            'reply_to_qq': reply_to_qq,
        })

    return conv, messages, result.warnings
