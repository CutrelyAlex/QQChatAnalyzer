import logging
from pathlib import Path

from flask import Blueprint, jsonify, request


logger = logging.getLogger(__name__)
bp = Blueprint('analysis_cache', __name__)


@bp.route('/api/analysis/cache/list', methods=['GET'])
def list_analysis_cache():
    """T058: 列出所有已缓存的分析数据"""
    try:
        import pickle

        cache_dir = Path('exports/.analysis_cache')
        cache_dir.mkdir(parents=True, exist_ok=True)

        analysis_list = []
        for cache_file in cache_dir.glob('*.pkl'):
            try:
                with open(cache_file, 'rb') as f:
                    cache_data = pickle.load(f)

                analysis_type = cache_data.get('type', 'unknown')
                filename = cache_data.get('filename', 'unknown')
                created_at = cache_data.get('created_at', '')

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
                    'file_size': cache_file.stat().st_size,
                })
            except Exception as e:
                logger.error(f"Error reading cache file {cache_file}: {e}")
                continue

        return jsonify({'success': True, 'cache_list': sorted(analysis_list, key=lambda x: x['created_at'], reverse=True)})
    except Exception as e:
        logger.error(f"Error listing analysis cache: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/analysis/save', methods=['POST'])
def save_analysis():
    """T059: 保存分析数据到缓存"""
    try:
        import pickle
        import hashlib
        from datetime import datetime

        data = request.get_json()
        analysis_type = data.get('type', 'personal')
        filename = data.get('filename')
        analysis_data = data.get('data', {})

        if not filename:
            return jsonify({'success': False, 'error': '未指定文件名'}), 400

        cache_dir = Path('exports/.analysis_cache')
        cache_dir.mkdir(parents=True, exist_ok=True)

        cache_id_source = f"{analysis_type}_{filename}_{datetime.now().isoformat()}"
        cache_id = hashlib.md5(cache_id_source.encode()).hexdigest()[:8]

        cache_file = cache_dir / f"{cache_id}.pkl"

        cache_content = {
            'type': analysis_type,
            'filename': filename,
            'created_at': datetime.now().isoformat(),
            'data': analysis_data,
            'qq': data.get('qq'),
            'nickname': data.get('nickname'),
        }

        with open(cache_file, 'wb') as f:
            pickle.dump(cache_content, f)

        logger.info(f"Saved analysis cache: {cache_id}")

        return jsonify({'success': True, 'cache_id': cache_id, 'message': f'分析数据已保存，ID: {cache_id}'})
    except Exception as e:
        logger.error(f"Error saving analysis: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/analysis/load/<cache_id>', methods=['GET'])
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
            'nickname': cache_data.get('nickname'),
        })
    except Exception as e:
        logger.error(f"Error loading analysis: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/analysis/delete/<cache_id>', methods=['DELETE'])
def delete_analysis(cache_id):
    """T061: 删除缓存的分析数据"""
    try:
        cache_file = Path('exports/.analysis_cache') / f"{cache_id}.pkl"
        if not cache_file.exists():
            return jsonify({'success': False, 'error': '缓存不存在'}), 404

        cache_file.unlink()
        logger.info(f"Deleted analysis cache: {cache_id}")
        return jsonify({'success': True, 'message': '缓存已删除'})
    except Exception as e:
        logger.error(f"Error deleting analysis: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
