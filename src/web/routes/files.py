import logging
from datetime import datetime

from flask import jsonify, request

from src.config import Config
from src.web.services.conversation_loader import TEXTS_DIR, ALLOWED_SUFFIXES, safe_texts_file_path


logger = logging.getLogger(__name__)
def get_files():
    """获取可分析的文件列表（从texts/目录）"""
    try:
        TEXTS_DIR.mkdir(exist_ok=True)
        candidates = []
        for ext in ALLOWED_SUFFIXES:
            candidates.extend(TEXTS_DIR.glob(f'*{ext}'))

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

        files.sort(key=lambda x: x.get('modified', ''), reverse=True)

        return jsonify({'success': True, 'files': files, 'count': len(files)})
    except Exception as e:
        logger.error(f"Error getting files: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def load_file():
    """加载文件进行分析"""
    try:
        data = request.get_json()
        filename = data.get('filename')

        if not filename:
            return jsonify({'success': False, 'error': '未指定文件名'}), 400

        try:
            filepath = safe_texts_file_path(filename)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400

        if not filepath.exists():
            return jsonify({'success': False, 'error': '文件不存在'}), 404

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
