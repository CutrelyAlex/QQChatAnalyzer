import logging

from flask import Blueprint, jsonify, request

from src.compare import build_snapshot, diff_snapshots
from src.group_analyzer import GroupAnalyzer
from src.network_analyzer import NetworkAnalyzer
from src.web.services.conversation_loader import load_conversation_and_messages, parse_bool_query


logger = logging.getLogger(__name__)
bp = Blueprint('compare', __name__)


@bp.route('/api/compare', methods=['GET'])
def compare_files():
    """对比两段聊天（文件级别）。"""
    try:
        left_name = request.args.get('left')
        right_name = request.args.get('right')
        if not left_name or not right_name:
            return jsonify({'success': False, 'error': '缺少 left/right 参数'}), 400

        include_network = parse_bool_query(request.args.get('include_network'), default=True)
        max_nodes = request.args.get('max_nodes', type=int)
        max_edges = request.args.get('max_edges', type=int)
        limit_compute = parse_bool_query(request.args.get('limit_compute'), default=True)

        include_system = parse_bool_query(request.args.get('include_system'), default=True)
        include_recalled = parse_bool_query(request.args.get('include_recalled'), default=True)
        options = {'includeSystem': include_system, 'includeRecalled': include_recalled}

        conv_l, msgs_l, warn_l = load_conversation_and_messages(left_name, options=options)
        conv_r, msgs_r, warn_r = load_conversation_and_messages(right_name, options=options)

        g1 = GroupAnalyzer(); g1.load_messages(msgs_l); gs1 = g1.analyze().to_dict()
        g2 = GroupAnalyzer(); g2.load_messages(msgs_r); gs2 = g2.analyze().to_dict()

        ns1 = None
        ns2 = None
        if include_network:
            n1 = NetworkAnalyzer(max_nodes_for_viz=max_nodes, max_edges_for_viz=max_edges, limit_compute=limit_compute)
            n1.load_messages(msgs_l)
            ns1 = n1.analyze().to_dict()

            n2 = NetworkAnalyzer(max_nodes_for_viz=max_nodes, max_edges_for_viz=max_edges, limit_compute=limit_compute)
            n2.load_messages(msgs_r)
            ns2 = n2.analyze().to_dict()

        snap_l = build_snapshot(filename=left_name, conversation=conv_l, group_stats=gs1, network_stats=ns1)
        snap_r = build_snapshot(filename=right_name, conversation=conv_r, group_stats=gs2, network_stats=ns2)
        diff = diff_snapshots(snap_l, snap_r)

        return jsonify({
            'success': True,
            'left': snap_l.to_dict(),
            'right': snap_r.to_dict(),
            'diff': diff,
            'warnings': {'left': warn_l, 'right': warn_r},
        })
    except Exception as e:
        logger.error(f"Error in compare: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
