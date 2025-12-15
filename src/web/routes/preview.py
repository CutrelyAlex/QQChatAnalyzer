import logging

from flask import Blueprint, jsonify, request

from src.web.services.conversation_loader import load_conversation_and_messages


logger = logging.getLogger(__name__)
bp = Blueprint('preview', __name__)


@bp.route('/api/preview/<filename>', methods=['GET'])
def preview_chat_records(filename):
    """预览聊天记录"""
    try:
        try:
            _conv, messages, _warnings = load_conversation_and_messages(filename)
        except FileNotFoundError:
            return jsonify({'success': False, 'error': '文件不存在'}), 404

        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 50))
        filter_type = request.args.get('filter_type', 'all')
        filter_value = request.args.get('filter_value', '')

        records = []
        for msg in messages:
            timestamp = msg.get('time', '')
            sender = msg.get('sender', '')
            qq = msg.get('qq', '')
            content = msg.get('content', '')

            if filter_type == 'date':
                if filter_value and not str(timestamp).startswith(filter_value):
                    continue
            elif filter_type == 'qq':
                if filter_value and str(qq) != filter_value:
                    continue

            records.append({'timestamp': timestamp, 'sender': sender, 'qq': qq, 'content': (content or '')[:100]})

        total = len(records)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_records = records[start:end]

        return jsonify({
            'success': True,
            'records': paginated_records,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size,
        })
    except Exception as e:
        logger.error(f"Error previewing chat records: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/preview/<filename>/stats', methods=['GET'])
def preview_chat_stats(filename):
    """获取聊天记录统计信息（用于过滤器）"""
    try:
        try:
            _conv, messages, _warnings = load_conversation_and_messages(filename)
        except FileNotFoundError:
            return jsonify({'success': False, 'error': '文件不存在'}), 404

        dates = set()
        qqs = {}
        for msg in messages:
            timestamp = msg.get('time', '')
            sender = msg.get('sender', '')
            qq = msg.get('qq', '')

            if timestamp and ' ' in timestamp:
                date = timestamp.split(' ', 1)[0]
                dates.add(date)

            if qq:
                if sender:
                    qqs[qq] = sender
                elif qq not in qqs:
                    qqs[qq] = qq

        return jsonify({
            'success': True,
            'dates': sorted(list(dates)),
            'qqs': [{'qq': qq, 'sender': qqs[qq]} for qq in sorted(qqs.keys())],
        })
    except Exception as e:
        logger.error(f"Error getting chat stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
