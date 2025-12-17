"""
Flask Web应用 - QQ聊天记录分析系统
支持个人分析、群体分析、社交网络分析、AI总结、报告导出
"""

import logging
from pathlib import Path

# 立即加载 .env 文件
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify
from flask_cors import CORS
from src.config import Config

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
Path('exports').mkdir(exist_ok=True)

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


@app.route('/favicon.ico')
def favicon():
    return ('', 204)

@app.route('/')
def index():
    """主页"""
    from src.web.routes.home import index as impl
    return impl()


# ============ 文件管理API ============

@app.route('/api/files', methods=['GET'])
def get_files():
    """获取可分析的文件列表（从texts/目录）"""
    from src.web.routes.files import get_files as impl
    return impl()


@app.route('/api/load', methods=['POST'])
def load_file():
    """加载文件进行分析"""
    from src.web.routes.files import load_file as impl
    return impl()


# ============ 个人分析API ============

@app.route('/api/personal/list/<filename>', methods=['GET'])
def get_personal_list(filename):
    """获取文件中所有用户列表"""
    from src.web.routes.personal import get_personal_list as impl
    return impl(filename)


@app.route('/api/personal/<qq>', methods=['GET'])
def get_personal_analysis(qq):
    """个人分析API"""
    from src.web.routes.personal import get_personal_analysis as impl
    return impl(qq)


@app.route('/api/group', methods=['GET'])
def get_group_analysis():
    """群体分析API - T027实现"""
    from src.web.routes.group import get_group_analysis as impl
    return impl()


@app.route('/api/network', methods=['GET'])
def get_network_analysis():
    """社交网络分析API - T036实现"""
    from src.web.routes.network import get_network_analysis as impl
    return impl()


# ============ 对比分析API ============


@app.route('/api/compare', methods=['GET'])
def compare_files():
    """对比两段聊天（文件级别）。

    Query:
      - left/right: 两个 texts/ 下的文件名（.txt 或 .json）
      - include_network: 是否计算网络摘要（默认 true）
      - max_nodes/max_edges/limit_compute: 传递给 NetworkAnalyzer 的参数
    """
    from src.web.routes.compare import compare_files as impl
    return impl()


# ============ Token管理API (T044-T045) ============

@app.route('/api/ai/status', methods=['GET'])
def ai_status():
    """T044: 检查AI服务状态"""
    from src.web.routes.ai import ai_status as impl
    return impl()


@app.route('/api/test-ai-connection', methods=['POST'])
def test_ai_connection():
    """测试AI连接配置"""
    from src.web.routes.ai import test_ai_connection as impl
    return impl()


@app.route('/api/ai/token-estimate', methods=['POST'])
def token_estimate():
    """T045: Token预估API"""
    from src.web.routes.ai import token_estimate as impl
    return impl()

# ============ 分析缓存管理API ============

@app.route('/api/analysis/cache/list', methods=['GET'])
def list_analysis_cache():
    """T058: 列出所有已缓存的分析数据"""
    from src.web.routes.analysis_cache import list_analysis_cache as impl
    return impl()


@app.route('/api/analysis/save', methods=['POST'])
def save_analysis():
    """T059: 保存分析数据到缓存"""
    from src.web.routes.analysis_cache import save_analysis as impl
    return impl()


@app.route('/api/analysis/load/<cache_id>', methods=['GET'])
def load_analysis(cache_id):
    """T060: 从缓存加载分析数据"""
    from src.web.routes.analysis_cache import load_analysis as impl
    return impl(cache_id)


@app.route('/api/analysis/delete/<cache_id>', methods=['DELETE'])
def delete_analysis(cache_id):
    """T061: 删除缓存的分析数据"""
    from src.web.routes.analysis_cache import delete_analysis as impl
    return impl(cache_id)


@app.route('/api/ai/summary', methods=['POST'])
def generate_summary():
    """T056: 生成AI总结 - 支持从缓存数据或实时分析"""
    from src.web.routes.ai import generate_summary as impl
    return impl()


@app.route('/api/ai/summary/stream', methods=['POST'])
def generate_summary_stream():
    """T056b: 流式生成AI总结 - 支持从缓存数据或实时分析"""
    from src.web.routes.ai import generate_summary_stream as impl
    return impl()


# ============ 聊天记录预览API ============

@app.route('/api/preview/<filename>', methods=['GET'])
def preview_chat_records(filename):
    """预览聊天记录"""
    from src.web.routes.preview import preview_chat_records as impl
    return impl(filename)


@app.route('/api/preview/<filename>/stats', methods=['GET'])
def preview_chat_stats(filename):
    """获取聊天记录统计信息（用于过滤器）"""
    from src.web.routes.preview import preview_chat_stats as impl
    return impl(filename)


# ============ 导出API（预留接口）============

@app.route('/api/export/<format_type>', methods=['POST'])
def export_report(format_type):
    """导出报告 - 预留"""
    from src.web.routes.export import export_report as impl
    return impl(format_type)


@app.route('/api/export/network/png/start', methods=['POST'])
def export_network_png_start():
    """开始一次网络图 PNG 导出任务（服务端拼接）。"""
    from src.web.routes.export import export_network_png_start as impl
    return impl()


@app.route('/api/export/network/png/tile', methods=['POST'])
def export_network_png_tile():
    """上传单个网络图 PNG 导出 tile（服务端拼接）。"""
    from src.web.routes.export import export_network_png_tile as impl
    return impl()


@app.route('/api/export/network/png/finish', methods=['POST'])
def export_network_png_finish():
    """完成网络图 PNG 导出任务（服务端拼接）并写入 exports/。"""
    from src.web.routes.export import export_network_png_finish as impl
    return impl()


# ============ 热词示例API ============

@app.route('/api/chat-examples', methods=['GET'])
def get_chat_examples():
    """获取包含某个热词的聊天记录示例（2-4条）"""
    from src.web.routes.hotwords import get_chat_examples as impl
    return impl()


# ============ 系统信息API ============

@app.route('/api/system/info', methods=['GET'])
def system_info():
    """获取系统信息"""
    from src.web.routes.system import system_info as impl
    return impl()


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
