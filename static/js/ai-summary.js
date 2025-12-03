/**
 * QQ聊天记录分析系统 - AI总结模块
 * AI生成摘要和报告功能
 */

// ============ AI总结 ============

async function generateSummary(type) {
    if (!appState.aiEnabled || !appState.currentFile) {
        showStatusMessage('error', '请启用AI并加载文件');
        return;
    }
    
    try {
        // 显示加载状态
        showSummaryModal(true);
        
        // 构建请求数据
        const requestData = {
            type: type,
            filename: appState.currentFile,
            max_tokens: appState.aiMaxTokens
        };
        
        // 添加AI配置（如果已初始化）
        if (typeof aiConfig !== 'undefined') {
            requestData.ai_config = {
                api_key: aiConfig.api_key || '',
                api_base: aiConfig.api_base || '',
                model: aiConfig.model || ''
            };
        }
        
        // 如果是个人总结，需要QQ号
        if (type === 'personal') {
            const qq = document.getElementById('qq-input').value;
            if (!qq) {
                showSummaryError('请先输入QQ号并进行个人分析');
                return;
            }
            requestData.qq = qq;
        }
        
        const response = await fetch(`${API_BASE}/ai/summary`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestData)
        });
        
        const data = await response.json();
        
        if (data.success) {
            displaySummary(type, data);
        } else {
            showSummaryError(data.error || '生成失败');
        }
    } catch (error) {
        console.error('生成总结失败:', error);
        showSummaryError('生成总结失败: ' + error.message);
    }
}

function showSummaryModal(show, loading = true) {
    const modal = document.getElementById('summary-modal');
    const loadingDiv = document.getElementById('summary-loading');
    const contentDiv = document.getElementById('summary-content');
    const errorDiv = document.getElementById('summary-error');
    
    if (show) {
        modal.style.display = 'flex';
        if (loading) {
            loadingDiv.style.display = 'block';
            contentDiv.style.display = 'none';
            errorDiv.style.display = 'none';
        }
    } else {
        modal.style.display = 'none';
    }
}

function displaySummary(type, data) {
    const typeNames = {
        'personal': '📱 个人年度报告',
        'group': '👥 群聊年度报告',
        'network': '🕸️ 社交网络报告'
    };
    
    // 设置标题
    document.getElementById('summary-title').textContent = typeNames[type] || 'AI 总结';
    
    // 渲染 Markdown 内容
    const summaryContent = data.summary || '';
    const summaryHtml = renderMarkdown(summaryContent);
    
    document.getElementById('summary-text').innerHTML = summaryHtml;
    
    // 更新元信息
    document.getElementById('summary-time').textContent = new Date().toLocaleTimeString();
    document.getElementById('summary-tokens').textContent = data.tokens_used ? `${data.tokens_used} tokens` : '-';
    document.getElementById('summary-model').textContent = data.model || '-';
    
    // 存储原始内容用于复制
    document.getElementById('summary-text').dataset.rawContent = summaryContent;
    
    document.getElementById('summary-loading').style.display = 'none';
    document.getElementById('summary-error').style.display = 'none';
    document.getElementById('summary-content').style.display = 'block';
}

function renderMarkdown(text) {
    // 简单的 Markdown 渲染
    if (!text) return '';
    
    return text
        // 标题
        .replace(/^### (.*$)/gm, '<h3>$1</h3>')
        .replace(/^## (.*$)/gm, '<h2>$1</h2>')
        .replace(/^# (.*$)/gm, '<h1>$1</h1>')
        // 加粗
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        // 斜体
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        // 代码
        .replace(/`(.*?)`/g, '<code>$1</code>')
        // 列表
        .replace(/^\- (.*$)/gm, '<li>$1</li>')
        .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
        // 分隔线
        .replace(/^---$/gm, '<hr>')
        // 换行
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>');
}

function showSummaryError(message) {
    const errorDiv = document.getElementById('summary-error');
    errorDiv.textContent = '❌ ' + message;
    errorDiv.style.display = 'block';
    
    document.getElementById('summary-loading').style.display = 'none';
    document.getElementById('summary-content').style.display = 'none';
}

function closeSummaryModal() {
    document.getElementById('summary-modal').style.display = 'none';
}

function copySummary() {
    const rawContent = document.getElementById('summary-text').dataset.rawContent || 
                       document.getElementById('summary-text').textContent;
    
    navigator.clipboard.writeText(rawContent).then(() => {
        showStatusMessage('success', '已复制到剪贴板');
    }).catch(err => {
        showStatusMessage('error', '复制失败');
    });
}
