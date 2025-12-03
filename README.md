# QQ 聊天记录分析系统

一个全面的网络应用系统，用于分析 QQ 聊天记录，支持个人分析、群体动态分析、社交网络可视化和 AI 驱动的摘要生成。

## 功能特性

### 核心分析能力

**个人分析**
- 个人用户统计，包括消息数量、活动模式和时间分布
- 按工作日的小时活跃度热力图
- 词汇档案和沟通偏好
- 历史活动趋势

**群体分析**
- 所有参与者的聚合统计
- 群体活动指标和参与度分布
- 按时间段检测高峰活动
- 热词和频繁内容分析，包含示例消息
- 每日和每小时的活动模式

**社交网络分析**
- 用户交互图表，显示连接强度可视化
- 用户之间的提及关系
- 社区检测和影响力排名
- 网络统计（聚类系数、密度、度数分布）

**AI 驱动的摘要**
- 使用 OpenAI API 生成创意的聊天记录摘要
- 可自定义的 AI 提供商配置（支持 OpenAI 兼容的 API）
- 代币估计和大型对话的数据裁剪
- 多种摘要样式（个人、群体、网络视角）

**数据管理**
- 聊天记录预览，支持筛选（按日期、参与者、内容）
- 报告导出功能
- 大数据集的分页支持
- 代币计数和 API 成本估计

## 技术栈

### 后端
- **框架**：Flask 3.1.0
- **语言**：Python 3.12+
- **自然语言处理**：jieba（中文分词）
- **可视化**：matplotlib、wordcloud
- **AI 集成**：OpenAI API（兼容 aihubmix.com 和其他 OpenAI 兼容提供商）

### 前端
- **架构**：模块化 JavaScript
- **UI 组件**：选项卡式界面，带模态对话框
- **可视化**：基于 Chart.js 的热力图和统计图表
- **通信**：使用 Fetch API 的 REST 端点

### 依赖项
- Flask 3.1.0 - Web 框架
- flask-cors 4.0.0 - 跨源支持
- python-dotenv 1.0.1 - 环境配置
- jieba 0.42.1 - 中文文本分词
- openai 1.61.0 - AI 集成
- wordcloud 1.9.4 - 词云生成
- matplotlib 3.10.0 - 绘图库
- numpy 1.26.3 - 数值计算

## 安装

### 系统要求
- Python 3.12 或更高版本
- pip 包管理器
- 最少 512 MB RAM
- Windows、macOS 或 Linux

### 安装步骤

1. 克隆或下载项目：
```bash
cd Ciyun
```

2. 创建虚拟环境（推荐）：
```bash
python -m venv venv
source venv/bin/activate  # 在 Windows 上：venv\Scripts\activate
```

3. 安装依赖项：
```bash
python -m pip install -r requirements.txt
```

4. 配置环境变量：
```bash
cp .env.example .env  # 如果可用
# 使用你的设置编辑 .env 文件
```

5. 创建所需的目录：
```bash
mkdir -p texts uploads exports
```

6. 运行应用程序：
```bash
python app.py
```

应用程序将在默认地址 `http://127.0.0.1:5002` 上启动。

## 配置

### 环境变量

**Flask 配置**
- `FLASK_DEBUG` - 启用调试模式（默认值：False）
- `FLASK_HOST` - 绑定地址（默认值：127.0.0.1）
- `FLASK_PORT` - 端口号（默认值：5000）

**AI 配置**
- `OPENAI_API_KEY` - AI 摘要功能所需
- `OPENAI_API_BASE` - API 端点（默认值：https://api.openai.com/v1）
- `OPENAI_MODEL` - 模型选择（默认值：gpt-3.5-turbo）
- `OPENAI_REQUEST_TIMEOUT` - 请求超时（秒）（默认值：30）

**数据处理**
- `MAX_FILE_SIZE_MB` - 最大文件上传大小（默认值：100）
- `MAX_MEMBERS` - 每个分析的最大用户数（默认值：5000）
- `MAX_TOKENS` - 最大 AI 代币限制（默认值：500000）

示例 `.env` 文件：
```
FLASK_DEBUG=True
OPENAI_API_KEY=your_api_key_here
OPENAI_API_BASE=https://aihubmix.com/v1
OPENAI_MODEL=gpt-4o-mini
OPENAI_REQUEST_TIMEOUT=30
```

## 聊天记录格式

系统处理具有以下 QQ 聊天记录格式的文本文件：

```
YYYY-MM-DD HH:MM:SS 发送者名称(QQ_号码)
消息内容（可以跨多行）
YYYY-MM-DD HH:MM:SS 下一个发送者(QQ_号码)
下一条消息内容
```

示例：
```
2025-05-10 14:30:45 Alice(12345678)
大家好！
2025-05-10 14:31:20 Bob(87654321)
Hi Alice，你好吗？
```

将聊天文件放在 `texts/` 目录中，扩展名为 `.txt`。

## API 端点

### 文件管理
- `GET /api/files` - 列出可用的聊天记录文件
- `POST /api/load` - 加载要分析的文件
- `GET /api/preview/<filename>` - 预览聊天记录（支持分页）
- `GET /api/preview/<filename>/stats` - 获取筛选统计信息

### 分析 API
- `GET /api/personal/<qq>` - 获取 QQ 号的个人统计信息
- `GET /api/personal/list/<filename>` - 列出文件中的所有用户
- `GET /api/group` - 获取群体范围的统计信息
- `GET /api/network` - 获取社交网络分析

### AI 功能
- `GET /api/ai/status` - 检查 AI 服务可用性
- `POST /api/test-ai-connection` - 测试 AI API 配置
- `POST /api/ai/token-estimate` - 估计数据裁剪的代币数
- `POST /api/ai/summary` - 生成 AI 摘要

### 数据导出
- `POST /api/export` - 导出分析报告

## 项目结构

```
Ciyun/
├── app.py                 # Flask 应用程序入口
├── requirements.txt       # Python 依赖项
├── .env                   # 环境配置
├── README.md             # 本文件
│
├── src/
│   ├── config.py         # 配置管理
│   ├── utils.py          # 共享工具函数
│   ├── LineProcess.py    # 聊天记录解析
│   ├── CutWords.py       # 词分词
│   ├── personal_analyzer.py     # 个人用户分析
│   ├── group_analyzer.py        # 群体统计
│   ├── network_analyzer.py      # 网络分析
│   ├── ai_summarizer.py         # AI 摘要生成
│   ├── data_pruner.py           # 代币管理
│   └── WordCloudMaker.py        # 可视化
│
├── templates/
│   └── index.html        # 主 UI 模板
│
├── static/
│   ├── css/
│   │   └── style.css     # 样式表
│   └── js/
│       ├── core.js       # 核心功能
│       ├── file-handler.js       # 文件操作
│       ├── analyzer.js   # 分析接口
│       ├── ai-summary.js # AI 集成
│       ├── ui.js         # UI 组件
│       ├── network.js    # 网络可视化
│       ├── hotwords.js   # 词频显示
│       └── config.js     # 配置管理
│
├── texts/                # 输入聊天记录文件
├── uploads/              # 临时上传存储
└── exports/              # 生成的报告文件
```

## 使用工作流

### 基本分析
1. 在 http://127.0.0.1:5002 处导航到 Web 界面
2. 从 `texts/` 目录上传或选择聊天记录文件
3. 选择分析类型（个人/群体/网络）
4. 输入参与者 QQ 号（用于个人分析）
5. 在相应选项卡中查看结果

### AI 摘要生成
1. 在"AI总结"选项卡中配置 AI API 设置
   - 输入 API 密钥和基础 URL
   - 点击"测试连接"验证配置
2. 选择摘要目标（个人/群体/网络）
3. 点击"生成AI总结"按钮
4. 在模态对话框中查看生成的摘要

### 数据预览
1. 使用预览选项卡浏览聊天记录
2. 按日期范围或参与者筛选
3. 大数据集的分页控制
4. 已识别主题的示例消息

## 性能考虑

- 大文件（>100MB）可能需要较长的处理时间
- AI 摘要生成前应用代币估计
- 数据裁剪使用多种策略（均匀、时间、基于频率）
- 网络分析 O(n²) 复杂度；最适合 <10,000 参与者

## 故障排除

### AI 服务不可用
- 验证是否设置了 `OPENAI_API_KEY` 环境变量
- 使用"测试连接"按钮测试连接
- 检查到 API 端点的网络连接
- 验证 API 基础 URL 和模型名称

### 解析错误
- 确保聊天记录格式与规范相匹配
- 检查文件编码是否为 UTF-8
- 验证 QQ 号为数字（不含特殊字符）

### 内存不足
- 减少文件大小或分小批处理
- 增加系统 RAM 或调整 `MAX_RECORDS_PER_LOAD`
- 对 AI 操作使用数据裁剪

### 性能问题
- 在生产环境中禁用调试模式（`FLASK_DEBUG=False`）
- 使用生产 WSGI 服务器（gunicorn、waitress）
- 为重复分析实现缓存

## 开发

### 运行测试
```bash
python test_analyzers.py
```

### 代码风格
- Python 文件遵循 PEP 8 规范
- JavaScript 使用带命名空间的模块化模式
- 文档中的注释使用英文
- HTML5 语义标记

### 添加新分析
1. 在 `src/` 中创建继承自基础模式的分析器类
2. 实现返回标准化字典的 `analyze()` 方法
3. 在 `app.py` 中添加 API 端点
4. 在 `static/js/` 中创建对应的前端模块

## 许可证

专有版权 - 本项目按原样提供，用于特定用例。

## 支持

如有关于功能的问题或疑问，请参考代码注释和内联文档。该系统针对中文文本分析进行了优化，但也支持多语言聊天记录。

## 版本历史

- v1.0.0 - 初始稳定版本
  - 个人、群体、网络分析
  - AI 摘要集成
  - 具有选项卡式界面的 Web 应用
  - 导出和预览功能

## 技术规范

**支持的输入大小**：1 MB - 100 MB（可配置）
**支持的参与者**：最多 5000 个唯一用户
**最大代币上下文**：500000 代币用于 AI 操作
**API 响应时间**：典型分析 <5 秒
**并发用户**：单线程（建议使用反向代理进行扩展）

## 注意事项

- 该系统针对 QQ 聊天记录分析进行了优化，但可以适配其他聊天格式
- AI 功能需要有效的 OpenAI API 凭证
- 数据在本地处理；除了 AI API 外，文件不会传输到外部服务
- 词云生成需要足够的词汇量（建议最少 50 个单词）

````
