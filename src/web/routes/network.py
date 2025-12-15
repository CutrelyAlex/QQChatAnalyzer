import logging

from flask import jsonify, request

from src.network_analyzer import NetworkAnalyzer
from src.web.services.conversation_loader import load_conversation_and_messages, parse_bool_query


logger = logging.getLogger(__name__)
def get_network_analysis():
    """社交网络分析API - T036实现"""
    try:
        filename = request.args.get('file')
        max_nodes = request.args.get('max_nodes', type=int)
        max_edges = request.args.get('max_edges', type=int)
        limit_compute = request.args.get('limit_compute', '').strip() in ('1', 'true', 'True', 'yes', 'on')
        if not filename:
            return jsonify({'success': False, 'error': '未指定文件'}), 400
        logger.info(f"Analyzing network from {filename}")

        include_system = parse_bool_query(request.args.get('include_system'), default=True)
        include_recalled = parse_bool_query(request.args.get('include_recalled'), default=True)

        _conv, messages, _warnings = load_conversation_and_messages(
            filename,
            options={'includeSystem': include_system, 'includeRecalled': include_recalled},
        )

        analyzer = NetworkAnalyzer(
            max_nodes_for_viz=max_nodes,
            max_edges_for_viz=max_edges,
            limit_compute=limit_compute,
        )
        analyzer.load_messages(messages)
        stats = analyzer.analyze()

        return jsonify({'success': True, 'data': stats.to_dict()})
    except Exception as e:
        logger.error(f"Error in network analysis: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
