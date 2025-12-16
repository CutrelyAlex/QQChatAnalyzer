/**
 * QQ聊天记录分析系统 - AI总结模块
 * AI生成摘要和报告功能（支持流式输出）
 */

// ============ AI总结 ============

function getAiGenerationParams() {
    const cfg = (typeof window !== 'undefined' && window.aiConfig) ? window.aiConfig : null;
    const temperature = (cfg && typeof cfg.temperature === 'number')
        ? cfg.temperature
        : parseFloat(localStorage.getItem('ai_temperature') || '0.7');
    const topP = (cfg && typeof cfg.topP === 'number')
        ? cfg.topP
        : parseFloat(localStorage.getItem('ai_top_p') || '0.9');
    return {
        temperature: Number.isFinite(temperature) ? temperature : 0.7,
        top_p: Number.isFinite(topP) ? topP : 0.9
    };
}

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
            max_tokens: appState.aiOutputTokens,          // 输出Token（报告长度）
            context_budget: appState.aiContextTokens,      // 输入Token预算（聊天采样）
            ...getAiGenerationParams()
        };
        
        // 检查是否选择了缓存ID
        const selectedCacheId = sessionStorage.getItem('selected_cache_id');
        if (selectedCacheId) {
            requestData.cache_id = selectedCacheId;
        }
        
        // 如果是个人总结，需要指定成员（支持 QQ号 或 昵称，内部解析为 participant_id）
        if (type === 'personal') {
            const q = document.getElementById('qq-input').value;
            if (!q) {
                showSummaryError('请先输入QQ号或昵称并进行个人分析');
                return;
            }

            const resolved = (typeof resolveMemberQuery === 'function') ? resolveMemberQuery(q) : { id: q };
            if (!resolved?.id) {
                showSummaryError('未找到匹配的成员（请输入QQ号或昵称）');
                return;
            }
            requestData.qq = resolved.id;
        }
        
        // 尝试使用流式API
        try {
            await generateSummaryStream(type, requestData);
        } catch (streamError) {
            console.warn('流式API失败，回退到普通API:', streamError);
            // 回退到普通API
            await generateSummaryFallback(type, requestData);
        }
        
    } catch (error) {
        console.error('生成总结失败:', error);
        showSummaryError('生成总结失败: ' + error.message);
    }
}

async function generateSummaryStream(type, requestData) {
    const typeNames = {
        'personal': '📱 个人年度报告',
        'group': '👥 群体 + 社交网络融合报告',
        'network': '👥 群体 + 社交网络融合报告'
    };
    
    // 准备显示区域
    document.getElementById('summary-title').textContent = typeNames[type] || 'AI 总结';
    document.getElementById('summary-text').innerHTML = '<span class="streaming-cursor">▌</span>';
    document.getElementById('summary-text').dataset.rawContent = '';
    document.getElementById('summary-loading').style.display = 'none';
    document.getElementById('summary-error').style.display = 'none';
    document.getElementById('summary-content').style.display = 'block';
    document.getElementById('summary-tokens').textContent = '生成中...';
    document.getElementById('summary-time').textContent = new Date().toLocaleTimeString();
    
    const response = await fetch(`${API_BASE}/ai/summary/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestData)
    });
    
    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || '请求失败');
    }
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let fullContent = '';
    let model = '';
    
    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');
        
        for (const line of lines) {
            if (line.startsWith('data: ')) {
                try {
                    const data = JSON.parse(line.slice(6));
                    
                    if (data.error) {
                        throw new Error(data.error);
                    }
                    
                    if (data.event === 'start') {
                        model = data.model || '';
                        document.getElementById('summary-model').textContent = model;
                    } else if (data.content) {
                        fullContent += data.content;
                        // 实时渲染 Markdown
                        document.getElementById('summary-text').innerHTML = 
                            renderMarkdown(fullContent) + '<span class="streaming-cursor">▌</span>';
                        // 自动滚动到底部
                        const textEl = document.getElementById('summary-text');
                        textEl.scrollTop = textEl.scrollHeight;
                    } else if (data.event === 'done') {
                        // 完成，移除光标
                        document.getElementById('summary-text').innerHTML = renderMarkdown(fullContent);
                        document.getElementById('summary-text').dataset.rawContent = fullContent;
                        document.getElementById('summary-tokens').textContent = 
                            `约 ${Math.round(fullContent.length / 1.5)} tokens`;
                    }
                } catch (e) {
                    if (e.message !== 'Unexpected end of JSON input') {
                        console.error('解析SSE数据失败:', e);
                    }
                }
            }
        }
    }
    
    // 确保最终状态正确
    if (fullContent) {
        document.getElementById('summary-text').innerHTML = renderMarkdown(fullContent);
        document.getElementById('summary-text').dataset.rawContent = fullContent;
    }
}

async function generateSummaryFallback(type, requestData) {
    // 原来的非流式实现作为回退
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
        'group': '👥 群体 + 社交网络融合报告',
        'network': '👥 群体 + 社交网络融合报告'
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
