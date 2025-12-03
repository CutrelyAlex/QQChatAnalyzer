# QQ Chat Record Analysis System

A comprehensive web-based system for analyzing QQ chat records with support for personal analytics, group dynamics analysis, social network visualization, and AI-powered summaries.

## Features

### Core Analysis Capabilities

**Personal Analytics (个人分析)**
- Individual user statistics including message count, activity patterns, and timeline distribution
- Hourly activity heatmap by weekday
- Vocabulary profile and communication preferences
- Historical activity trends

**Group Analytics (群体分析)**  
- Aggregate statistics across all participants
- Group activity metrics and participation distribution
- Peak activity detection by time period
- Hot words and frequent content analysis with example messages
- Daily and hourly activity patterns

**Social Network Analysis (社交网络)**
- User interaction graph with connection strength visualization
- Mention relationships between users
- Community detection and influence ranking
- Network statistics (clustering coefficient, density, degree distribution)

**AI-Powered Summaries (AI总结)**
- Creative narrative summaries of chat records using OpenAI API
- Customizable AI provider configuration (supports OpenAI-compatible APIs)
- Token estimation and data pruning for large conversations
- Multiple summary styles (personal, group, network perspectives)

**Data Management**
- Chat record preview with filtering (by date, participant, content)
- Report export functionality
- Pagination support for large datasets
- Token counting and API cost estimation

## Technical Stack

### Backend
- **Framework**: Flask 3.1.0
- **Language**: Python 3.12+
- **NLP**: jieba (Chinese word segmentation)
- **Visualization**: matplotlib, wordcloud
- **AI Integration**: OpenAI API (compatible with aihubmix.com, other OpenAI-compatible providers)

### Frontend
- **Architecture**: Modular JavaScript
- **UI Components**: Tabbed interface with modal dialogs
- **Visualization**: Chart.js-based heatmaps and statistics
- **Communication**: Fetch API for REST endpoints

### Dependencies
- Flask 3.1.0 - Web framework
- flask-cors 4.0.0 - Cross-origin support
- python-dotenv 1.0.1 - Environment configuration
- jieba 0.42.1 - Chinese text segmentation
- openai 1.61.0 - AI integration
- wordcloud 1.9.4 - Word cloud generation
- matplotlib 3.10.0 - Plotting library
- numpy 1.26.3 - Numerical computing

## Installation

### System Requirements
- Python 3.12 or higher
- pip package manager
- 512 MB minimum RAM
- Windows, macOS, or Linux

### Setup Steps

1. Clone or download the project:
```bash
cd Ciyun
```

2. Create virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
python -m pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env  # If available
# Edit .env file with your settings
```

5. Create required directories:
```bash
mkdir -p texts uploads exports
```

6. Run the application:
```bash
python app.py
```

The application will start on `http://127.0.0.1:5002` by default.

## Configuration

### Environment Variables

**Flask Configuration**
- `FLASK_DEBUG` - Enable debug mode (default: False)
- `FLASK_HOST` - Bind address (default: 127.0.0.1)
- `FLASK_PORT` - Port number (default: 5000)

**AI Configuration**
- `OPENAI_API_KEY` - Required for AI summary features
- `OPENAI_API_BASE` - API endpoint (default: https://api.openai.com/v1)
- `OPENAI_MODEL` - Model selection (default: gpt-3.5-turbo)
- `OPENAI_REQUEST_TIMEOUT` - Request timeout in seconds (default: 30)

**Data Processing**
- `MAX_FILE_SIZE_MB` - Maximum file upload size (default: 100)
- `MAX_MEMBERS` - Maximum users per analysis (default: 5000)
- `MAX_TOKENS` - Maximum AI token limit (default: 500000)

Example `.env` file:
```
FLASK_DEBUG=True
OPENAI_API_KEY=your_api_key_here
OPENAI_API_BASE=https://aihubmix.com/v1
OPENAI_MODEL=gpt-4o-mini
OPENAI_REQUEST_TIMEOUT=30
```

## Chat Record Format

The system processes text files with the following QQ chat record format:

```
YYYY-MM-DD HH:MM:SS Sender_Name(QQ_Number)
message content (can span multiple lines)
YYYY-MM-DD HH:MM:SS Next_Sender(QQ_Number)
next message content
```

Example:
```
2025-05-10 14:30:45 Alice(12345678)
Hello everyone!
2025-05-10 14:31:20 Bob(87654321)
Hi Alice, how are you?
```

Place chat files in the `texts/` directory with `.txt` extension.

## API Endpoints

### File Management
- `GET /api/files` - List available chat record files
- `POST /api/load` - Load file for analysis
- `GET /api/preview/<filename>` - Preview chat records with pagination
- `GET /api/preview/<filename>/stats` - Get statistics for filtering

### Analysis APIs
- `GET /api/personal/<qq>` - Get personal statistics for QQ number
- `GET /api/personal/list/<filename>` - List all users in file
- `GET /api/group` - Get group-wide statistics
- `GET /api/network` - Get social network analysis

### AI Features
- `GET /api/ai/status` - Check AI service availability
- `POST /api/test-ai-connection` - Test AI API configuration
- `POST /api/ai/token-estimate` - Estimate tokens for data pruning
- `POST /api/ai/summary` - Generate AI summary

### Data Export
- `POST /api/export` - Export analysis report

## Project Structure

```
Ciyun/
├── app.py                 # Flask application entry point
├── requirements.txt       # Python dependencies
├── .env                   # Environment configuration
├── README.md             # This file
│
├── src/
│   ├── config.py         # Configuration management
│   ├── utils.py          # Shared utility functions
│   ├── LineProcess.py    # Chat record parsing
│   ├── CutWords.py       # Word tokenization
│   ├── personal_analyzer.py     # Individual user analysis
│   ├── group_analyzer.py        # Group statistics
│   ├── network_analyzer.py      # Network analysis
│   ├── ai_summarizer.py         # AI summary generation
│   ├── data_pruner.py           # Token management
│   └── WordCloudMaker.py        # Visualization
│
├── templates/
│   └── index.html        # Main UI template
│
├── static/
│   ├── css/
│   │   └── style.css     # Stylesheet
│   └── js/
│       ├── core.js       # Core functionality
│       ├── file-handler.js       # File operations
│       ├── analyzer.js   # Analysis interface
│       ├── ai-summary.js # AI integration
│       ├── ui.js         # UI components
│       ├── network.js    # Network visualization
│       ├── hotwords.js   # Word frequency display
│       └── config.js     # Configuration management
│
├── texts/                # Input chat record files
├── uploads/              # Temporary upload storage
└── exports/              # Generated report files
```

## Usage Workflow

### Basic Analysis
1. Navigate to web interface at http://127.0.0.1:5002
2. Upload or select chat record file from `texts/` directory
3. Select analysis type (Personal/Group/Network)
4. Enter participant QQ number (for personal analysis)
5. View results in respective tabs

### AI Summary Generation
1. Configure AI API settings in "AI总结" tab
   - Input API key and base URL
   - Click "测试连接" to verify configuration
2. Select summary target (Personal/Group/Network)
3. Click "生成AI总结" button
4. Review generated summary in modal dialog

### Data Preview
1. Use Preview tab to browse chat records
2. Filter by date range or participant
3. Pagination controls for large datasets
4. Example messages for identified topics

## Performance Considerations

- Large files (>100MB) may require extended processing time
- Token estimation applies before AI summary generation
- Data pruning uses multiple strategies (uniform, temporal, frequency-based)
- Network analysis O(n²) complexity; optimal for <10,000 participants

## Troubleshooting

### AI Service Unavailable
- Verify `OPENAI_API_KEY` environment variable is set
- Test connection using "测试连接" button
- Check network connectivity to API endpoint
- Verify API base URL and model name

### Parse Errors
- Ensure chat record format matches specification
- Check file encoding is UTF-8
- Verify QQ numbers are numeric (no special characters)

### Out of Memory
- Reduce file size or process in smaller batches
- Increase system RAM or adjust `MAX_RECORDS_PER_LOAD`
- Use data pruning for AI operations

### Performance Issues
- Disable debug mode in production (`FLASK_DEBUG=False`)
- Use production WSGI server (gunicorn, waitress)
- Implement caching for repeated analyses

## Development

### Running Tests
```bash
python test_analyzers.py
```

### Code Style
- Python files follow PEP 8 conventions
- JavaScript uses modular pattern with namespacing
- Comments in English for documentation
- HTML5 semantic markup

### Adding New Analysis
1. Create analyzer class in `src/` inheriting from base pattern
2. Implement `analyze()` method returning standardized dict
3. Add API endpoint in `app.py`
4. Create corresponding frontend module in `static/js/`

## License

Proprietary - This project is provided as-is for specific use case.

## Support

For issues or questions regarding functionality, refer to code comments and inline documentation. The system is optimized for Chinese text analysis but supports multilingual chat records.

## Version History

- v1.0.0 - Initial stable release
  - Personal, group, network analysis
  - AI summary integration
  - Web-based UI with tabbed interface
  - Export and preview functionality

## Technical Specifications

**Supported Input Size**: 1 MB - 100 MB (configurable)
**Supported Participants**: Up to 5000 unique users
**Max Token Context**: 500000 tokens for AI operations
**API Response Time**: <5 seconds for typical analysis
**Concurrent Users**: Single-threaded (recommended reverse proxy for scaling)

## Notes

- The system is optimized for QQ chat record analysis but can be adapted for other chat formats
- AI features require valid OpenAI API credentials
- Data is processed locally; files are not transmitted to external services except AI API
- Word cloud generation requires sufficient vocabulary (minimum 50 words recommended)
