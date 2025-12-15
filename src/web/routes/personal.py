import logging

from flask import jsonify, request

from src.personal_analyzer import PersonalAnalyzer
from src.web.services.conversation_loader import load_conversation_and_messages


logger = logging.getLogger(__name__)
def get_personal_list(filename):
    """获取文件中所有用户列表"""
    try:
        conv, messages, _warnings = load_conversation_and_messages(filename)

        qq_to_names = {}
        for msg in (messages or []):
            qq = (msg.get('qq') or '').strip()
            sender = (msg.get('sender') or '').strip()
            if not qq or not sender:
                continue
            lst = qq_to_names.setdefault(qq, [])
            if not lst or lst[-1] != sender:
                lst.append(sender)

        users = []
        for p in (conv.participants or []):
            users.append({
                'id': p.participant_id,
                'qq': p.uin or '',
                'uid': p.uid or '',
                'name': (
                    (qq_to_names.get(p.uin or '', [])[-1] if (p.uin and qq_to_names.get(p.uin or '')) else '')
                    or p.display_name
                    or (p.uin or p.uid or p.participant_id)
                ),
                'names': qq_to_names.get(p.uin or '', []),
            })

        users.sort(key=lambda x: (x.get('name') or '', x.get('qq') or '', x.get('id') or ''))

        return jsonify({'success': True, 'users': users, 'count': len(users)})
    except Exception as e:
        logger.error(f"Error getting personal list: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def get_personal_analysis(qq):
    """个人分析API"""
    try:
        filename = request.args.get('file')
        if not filename:
            return jsonify({'success': False, 'error': '未指定文件'}), 400

        logger.info(f"Analyzing personal stats for {qq} from {filename}")

        _conv, messages, _warnings = load_conversation_and_messages(filename)

        analyzer = PersonalAnalyzer()
        stats = analyzer.get_user_stats_from_messages(messages, qq)

        if not stats:
            return jsonify({'success': False, 'error': f'未找到QQ {qq} 的数据'}), 404

        return jsonify({'success': True, 'data': stats.to_dict()})
    except Exception as e:
        logger.error(f"Error in personal analysis: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
