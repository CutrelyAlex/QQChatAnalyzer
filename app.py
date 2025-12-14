"""
Flask Web应用 - QQ聊天记录分析系统
支持个人分析、群体分析、社交网络分析、AI总结、报告导出
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# 立即加载 .env 文件
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS

# `src/` is a package; import analyzers via package path.
from src.config import Config
from src.personal_analyzer import PersonalAnalyzer
from src.group_analyzer import GroupAnalyzer
from src.network_analyzer import NetworkAnalyzer
from src.chat_import import load_chat_file
from src.compare import build_snapshot, diff_snapshots

# 热词示例缓存
_CHAT_EXAMPLES_CACHE = {
    # filename: {"mtime": float, "records": [ {timestamp,sender,qq,clean_text}, ... ]}
}

_CHAT_EXAMPLES_CLEANER_VERSION = 4

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建Flask应用
app = Flask(__name__, template_folder='templates', static_folder='static')

# CORS配置
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# 应用配置
app.config.from_object(Config)

# 创建必要的目录
Path('uploads').mkdir(exist_ok=True)
Path('exports').mkdir(exist_ok=True)

# texts 目录与允许的输入文件类型
_TEXTS_DIR = Path('texts')
_ALLOWED_SUFFIXES = {'.txt', '.json'}


def _safe_texts_file_path(filename: str) -> Path:
    """
    把用户输入的文件名映射到 texts/ 下
    仅允许 .txt/.json
    """
    if not filename or not isinstance(filename, str):
        raise ValueError('未指定文件名')

    texts_dir = _TEXTS_DIR.resolve()
    candidate = (_TEXTS_DIR / filename).resolve()

    if texts_dir not in candidate.parents and candidate != texts_dir:
        raise ValueError('非法文件路径')

    if candidate.suffix.lower() not in _ALLOWED_SUFFIXES:
        raise ValueError('不支持的文件类型')

    return candidate


def _format_time_from_ts_ms(ts_ms: int) -> str:
    """把 epoch ms 转为时间字符串。"""
    try:
        if not ts_ms:
            return ''
        return datetime.fromtimestamp(ts_ms / 1000).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return ''


def _parse_bool_query(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    s = str(value).strip().lower()
    if s in ('1', 'true', 'yes', 'on'):
        return True
    if s in ('0', 'false', 'no', 'off'):
        return False
    return default


def _legacy_placeholders_for_message(message_type: str, resource_types: list[str] | None, *, is_recalled: bool) -> str:
    """为旧分析器生成可读占位符。
    """

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


def _load_conversation_and_messages(filename: str, *, options=None):
    """从 texts/ 加载归一化会话，并返回适配现有分析/AI 的消息字典列表。"""
    options = options or {}
    filepath = _safe_texts_file_path(filename)
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
    for m in conv.messages:
        time_str = _format_time_from_ts_ms(m.timestamp_ms)

        # 系统类事件可能没有 sender，这里用兜底身份承载
        qq = m.sender_participant_id or 'system'
        sender = m.sender_name or pid_to_name.get(qq, qq) or ('系统' if qq == 'system' else qq)

        resource_types = [getattr(r, 'type', None) for r in (m.resources or [])]
        resource_types = [str(t) for t in resource_types if t]

        mention_targets = []
        for it in (m.mentions or []):
            try:
                pid = getattr(it, 'target_participant_id', None)
                name = getattr(it, 'target_name', None)
                mention_targets.append(pid or name)
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
            content = _legacy_placeholders_for_message(
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


# ============ 错误处理 ============

@app.errorhandler(400)
def bad_request(error):
    return jsonify({'error': '请求错误', 'message': str(error)}), 400


@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': '资源不存在', 'message': str(error)}), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': '服务器错误', 'message': '请稍后重试'}), 500


# ============ 首页路由 ============

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


# ============ 文件管理API ============

@app.route('/api/files', methods=['GET'])
def get_files():
    """获取可分析的文件列表（从texts/目录）"""
    try:
        # 获取 texts 目录下的所有可支持文件（.txt / .json）
        _TEXTS_DIR.mkdir(exist_ok=True)
        candidates = []
        for ext in _ALLOWED_SUFFIXES:
            candidates.extend(_TEXTS_DIR.glob(f'*{ext}'))

        files = []
        for f in candidates:
            try:
                st = f.stat()
                files.append({
                    'name': f.name,
                    'size': st.st_size,
                    'modified': datetime.fromtimestamp(st.st_mtime).isoformat(),
                    'ext': f.suffix.lower(),
                })
            except Exception:
                continue

        # 最近修改优先
        files.sort(key=lambda x: x.get('modified', ''), reverse=True)
        
        return jsonify({
            'success': True,
            'files': files,
            'count': len(files)
        })
    except Exception as e:
        logger.error(f"Error getting files: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/load', methods=['POST'])
def load_file():
    """加载文件进行分析"""
    try:
        data = request.get_json()
        filename = data.get('filename')
        
        if not filename:
            return jsonify({'success': False, 'error': '未指定文件名'}), 400
        
        try:
            filepath = _safe_texts_file_path(filename)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400

        # 只允许加载 texts 目录下的支持类型文件
        if not filepath.exists():
            return jsonify({'success': False, 'error': '文件不存在'}), 404
        
        # 检查文件大小
        file_size_mb = filepath.stat().st_size / (1024 * 1024)
        if file_size_mb > Config.MAX_FILE_SIZE_MB:
            return jsonify({
                'success': False,
                'error': f'文件过大 ({file_size_mb:.2f}MB > {Config.MAX_FILE_SIZE_MB}MB)'
            }), 413
        
        logger.info(f"Loading file: {filename}")
        
        return jsonify({
            'success': True,
            'message': f'文件 {filename} 已加载',
            'filename': filename,
            'ext': filepath.suffix.lower(),
            'size_mb': round(file_size_mb, 2)
        })
    except Exception as e:
        logger.error(f"Error loading file: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ 个人分析API ============

@app.route('/api/personal/list/<filename>', methods=['GET'])
def get_personal_list(filename):
    """获取文件中所有用户列表"""
    try:
        conv, _messages, _warnings = _load_conversation_and_messages(filename)

        users = []
        for p in (conv.participants or []):
            # 说明：
            # - id: internal participant_id（分析与接口调用使用；可能是 uid:... 或 uin:...）
            # - qq: QQ号（uin，纯数字字符串；可能为空）
            # - uid: exporter uid（可能为空）
            users.append({
                'id': p.participant_id,
                'qq': p.uin or '',
                'uid': p.uid or '',
                'name': p.display_name or (p.uin or p.uid or p.participant_id),
            })

        users.sort(key=lambda x: (x.get('name') or '', x.get('qq') or '', x.get('id') or ''))
        
        return jsonify({
            'success': True,
            'users': users,
            'count': len(users)
        })
    except Exception as e:
        logger.error(f"Error getting personal list: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/personal/<qq>', methods=['GET'])
def get_personal_analysis(qq):
    """个人分析API"""
    try:
        filename = request.args.get('file')
        if not filename:
            return jsonify({'success': False, 'error': '未指定文件'}), 400

        logger.info(f"Analyzing personal stats for {qq} from {filename}")

        conv, messages, _warnings = _load_conversation_and_messages(filename)

        # 执行分析（走消息列表入口，避免 .txt/.json 两套解析）
        analyzer = PersonalAnalyzer()
        stats = analyzer.get_user_stats_from_messages(messages, qq)
        
        if not stats:
            return jsonify({
                'success': False,
                'error': f'未找到QQ {qq} 的数据'
            }), 404
        
        return jsonify({
            'success': True,
            'data': stats.to_dict()
        })
    except Exception as e:
        logger.error(f"Error in personal analysis: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/group', methods=['GET'])
def get_group_analysis():
    """群体分析API - T027实现"""
    try:
        filename = request.args.get('file')
        if not filename:
            return jsonify({'success': False, 'error': '未指定文件'}), 400
        logger.info(f"Analyzing group stats from {filename}")

        include_system = _parse_bool_query(request.args.get('include_system'), default=True)
        include_recalled = _parse_bool_query(request.args.get('include_recalled'), default=True)

        _conv, messages, _warnings = _load_conversation_and_messages(
            filename,
            options={
                'includeSystem': include_system,
                'includeRecalled': include_recalled,
            },
        )

        analyzer = GroupAnalyzer()
        analyzer.load_messages(messages)
        stats = analyzer.analyze()
        
        return jsonify({
            'success': True,
            'data': stats.to_dict()
        })
    except Exception as e:
        logger.error(f"Error in group analysis: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network', methods=['GET'])
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

        include_system = _parse_bool_query(request.args.get('include_system'), default=True)
        include_recalled = _parse_bool_query(request.args.get('include_recalled'), default=True)

        _conv, messages, _warnings = _load_conversation_and_messages(
            filename,
            options={
                'includeSystem': include_system,
                'includeRecalled': include_recalled,
            },
        )

        # 执行网络分析（允许用前端 slider 覆盖默认上限）
        analyzer = NetworkAnalyzer(
            max_nodes_for_viz=max_nodes,
            max_edges_for_viz=max_edges,
            limit_compute=limit_compute
        )
        analyzer.load_messages(messages)
        stats = analyzer.analyze()
        
        return jsonify({
            'success': True,
            'data': stats.to_dict()
        })
    except Exception as e:
        logger.error(f"Error in network analysis: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ 对比分析API ============


@app.route('/api/compare', methods=['GET'])
def compare_files():
    """对比两段聊天（文件级别）。

    Query:
      - left/right: 两个 texts/ 下的文件名（.txt 或 .json）
      - include_network: 是否计算网络摘要（默认 true）
      - max_nodes/max_edges/limit_compute: 传递给 NetworkAnalyzer 的参数
    """
    try:
        left_name = request.args.get('left')
        right_name = request.args.get('right')
        if not left_name or not right_name:
            return jsonify({'success': False, 'error': '缺少 left/right 参数'}), 400

        include_network = _parse_bool_query(request.args.get('include_network'), default=True)

        max_nodes = request.args.get('max_nodes', type=int)
        max_edges = request.args.get('max_edges', type=int)
        limit_compute = _parse_bool_query(request.args.get('limit_compute'), default=True)

        # 使用相同的导入过滤规则（默认包含系统/撤回；热词在 analyzer 内默认排除）
        include_system = _parse_bool_query(request.args.get('include_system'), default=True)
        include_recalled = _parse_bool_query(request.args.get('include_recalled'), default=True)
        options = {'includeSystem': include_system, 'includeRecalled': include_recalled}

        conv_l, msgs_l, warn_l = _load_conversation_and_messages(left_name, options=options)
        conv_r, msgs_r, warn_r = _load_conversation_and_messages(right_name, options=options)

        # Group
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
            'warnings': {
                'left': warn_l,
                'right': warn_r,
            }
        })

    except Exception as e:
        logger.error(f"Error in compare: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ Token管理API (T044-T045) ============

@app.route('/api/ai/status', methods=['GET'])
def ai_status():
    """T044: 检查AI服务状态"""
    try:
        api_key = Config.OPENAI_API_KEY
        is_available = bool(api_key)
        
        return jsonify({
            'success': True,
            'available': is_available,
            'model': Config.OPENAI_MODEL,
            'apiBase': Config.OPENAI_API_BASE or 'https://api.openai.com/v1',
            'message': 'AI服务可用' if is_available else 'AI服务未配置，请设置 OPENAI_API_KEY 环境变量'
        })
    except Exception as e:
        logger.error(f"Error checking AI status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/test-ai-connection', methods=['POST'])
def test_ai_connection():
    """测试AI连接配置"""
    try:
        data = request.get_json()
        api_base = data.get('api_base', '')
        api_key = data.get('api_key', '')
        model = data.get('model', 'gpt-4o-mini')
        timeout = data.get('timeout', 30)
        
        if not api_key or not api_base:
            return jsonify({
                'success': False,
                'error': '请提供API密钥和基础URL'
            }), 400
        
        try:
            from openai import OpenAI
            
            # 创建自定义客户端进行测试
            client = OpenAI(
                api_key=api_key,
                base_url=api_base
            )
            
            # 发送一个简单的测试请求
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": "ping"}
                ],
                max_tokens=5,
                timeout=timeout
            )
            
            return jsonify({
                'success': True,
                'message': '连接成功',
                'model': model,
                'base_url': api_base
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'连接失败: {str(e)}'
            }), 400
    except Exception as e:
        logger.error(f"Error testing AI connection: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/token-estimate', methods=['POST'])
def token_estimate():
    """T045: Token预估API"""
    try:
        data = request.get_json()
        filename = data.get('filename')
        max_tokens = data.get('max_tokens', Config.DEFAULT_MAX_TOKENS)
        
        if not filename:
            return jsonify({'success': False, 'error': '未指定文件'}), 400
        
        try:
            _conv, messages, _warnings = _load_conversation_and_messages(filename)
        except FileNotFoundError:
            return jsonify({'success': False, 'error': '文件不存在'}), 404

        from src.data_pruner import DataPruner

        pruner = DataPruner(max_tokens)
        pruner.load_messages(messages)
        
        # 获取 Token 估算结果
        estimate = pruner.estimate_tokens()
        
        # 获取修剪策略
        strategy = pruner.calculate_pruning_strategy()
        
        return jsonify({
            'success': True,
            'estimate': estimate,
            'pruning_strategy': strategy
        })
    except Exception as e:
        logger.error(f"Error estimating tokens: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ 分析缓存管理API ============

@app.route('/api/analysis/cache/list', methods=['GET'])
def list_analysis_cache():
    """T058: 列出所有已缓存的分析数据"""
    try:
        import pickle
        cache_dir = Path('exports/.analysis_cache')
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        analysis_list = []
        
        # 遍历所有缓存文件
        for cache_file in cache_dir.glob('*.pkl'):
            try:
                with open(cache_file, 'rb') as f:
                    cache_data = pickle.load(f)
                
                # 提取缓存元数据
                analysis_type = cache_data.get('type', 'unknown')
                filename = cache_data.get('filename', 'unknown')
                created_at = cache_data.get('created_at', '')
                
                # 根据类型生成显示名称
                if analysis_type == 'personal':
                    display_name = f"{filename} - {cache_data.get('qq', '?')} ({cache_data.get('nickname', '未知')})"
                elif analysis_type == 'group':
                    display_name = f"{filename} (群体+网络分析)"
                else:
                    display_name = f"{filename} ({analysis_type}分析)"
                
                analysis_list.append({
                    'id': cache_file.stem,
                    'type': analysis_type,
                    'filename': filename,
                    'display_name': display_name,
                    'qq': cache_data.get('qq'),
                    'nickname': cache_data.get('nickname'),
                    'created_at': created_at,
                    'file_size': cache_file.stat().st_size
                })
            except Exception as e:
                logger.error(f"Error reading cache file {cache_file}: {e}")
                continue
        
        return jsonify({
            'success': True,
            'cache_list': sorted(analysis_list, key=lambda x: x['created_at'], reverse=True)
        })
    except Exception as e:
        logger.error(f"Error listing analysis cache: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analysis/save', methods=['POST'])
def save_analysis():
    """T059: 保存分析数据到缓存"""
    try:
        import pickle
        import hashlib
        from datetime import datetime
        import re
        
        data = request.get_json()
        analysis_type = data.get('type', 'personal')  # personal, group, network
        filename = data.get('filename')
        analysis_data = data.get('data', {})
        
        if not filename:
            return jsonify({'success': False, 'error': '未指定文件名'}), 400
        
        # 创建缓存目录
        cache_dir = Path('exports/.analysis_cache')
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成唯一的缓存ID
        cache_id_source = f"{analysis_type}_{filename}_{datetime.now().isoformat()}"
        cache_id = hashlib.md5(cache_id_source.encode()).hexdigest()[:8]
        
        # 保存缓存
        cache_file = cache_dir / f"{cache_id}.pkl"
        
        cache_content = {
            'type': analysis_type,
            'filename': filename,
            'created_at': datetime.now().isoformat(),
            'data': analysis_data,
            'qq': data.get('qq'),  # 个人分析时的QQ
            'nickname': data.get('nickname')  # 个人分析时的昵称
        }
        
        with open(cache_file, 'wb') as f:
            pickle.dump(cache_content, f)
        
        logger.info(f"Saved analysis cache: {cache_id}")
        
        return jsonify({
            'success': True,
            'cache_id': cache_id,
            'message': f'分析数据已保存，ID: {cache_id}'
        })
    except Exception as e:
        logger.error(f"Error saving analysis: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analysis/load/<cache_id>', methods=['GET'])
def load_analysis(cache_id):
    """T060: 从缓存加载分析数据"""
    try:
        import pickle
        
        cache_file = Path('exports/.analysis_cache') / f"{cache_id}.pkl"
        
        if not cache_file.exists():
            return jsonify({'success': False, 'error': '缓存不存在'}), 404
        
        with open(cache_file, 'rb') as f:
            cache_data = pickle.load(f)
        
        return jsonify({
            'success': True,
            'type': cache_data.get('type'),
            'filename': cache_data.get('filename'),
            'data': cache_data.get('data'),
            'qq': cache_data.get('qq'),
            'nickname': cache_data.get('nickname')
        })
    except Exception as e:
        logger.error(f"Error loading analysis: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analysis/delete/<cache_id>', methods=['DELETE'])
def delete_analysis(cache_id):
    """T061: 删除缓存的分析数据"""
    try:
        cache_file = Path('exports/.analysis_cache') / f"{cache_id}.pkl"
        
        if not cache_file.exists():
            return jsonify({'success': False, 'error': '缓存不存在'}), 404
        
        cache_file.unlink()
        logger.info(f"Deleted analysis cache: {cache_id}")
        
        return jsonify({
            'success': True,
            'message': '缓存已删除'
        })
    except Exception as e:
        logger.error(f"Error deleting analysis: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/summary', methods=['POST'])
def generate_summary():
    """T056: 生成AI总结 - 支持从缓存数据或实时分析"""
    try:
        import pickle
        
        data = request.get_json()
        summary_type = data.get('type', 'personal')  # personal, group, network
        cache_id = data.get('cache_id')  # 如果提供，使用缓存数据
        filename = data.get('filename')
        # max_tokens 控制输出长度
        max_tokens = data.get('max_tokens', Config.DEFAULT_OUTPUT_TOKENS)
        # context_budget 控制输入聊天记录的Token预算，用于稀疏采样
        context_budget = data.get('context_budget', Config.DEFAULT_CONTEXT_BUDGET)
        
        # 检查是否使用缓存数据
        analysis_data = None
        if cache_id:
            try:
                cache_file = Path('exports/.analysis_cache') / f"{cache_id}.pkl"
                if cache_file.exists():
                    with open(cache_file, 'rb') as f:
                        cache_content = pickle.load(f)
                    analysis_data = cache_content.get('data')
                    filename = cache_content.get('filename')
                    summary_type = cache_content.get('type', summary_type)
                    logger.info(f"Using cached analysis data: {cache_id}")
            except Exception as e:
                logger.warning(f"Failed to load cache {cache_id}: {e}")
                # 继续使用实时分析
        
        if not filename:
            return jsonify({'success': False, 'error': '未指定文件'}), 400

        filepath = None
        try:
            filepath = _safe_texts_file_path(filename)
        except Exception as e:
            # 若来自缓存且文件名非法，仍然无法加载消息样本
            if not analysis_data:
                return jsonify({'success': False, 'error': str(e)}), 400

        if filepath is not None and (not filepath.exists()) and not analysis_data:
            return jsonify({'success': False, 'error': '文件不存在'}), 404
        
        if not Config.OPENAI_API_KEY:
            return jsonify({
                'success': False,
                'error': 'AI服务未配置，请设置 OPENAI_API_KEY 环境变量'
            }), 503
        
        logger.info(f"Generating {summary_type} AI summary for {filename} (max_tokens={max_tokens}, context_budget={context_budget})")
        
        # 导入 AI Summarizer
        from src.ai_summarizer import AISummarizer
        
        # 使用环境变量配置，传入用户指定的context_budget
        summarizer = AISummarizer(
            model=Config.OPENAI_MODEL,
            max_tokens=max_tokens,
            api_key=Config.OPENAI_API_KEY,
            base_url=Config.OPENAI_API_BASE,
            context_budget=context_budget,
            timeout=int(Config.OPENAI_REQUEST_TIMEOUT)
        )
        
        if not summarizer.is_available():
            return jsonify({
                'success': False,
                'error': 'AI服务未配置，请设置 OPENAI_API_KEY 环境变量'
            }), 503
        
        # 如果有缓存的分析数据，仍从原文件读取消息列表以生成 chat_sample
        if analysis_data:
            cache_messages = []
            if filepath is not None and filepath.exists():
                _conv, cache_messages, _warnings = _load_conversation_and_messages(filename)

            if summary_type == 'personal':
                result = summarizer.generate_personal_summary(
                    analysis_data.get('stats', {}),
                    messages=cache_messages
                )
            else:
                result = summarizer.generate_group_summary(
                    group_stats=analysis_data.get('group_stats', {}),
                    messages=cache_messages,
                    network_stats=analysis_data.get('network_stats')
                )
            return jsonify(result)

        # 实时分析模式：统一从导入层加载消息
        if filepath is None or not filepath.exists():
            return jsonify({'success': False, 'error': '文件不存在'}), 404

        _conv, messages, _warnings = _load_conversation_and_messages(filename)
    
        
        result = None
        
        if summary_type == 'personal':
            # 获取个人统计
            qq = data.get('qq')
            if not qq:
                return jsonify({'success': False, 'error': '个人总结需要指定成员（QQ号/昵称）'}), 400
            
            analyzer = PersonalAnalyzer()
            stats = analyzer.get_user_stats_from_messages(messages, qq)
            if not stats:
                return jsonify({'success': False, 'error': f'未找到账号 {qq} 的数据'}), 404
            
            # 传递完整消息列表，由summarizer内部进行智能稀疏采样
            result = summarizer.generate_personal_summary(stats.to_dict(), messages=messages)
            
        elif summary_type in ('group', 'network'):
            # 合并处理：同时获取群体统计和网络统计
            # 群体分析
            group_analyzer = GroupAnalyzer()
            group_analyzer.load_messages(messages)
            group_stats = group_analyzer.analyze()
            
            # 网络分析
            network_analyzer = NetworkAnalyzer()
            network_analyzer.load_messages(messages)
            network_stats = network_analyzer.analyze()
            
            # 合并传递给summarizer进行群体+网络融合总结
            result = summarizer.generate_group_summary(
                group_stats=group_stats.to_dict(),
                messages=messages,
                network_stats=network_stats.to_dict()
            )
        else:
            return jsonify({'success': False, 'error': f'未知的总结类型: {summary_type}'}), 400
        
        return jsonify({
            'success': result.get('success', False),
            'summary': result.get('summary', ''),
            'tokens_used': result.get('tokens_used', 0),
            'model': result.get('model', ''),
            'error': result.get('error', '')
        })
        
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/summary/stream', methods=['POST'])
def generate_summary_stream():
    """T056b: 流式生成AI总结 - 支持从缓存数据或实时分析"""
    from flask import Response, stream_with_context
    import pickle
    
    try:
        data = request.get_json()
        summary_type = data.get('type', 'personal')
        cache_id = data.get('cache_id')  # 如果提供，使用缓存数据
        group_cache_id = data.get('group_cache_id')  # 群体分析缓存ID
        network_cache_id = data.get('network_cache_id')  # 网络分析缓存ID
        filename = data.get('filename')
        max_tokens = data.get('max_tokens', Config.DEFAULT_OUTPUT_TOKENS)
        context_budget = data.get('context_budget', Config.DEFAULT_CONTEXT_BUDGET)
        
        # 检查是否使用缓存数据
        cached_data = None
        
        # 处理合并缓存模式：同时使用群体分析和网络分析缓存
        if group_cache_id and network_cache_id:
            try:
                group_cache_file = Path('exports/.analysis_cache') / f"{group_cache_id}.pkl"
                network_cache_file = Path('exports/.analysis_cache') / f"{network_cache_id}.pkl"
                
                if group_cache_file.exists() and network_cache_file.exists():
                    with open(group_cache_file, 'rb') as f:
                        group_cache_content = pickle.load(f)
                    with open(network_cache_file, 'rb') as f:
                        network_cache_content = pickle.load(f)
                    
                    group_data = group_cache_content.get('data', {})
                    network_data = network_cache_content.get('data', {})
                    
                    # 合并数据
                    cached_data = {
                        'group_stats': group_data.get('group_stats', {}),
                        'network_stats': network_data.get('network_stats', {}),
                        # 优先使用较长的聊天样本
                        'chat_sample': group_data.get('chat_sample', '') if len(group_data.get('chat_sample', '')) >= len(network_data.get('chat_sample', '')) else network_data.get('chat_sample', '')
                    }
                    
                    filename = group_cache_content.get('filename')
                    summary_type = 'group_and_network'  # 强制设为合并类型
                    logger.info(f"Using merged cache data: group={group_cache_id}, network={network_cache_id}")
                else:
                    return jsonify({'success': False, 'error': '缓存文件不存在'}), 404
            except Exception as e:
                logger.warning(f"Failed to load merged cache: {e}")
                return jsonify({'success': False, 'error': f'加载合并缓存失败: {e}'}), 500
        elif cache_id:
            try:
                cache_file = Path('exports/.analysis_cache') / f"{cache_id}.pkl"
                if cache_file.exists():
                    with open(cache_file, 'rb') as f:
                        cache_content = pickle.load(f)
                    cached_data = cache_content.get('data')
                    filename = cache_content.get('filename')
                    summary_type = cache_content.get('type', summary_type)
                    logger.info(f"Using cached analysis data: {cache_id}")
            except Exception as e:
                logger.warning(f"Failed to load cache {cache_id}: {e}")
        
        if not filename and not cached_data:
            return jsonify({'success': False, 'error': '未指定文件或缓存'}), 400

        filepath = None
        if filename:
            try:
                filepath = _safe_texts_file_path(filename)
            except Exception as e:
                if not cached_data:
                    return jsonify({'success': False, 'error': str(e)}), 400

        if filepath and not filepath.exists() and not cached_data:
            return jsonify({'success': False, 'error': '文件不存在'}), 404
        
        if not Config.OPENAI_API_KEY:
            return jsonify({'success': False, 'error': 'AI服务未配置'}), 503
        
        from src.ai_summarizer import AISummarizer
        summarizer = AISummarizer(model=Config.OPENAI_MODEL, max_tokens=max_tokens, api_key=Config.OPENAI_API_KEY, base_url=Config.OPENAI_API_BASE, context_budget=context_budget, timeout=int(Config.OPENAI_REQUEST_TIMEOUT))
        
        if not summarizer.is_available():
            return jsonify({'success': False, 'error': 'AI服务未配置'}), 503
        
        def generate():
            try:
                # 如果有缓存数据，需要重新从原文件读取聊天记录生成 chat_sample
                chat_sample = ""
                if cached_data and filepath and filepath.exists():
                    _conv, cache_messages, _warnings = _load_conversation_and_messages(filename)

                    if summary_type == 'personal':
                        target_qq = cached_data.get('stats', {}).get('qq', '')
                        chat_sample = summarizer._sparse_sample_messages(cache_messages, target_qq)
                    else:
                        chat_sample = summarizer._sparse_sample_messages(cache_messages)
                    
                    logger.info(f"Generated chat_sample from file: {len(chat_sample)} chars")
                
                if cached_data:
                    logger.info(f"Generating from cached data, type={summary_type}")
                    
                    if summary_type == 'personal':
                        stats = cached_data.get('stats', {})
                        prompt = summarizer._build_personal_prompt(stats, chat_sample)
                        system_prompt = summarizer._get_system_prompt('personal')
                    else:
                        group_stats = cached_data.get('group_stats', {})
                        network_stats = cached_data.get('network_stats', {})
                        prompt = summarizer._build_group_and_network_prompt(
                            group_stats, network_stats, chat_sample
                        )
                        system_prompt = summarizer._get_system_prompt('group_and_network')
                else:
                    if not filepath or not filepath.exists():
                        yield f"data: {json.dumps({'type': 'error', 'message': '文件不存在'})}\n\n"
                        return

                    _conv, messages, _warnings = _load_conversation_and_messages(filename)
                    
                    if summary_type == 'personal':
                        qq = data.get('qq')
                        if not qq:
                            yield f"data: {json.dumps({'type': 'error', 'message': '个人总结需要指定成员（QQ号/昵称）'})}\n\n"
                            return
                        analyzer = PersonalAnalyzer()
                        stats = analyzer.get_user_stats_from_messages(messages, qq)
                        if not stats:
                            yield f"data: {json.dumps({'type': 'error', 'message': f'未找到账号 {qq} 的数据'})}\n\n"
                            return
                        # 使用稀疏采样生成聊天记录样本
                        chat_sample = summarizer._sparse_sample_messages(messages, qq)
                        prompt = summarizer._build_personal_prompt(stats.to_dict(), chat_sample)
                        system_prompt = summarizer._get_system_prompt('personal')
                    else:
                        group_analyzer = GroupAnalyzer()
                        group_analyzer.load_messages(messages)
                        group_stats = group_analyzer.analyze()
                        
                        network_analyzer = NetworkAnalyzer()
                        network_analyzer.load_messages(messages)
                        network_stats = network_analyzer.analyze()
                        
                        # 使用稀疏采样生成聊天记录样本
                        chat_sample = summarizer._sparse_sample_messages(messages)
                        prompt = summarizer._build_group_and_network_prompt(
                            group_stats.to_dict(), network_stats.to_dict(), chat_sample
                        )
                        system_prompt = summarizer._get_system_prompt('group_and_network')
                
                # 发送开始事件
                yield f"data: {json.dumps({'type': 'start', 'model': Config.OPENAI_MODEL})}\n\n"
                
                # 流式调用OpenAI
                stream = summarizer.client.chat.completions.create(
                    model=Config.OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=max_tokens,
                    temperature=0.8,
                    stream=True
                )
                
                total_content = ""
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        total_content += content
                        yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"
                
                # 发送完成事件
                yield f"data: {json.dumps({'type': 'done', 'total_length': len(total_content)})}\n\n"
                
            except Exception as e:
                logger.error(f"Stream error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )
        
    except Exception as e:
        logger.error(f"Error in stream setup: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ 聊天记录预览API ============

@app.route('/api/preview/<filename>', methods=['GET'])
def preview_chat_records(filename):
    """预览聊天记录"""
    try:
        try:
            _conv, messages, _warnings = _load_conversation_and_messages(filename)
        except FileNotFoundError:
            return jsonify({'success': False, 'error': '文件不存在'}), 404
        
        # 获取分页参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 50))
        filter_type = request.args.get('filter_type', 'all')  # all, date, qq
        filter_value = request.args.get('filter_value', '')
        
        records = []
        for msg in messages:
            timestamp = msg.get('time', '')
            sender = msg.get('sender', '')
            qq = msg.get('qq', '')
            content = msg.get('content', '')

            # 应用过滤
            if filter_type == 'date':
                if filter_value and not str(timestamp).startswith(filter_value):
                    continue
            elif filter_type == 'qq':
                if filter_value and str(qq) != filter_value:
                    continue

            records.append({
                'timestamp': timestamp,
                'sender': sender,
                'qq': qq,
                'content': (content or '')[:100]
            })
        
        # 分页
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
            'total_pages': (total + page_size - 1) // page_size
        })
    except Exception as e:
        logger.error(f"Error previewing chat records: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/preview/<filename>/stats', methods=['GET'])
def preview_chat_stats(filename):
    """获取聊天记录统计信息（用于过滤器）"""
    try:
        try:
            _conv, messages, _warnings = _load_conversation_and_messages(filename)
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

            if qq and qq not in qqs:
                qqs[qq] = sender
        
        return jsonify({
            'success': True,
            'dates': sorted(list(dates)),
            'qqs': [{'qq': qq, 'sender': qqs[qq]} for qq in sorted(qqs.keys())]
        })
    except Exception as e:
        logger.error(f"Error getting chat stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ 导出API（预留接口）============

@app.route('/api/export/<format_type>', methods=['POST'])
def export_report(format_type):
    """导出报告 - 预留"""
    try:
        if format_type not in ['html', 'pdf']:
            return jsonify({'success': False, 'error': '不支持的导出格式'}), 400
        
        return jsonify({
            'success': True,
            'message': f'{format_type.upper()}导出功能开发中...',
            'format': format_type
        })
    except Exception as e:
        logger.error(f"Error exporting report: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ 热词示例API ============

@app.route('/api/chat-examples', methods=['GET'])
def get_chat_examples():
    """获取包含某个热词的聊天记录示例（2-4条）"""
    try:
        word = request.args.get('word', '').strip()
        filename = request.args.get('file', '')
        qq = request.args.get('qq', '')  # 可选：个人分析时传入

        # 分页
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
            filepath = _safe_texts_file_path(filename)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400

        if not filepath.exists():
            return jsonify({'success': False, 'error': '文件不存在'}), 404

        from src.utils import clean_message_content

        # 优先走缓存（按文件 mtime 自动失效）
        file_mtime = filepath.stat().st_mtime
        cached = _CHAT_EXAMPLES_CACHE.get(filename)
        if cached and cached.get('mtime') == file_mtime and cached.get('ver') == _CHAT_EXAMPLES_CLEANER_VERSION:
            records = cached.get('records', [])
        else:
            _conv, messages, _warnings = _load_conversation_and_messages(filename)
            records = []
            for m in messages:
                content = m.get('content', '')
                records.append({
                    'timestamp': m.get('time', ''),
                    'sender': m.get('sender', ''),
                    'qq': m.get('qq', ''),
                    'clean_text': clean_message_content(content) if content else ''
                })
            _CHAT_EXAMPLES_CACHE[filename] = {'mtime': file_mtime, 'ver': _CHAT_EXAMPLES_CLEANER_VERSION, 'records': records}
        
        # 过滤包含热词的消息
        examples = []
        matched = 0
        has_more = False
        for rec in records:
            # 如果指定了QQ，则只查找该QQ的消息
            if qq and rec.get('qq') != qq:
                continue

            ct = rec.get('clean_text') or ''
            if not ct:
                continue

            # 在清理后的文本中查找热词
            if word in ct:
                if matched >= offset and len(examples) < limit:
                    examples.append({
                        'timestamp': rec.get('timestamp', ''),
                        'sender': rec.get('sender', ''),
                        'qq': rec.get('qq', ''),
                        'content': ct  # 显示清理后的文本
                    })
                matched += 1

                # 已拿满本页后，继续往后探测是否还有更多
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
            'has_more': bool(has_more)
        })
    except Exception as e:
        logger.error(f"Error getting chat examples: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ 系统信息API ============

@app.route('/api/system/info', methods=['GET'])
def system_info():
    """获取系统信息"""
    try:
        return jsonify({
            'success': True,
            'app_name': '聊天记录分析系统',
            'version': '1.0.0',
            'flask_host': Config.HOST,
            'flask_port': Config.PORT,
            'ai_available': bool(Config.OPENAI_API_KEY),
            'max_file_size_mb': Config.MAX_FILE_SIZE_MB
        })
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ 启动应用 ============

if __name__ == '__main__':
    # 打印配置状态
    Config.print_config_status()
    
    logger.info(f"Starting Flask app on {Config.HOST}:{Config.PORT}")
    
    # 启动应用
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG,
        use_reloader=False
    )
