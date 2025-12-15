import logging

from flask import Blueprint, jsonify

from src.config import Config


logger = logging.getLogger(__name__)
bp = Blueprint('system', __name__)


@bp.route('/api/system/info', methods=['GET'])
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
            'max_file_size_mb': Config.MAX_FILE_SIZE_MB,
        })
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
