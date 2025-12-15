import logging

from flask import jsonify, request

from src.utils import clean_message_content
from src.web.services.conversation_loader import load_conversation_and_messages, safe_texts_file_path


logger = logging.getLogger(__name__)


# 热词示例缓存
_CHAT_EXAMPLES_CACHE = {
    # filename: {"mtime": float, "records": [ {timestamp,sender,qq,clean_text}, ... ]}
}

_CHAT_EXAMPLES_CLEANER_VERSION = 4


def get_chat_examples():
    """获取包含某个热词的聊天记录示例（2-4条）"""
    try:
        word = request.args.get('word', '').strip()
        filename = request.args.get('file', '')
        qq = request.args.get('qq', '')

        try:
            limit = int(request.args.get('limit', 4) or 4)
        except Exception:
            limit = 4
        try:
            offset = int(request.args.get('offset', 0) or 0)
        except Exception:
            offset = 0

        limit = max(1, min(limit, 50))
        offset = max(0, offset)

        if not word or not filename:
            return jsonify({'success': False, 'error': '缺少必要参数'}), 400

        try:
            filepath = safe_texts_file_path(filename)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400

        if not filepath.exists():
            return jsonify({'success': False, 'error': '文件不存在'}), 404

        file_mtime = filepath.stat().st_mtime
        cached = _CHAT_EXAMPLES_CACHE.get(filename)
        if cached and cached.get('mtime') == file_mtime and cached.get('ver') == _CHAT_EXAMPLES_CLEANER_VERSION:
            records = cached.get('records', [])
        else:
            _conv, messages, _warnings = load_conversation_and_messages(filename)
            records = []
            for m in messages:
                content = m.get('content', '')
                records.append({
                    'timestamp': m.get('time', ''),
                    'sender': m.get('sender', ''),
                    'qq': m.get('qq', ''),
                    'clean_text': clean_message_content(content) if content else '',
                })
            _CHAT_EXAMPLES_CACHE[filename] = {'mtime': file_mtime, 'ver': _CHAT_EXAMPLES_CLEANER_VERSION, 'records': records}

        examples = []
        matched = 0
        has_more = False
        for rec in records:
            if qq and rec.get('qq') != qq:
                continue

            ct = rec.get('clean_text') or ''
            if not ct:
                continue

            if word in ct:
                if matched >= offset and len(examples) < limit:
                    examples.append({
                        'timestamp': rec.get('timestamp', ''),
                        'sender': rec.get('sender', ''),
                        'qq': rec.get('qq', ''),
                        'content': ct,
                    })
                matched += 1

                if len(examples) >= limit and matched > (offset + limit - 1):
                    has_more = True
                    break

        return jsonify({
            'success': True,
            'word': word,
            'examples': examples,
            'offset': offset,
            'limit': limit,
            'next_offset': offset + len(examples),
            'has_more': bool(has_more),
        })
    except Exception as e:
        logger.error(f"Error getting chat examples: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
