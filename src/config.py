"""
配置管理模块 - 读取和验证环境变量
"""

import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


class Config:
    """应用配置类"""
    
    # Flask配置
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    HOST = os.getenv('FLASK_HOST', '127.0.0.1')
    PORT = int(os.getenv('FLASK_PORT', 5000))
    
    # AI配置 - OpenAI兼容API
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    OPENAI_API_BASE = os.getenv('OPENAI_API_BASE', 'https://api.openai.com/v1')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
    OPENAI_REQUEST_TIMEOUT = int(os.getenv('OPENAI_REQUEST_TIMEOUT', 30))
    
    # 数据处理配置
    MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB', 500))
    MAX_MEMBERS = int(os.getenv('MAX_MEMBERS', 5000))
    MAX_RECORDS_PER_LOAD = int(os.getenv('MAX_RECORDS_PER_LOAD', 1000000))

    JSON_TIMESTAMP_ASSUME_UTC = os.getenv('CIYUN_JSON_ASSUME_UTC', '0').strip().lower() in (
        '1', 'true', 'yes', 'y', 'on'
    )

    # JSON 时间戳语义：
    # - utc_to_local: 把 '...Z' 当作 UTC（标准语义），后续展示用本地时区
    # - wysiwyg: 忽略 Z/offset，把字符串中“看到的 HH:MM:SS”当作真实时间（不做时区转换）
    #
    # 说明：如果未显式设置 CIYUN_JSON_TIMESTAMP_MODE，则默认选择 utc_to_local。
    _JSON_TIMESTAMP_MODE_RAW = os.getenv('CIYUN_JSON_TIMESTAMP_MODE', '').strip().lower()
    if _JSON_TIMESTAMP_MODE_RAW in ('wysiwyg', 'literal', 'as_is', 'asis', 'no_tz', 'no_timezone'):
        JSON_TIMESTAMP_MODE = 'wysiwyg'
    elif _JSON_TIMESTAMP_MODE_RAW in ('utc_to_local', 'utc-local', 'utc2local', 'utc', 'standard'):
        JSON_TIMESTAMP_MODE = 'utc_to_local'
    else:
        # 遵循 Z 的标准语义
        JSON_TIMESTAMP_MODE = 'utc_to_local'
    
    # AI总结配置
    DEFAULT_MAX_TOKENS = int(os.getenv('DEFAULT_MAX_TOKENS', 200000))
    RESERVED_TOKENS = int(os.getenv('RESERVED_TOKENS', 500))
    DEFAULT_RETENTION_RATIO = float(os.getenv('DEFAULT_RETENTION_RATIO', 0.8))
    DEFAULT_CONTEXT_BUDGET = int(os.getenv('DEFAULT_CONTEXT_BUDGET', 60000))
    DEFAULT_OUTPUT_TOKENS = int(os.getenv('DEFAULT_OUTPUT_TOKENS', 4000))

    # 文本生成参数
    DEFAULT_TEMPERATURE = float(os.getenv('OPENAI_TEMPERATURE', 0.8))
    DEFAULT_TOP_P = float(os.getenv('OPENAI_TOP_P', 0.9))
    
    @classmethod
    def validate_config(cls):
        """验证配置的有效性"""
        issues = []
        
        # 检查AI API配置
        if not cls.OPENAI_API_KEY:
            issues.append("❌ OPENAI_API_KEY 未配置，AI功能将不可用")
        
        if not cls.OPENAI_API_BASE:
            issues.append("❌ OPENAI_API_BASE 未配置")
        
        if cls.OPENAI_REQUEST_TIMEOUT < 10:
            issues.append("⚠️  OPENAI_REQUEST_TIMEOUT 过短 (<10s)，可能导致API请求超时")
        
        if cls.MAX_FILE_SIZE_MB < 1:
            issues.append("❌ MAX_FILE_SIZE_MB 配置无效")
        
        if cls.DEFAULT_MAX_TOKENS < 5000:
            issues.append("⚠️  DEFAULT_MAX_TOKENS 过小，可能影响AI总结效果")
        
        if cls.DEFAULT_RETENTION_RATIO <= 0 or cls.DEFAULT_RETENTION_RATIO > 1:
            issues.append("❌ DEFAULT_RETENTION_RATIO 必须在 0-1 之间")

        if cls.DEFAULT_TEMPERATURE < 0 or cls.DEFAULT_TEMPERATURE > 2:
            issues.append("❌ OPENAI_TEMPERATURE 必须在 0-2 之间")

        if cls.DEFAULT_TOP_P < 0 or cls.DEFAULT_TOP_P > 1:
            issues.append("❌ OPENAI_TOP_P 必须在 0-1 之间")
        
        return issues
    
    @classmethod
    def print_config_status(cls):
        """打印配置状态"""
        print("\n" + "="*50)
        print("📋 应用配置状态")
        print("="*50)
        print(f"Flask: {cls.HOST}:{cls.PORT} (DEBUG={cls.DEBUG})")
        print(f"OpenAI API: {cls.OPENAI_API_BASE}")
        print(f"模型: {cls.OPENAI_MODEL}")
        print(f"API超时: {cls.OPENAI_REQUEST_TIMEOUT}s")
        print(f"最大文件: {cls.MAX_FILE_SIZE_MB}MB")
        print(f"最大成员数: {cls.MAX_MEMBERS}")
        print(f"Token限制: {cls.DEFAULT_MAX_TOKENS} (预留: {cls.RESERVED_TOKENS})")
        print(f"Context预算: {cls.DEFAULT_CONTEXT_BUDGET} tokens")
        print(f"输出长度: {cls.DEFAULT_OUTPUT_TOKENS} tokens")
        print(f"采样参数: temperature={cls.DEFAULT_TEMPERATURE}, top_p={cls.DEFAULT_TOP_P}")
        print(f"JSON 时间戳模式: {getattr(cls, 'JSON_TIMESTAMP_MODE', 'utc_to_local')}")
        
        # 验证并显示问题
        issues = cls.validate_config()
        if issues:
            print("\n⚠️  配置问题:")
            for issue in issues:
                print(f"   {issue}")
        else:
            print("\n✅ 配置全部有效")
        
        print("="*50 + "\n")


if __name__ == '__main__':
    Config.print_config_status()
