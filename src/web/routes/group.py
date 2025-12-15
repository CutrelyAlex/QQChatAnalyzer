import logging

from flask import Blueprint, jsonify, request

from src.group_analyzer import GroupAnalyzer
from src.web.services.conversation_loader import load_conversation_and_messages, parse_bool_query


logger = logging.getLogger(__name__)
bp = Blueprint('group', __name__)


@bp.route('/api/group', methods=['GET'])
def get_group_analysis():
    """群体分析API - T027实现"""
    try:
        filename = request.args.get('file')
        if not filename:
            return jsonify({'success': False, 'error': '未指定文件'}), 400
        logger.info(f"Analyzing group stats from {filename}")

        include_system = parse_bool_query(request.args.get('include_system'), default=True)
        include_recalled = parse_bool_query(request.args.get('include_recalled'), default=True)

        _conv, messages, _warnings = load_conversation_and_messages(
            filename,
            options={'includeSystem': include_system, 'includeRecalled': include_recalled},
        )

        analyzer = GroupAnalyzer()
        analyzer.load_messages(messages)
        stats = analyzer.analyze()

        return jsonify({'success': True, 'data': stats.to_dict()})
    except Exception as e:
        logger.error(f"Error in group analysis: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
