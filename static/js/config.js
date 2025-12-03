/**
 * AI配置管理模块
 * 处理AI配置Tab中的所有交互和功能
 */

// ============ 配置对象 ============
const aiConfig = {
    // 基础配置
    enabled: localStorage.getItem('ai_enabled') !== 'false',
    target: localStorage.getItem('ai_target') || 'group',
    tokenLimit: parseInt(localStorage.getItem('ai_token_limit') || '5000'),
    
    // 高级配置 - 从env默认值初始化
    apiBase: localStorage.getItem('ai_api_base') || '',
    apiKey: localStorage.getItem('ai_api_key') || '',
    model: localStorage.getItem('ai_model') || '',
    temperature: parseFloat(localStorage.getItem('ai_temperature') || '0.7'),
    topP: parseFloat(localStorage.getItem('ai_top_p') || '0.9'),
    timeout: parseInt(localStorage.getItem('ai_timeout') || '30'),
    
    // 环境配置的默认值
    envDefaults: {
        apiBase: 'https://api.openai.com/v1',
        apiKey: '',
        model: 'gpt-4o-mini'
    }
};

// ============ 初始化 ============
document.addEventListener('DOMContentLoaded', async function() {
    await fetchEnvDefaults();
    initializeConfigUI();
    attachEventListeners();
});

// ============ 从后端获取env默认值 ============
async function fetchEnvDefaults() {
    try {
        const response = await fetch('/api/ai/status');
        const data = await response.json();
        
        if (data.success) {
            // 更新env默认值
            const baseUrl = data.base_url || 'https://api.openai.com/v1';
            const model = data.model || 'gpt-4o-mini';
            const apiKey = data.api_key || '';
            
            aiConfig.envDefaults.apiBase = baseUrl;
            aiConfig.envDefaults.model = model;
            aiConfig.envDefaults.apiKey = apiKey;
            
            // 如果localStorage中没有保存的值，则使用env默认值
            // 注意：即使localStorage为空字符串，我们也认为是已保存的
            if (localStorage.getItem('ai_api_base') === null) {
                aiConfig.apiBase = baseUrl;
            }
            if (localStorage.getItem('ai_model') === null) {
                aiConfig.model = model;
            }
            if (localStorage.getItem('ai_api_key') === null) {
                aiConfig.apiKey = apiKey;
            }
        }
    } catch (error) {
        console.warn('Failed to fetch env defaults:', error);
        // 使用硬编码的默认值作为后备
        aiConfig.apiBase = aiConfig.apiBase || 'https://api.openai.com/v1';
        aiConfig.model = aiConfig.model || 'gpt-4o-mini';
    }
}

// ============ UI初始化 ============
function initializeConfigUI() {
    // 基础配置初始化
    const enableToggle = document.getElementById('ai-enable-toggle');
    if (enableToggle) {
        enableToggle.checked = aiConfig.enabled;
        updateStatusText();
    }
    
    const targetSelect = document.getElementById('ai-target-select');
    if (targetSelect) {
        targetSelect.value = aiConfig.target;
    }
    
    // Token限制滑块
    const tokenLimitSlider = document.getElementById('ai-token-limit');
    const tokenLimitValue = document.getElementById('ai-token-limit-value');
    if (tokenLimitSlider && tokenLimitValue) {
        tokenLimitSlider.value = aiConfig.tokenLimit;
        tokenLimitValue.textContent = aiConfig.tokenLimit.toLocaleString();
    }
    
    // 高级配置初始化
    const apiBase = document.getElementById('ai-api-base');
    if (apiBase) {
        apiBase.value = aiConfig.apiBase || aiConfig.envDefaults.apiBase;
        apiBase.placeholder = '默认: ' + aiConfig.envDefaults.apiBase;
    }
    
    const apiKey = document.getElementById('ai-api-key');
    if (apiKey) {
        apiKey.value = aiConfig.apiKey || aiConfig.envDefaults.apiKey;
        if (aiConfig.envDefaults.apiKey && !aiConfig.apiKey) {
            apiKey.placeholder = '使用环境变量配置的密钥';
        }
    }
    
    // 模型文本输入框
    const modelInput = document.getElementById('ai-model');
    if (modelInput) {
        modelInput.value = aiConfig.model || aiConfig.envDefaults.model;
        modelInput.placeholder = '默认: ' + aiConfig.envDefaults.model;
    }
    
    const temperatureSlider = document.getElementById('ai-temperature');
    const temperatureValue = document.getElementById('ai-temperature-value');
    if (temperatureSlider && temperatureValue) {
        temperatureSlider.value = aiConfig.temperature;
        temperatureValue.textContent = aiConfig.temperature.toFixed(1);
    }
    
    const topPSlider = document.getElementById('ai-top-p');
    const topPValue = document.getElementById('ai-top-p-value');
    if (topPSlider && topPValue) {
        topPSlider.value = aiConfig.topP;
        topPValue.textContent = aiConfig.topP.toFixed(2);
    }
    
    const timeoutInput = document.getElementById('ai-timeout');
    if (timeoutInput) {
        timeoutInput.value = aiConfig.timeout;
    }
}

// ============ 事件监听 ============
function attachEventListeners() {
    // 基础配置事件
    const enableToggle = document.getElementById('ai-enable-toggle');
    if (enableToggle) {
        enableToggle.addEventListener('change', function() {
            aiConfig.enabled = this.checked;
            updateStatusText();
        });
    }
    
    const targetSelect = document.getElementById('ai-target-select');
    if (targetSelect) {
        targetSelect.addEventListener('change', function() {
            aiConfig.target = this.value;
        });
    }
    
    // Token限制滑块事件
    const tokenLimitSlider = document.getElementById('ai-token-limit');
    const tokenLimitValue = document.getElementById('ai-token-limit-value');
    if (tokenLimitSlider && tokenLimitValue) {
        tokenLimitSlider.addEventListener('input', function() {
            aiConfig.tokenLimit = parseInt(this.value);
            tokenLimitValue.textContent = aiConfig.tokenLimit.toLocaleString();
        });
    }
    
    // 展开/隐藏高级设置
    const toggleAdvancedBtn = document.getElementById('toggle-advanced');
    const advancedSettings = document.getElementById('advanced-settings');
    if (toggleAdvancedBtn && advancedSettings) {
        toggleAdvancedBtn.addEventListener('click', function(e) {
            e.preventDefault();
            const isHidden = advancedSettings.style.display === 'none';
            advancedSettings.style.display = isHidden ? 'block' : 'none';
            toggleAdvancedBtn.textContent = isHidden ? '🔽 折叠高级设置' : '🔧 展开高级设置';
        });
    }
    
    // 高级配置事件
    const apiBase = document.getElementById('ai-api-base');
    if (apiBase) {
        apiBase.addEventListener('change', function() {
            aiConfig.apiBase = this.value;
        });
    }
    
    const apiKey = document.getElementById('ai-api-key');
    if (apiKey) {
        apiKey.addEventListener('change', function() {
            aiConfig.apiKey = this.value;
        });
    }
    
    // 密钥显示/隐藏切换
    const toggleApiKeyBtn = document.getElementById('toggle-api-key');
    if (toggleApiKeyBtn && apiKey) {
        toggleApiKeyBtn.addEventListener('click', function(e) {
            e.preventDefault();
            const isPassword = apiKey.type === 'password';
            apiKey.type = isPassword ? 'text' : 'password';
            toggleApiKeyBtn.textContent = isPassword ? 'X' : 'O';
        });
    }
    
    // 模型文本输入框事件
    const modelInput = document.getElementById('ai-model');
    if (modelInput) {
        modelInput.addEventListener('change', function() {
            aiConfig.model = this.value;
        });
        // 同时监听input事件以提供实时反馈
        modelInput.addEventListener('input', function() {
            aiConfig.model = this.value;
        });
    }
    
    // 温度滑块
    const temperatureSlider = document.getElementById('ai-temperature');
    const temperatureValue = document.getElementById('ai-temperature-value');
    if (temperatureSlider && temperatureValue) {
        temperatureSlider.addEventListener('input', function() {
            aiConfig.temperature = parseFloat(this.value);
            temperatureValue.textContent = aiConfig.temperature.toFixed(1);
        });
    }
    
    // Top P滑块
    const topPSlider = document.getElementById('ai-top-p');
    const topPValue = document.getElementById('ai-top-p-value');
    if (topPSlider && topPValue) {
        topPSlider.addEventListener('input', function() {
            aiConfig.topP = parseFloat(this.value);
            topPValue.textContent = aiConfig.topP.toFixed(2);
        });
    }
    
    // Timeout输入框
    const timeoutInput = document.getElementById('ai-timeout');
    if (timeoutInput) {
        timeoutInput.addEventListener('change', function() {
            aiConfig.timeout = parseInt(this.value);
        });
    }
    
    // 配置操作按钮
    const saveBtn = document.getElementById('save-config-btn');
    if (saveBtn) {
        saveBtn.addEventListener('click', saveConfig);
    }
    
    const resetBtn = document.getElementById('reset-config-btn');
    if (resetBtn) {
        resetBtn.addEventListener('click', resetConfig);
    }
    
    const testBtn = document.getElementById('test-config-btn');
    if (testBtn) {
        testBtn.addEventListener('click', testConnection);
    }
}

// ============ 配置操作函数 ============

function saveConfig() {
    // 保存到localStorage
    localStorage.setItem('ai_enabled', aiConfig.enabled);
    localStorage.setItem('ai_target', aiConfig.target);
    localStorage.setItem('ai_token_limit', aiConfig.tokenLimit);
    
    // 高级设置
    localStorage.setItem('ai_api_base', aiConfig.apiBase);
    localStorage.setItem('ai_api_key', aiConfig.apiKey);
    localStorage.setItem('ai_model', aiConfig.model);
    localStorage.setItem('ai_temperature', aiConfig.temperature);
    localStorage.setItem('ai_top_p', aiConfig.topP);
    localStorage.setItem('ai_timeout', aiConfig.timeout);
    
    // 也更新appState（如果存在）
    if (typeof appState !== 'undefined') {
        appState.aiEnabled = aiConfig.enabled;
        appState.aiMaxTokens = aiConfig.tokenLimit;
    }
    
    showConfigStatus('✅ 配置已保存', 'success');
}

function resetConfig() {
    // 确认重置
    if (!confirm('确定要恢复默认设置吗？')) {
        return;
    }
    
    // 重置配置对象到env默认值
    aiConfig.enabled = true;
    aiConfig.target = 'group';
    aiConfig.tokenLimit = 5000;
    aiConfig.apiBase = aiConfig.envDefaults.apiBase;
    aiConfig.apiKey = aiConfig.envDefaults.apiKey;
    aiConfig.model = aiConfig.envDefaults.model;
    aiConfig.temperature = 0.7;
    aiConfig.topP = 0.9;
    aiConfig.timeout = 30;
    
    // 清除localStorage
    localStorage.removeItem('ai_enabled');
    localStorage.removeItem('ai_target');
    localStorage.removeItem('ai_token_limit');
    localStorage.removeItem('ai_api_base');
    localStorage.removeItem('ai_api_key');
    localStorage.removeItem('ai_model');
    localStorage.removeItem('ai_temperature');
    localStorage.removeItem('ai_top_p');
    localStorage.removeItem('ai_timeout');
    
    // 刷新UI
    initializeConfigUI();
    
    showConfigStatus('🔄 已恢复默认设置', 'info');
}

async function testConnection() {
    // 验证必填字段
    if (!aiConfig.apiKey) {
        showConfigStatus('❌ 请先填写API密钥', 'error');
        return;
    }
    
    if (!aiConfig.apiBase) {
        showConfigStatus('❌ 请先填写API基础URL', 'error');
        return;
    }
    
    const testBtn = document.getElementById('test-config-btn');
    const originalText = testBtn.textContent;
    testBtn.disabled = true;
    testBtn.textContent = '⏳ 测试中...';
    
    try {
        const response = await fetch('/api/test-ai-connection', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                api_base: aiConfig.apiBase,
                api_key: aiConfig.apiKey,
                model: aiConfig.model,
                timeout: aiConfig.timeout
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            showConfigStatus('✅ 连接测试成功！', 'success');
        } else {
            showConfigStatus(`❌ 连接失败: ${data.error || '未知错误'}`, 'error');
        }
    } catch (error) {
        showConfigStatus(`❌ 测试出错: ${error.message}`, 'error');
    } finally {
        testBtn.disabled = false;
        testBtn.textContent = originalText;
    }
}

// ============ 工具函数 ============

function updateStatusText() {
    const statusText = document.getElementById('ai-status-text');
    if (statusText) {
        statusText.textContent = aiConfig.enabled ? '✅ 已启用' : '❌ 已禁用';
    }
}

function showConfigStatus(message, type = 'info') {
    const statusDiv = document.getElementById('config-status');
    const messageDiv = document.getElementById('config-status-message');
    
    if (!statusDiv || !messageDiv) {
        return;
    }
    
    messageDiv.textContent = message;
    statusDiv.className = `config-status status-${type}`;
    statusDiv.style.display = 'block';
    
    // 5秒后自动隐藏
    setTimeout(() => {
        statusDiv.style.display = 'none';
    }, 5000);
}

// 导出全局访问
window.saveConfig = saveConfig;
window.resetConfig = resetConfig;
window.testConnection = testConnection;
window.aiConfig = aiConfig;

// ============ AI总结生成流程 ============

let generationController = null;
let generationStartTime = null;

function initializeSummaryGeneration() {
    const generateBtn = document.getElementById('generate-summary-btn');
    const targetSelect = document.getElementById('summary-target-select');
    const cancelBtn = document.getElementById('cancel-generation-btn');
    const copyBtn = document.getElementById('copy-summary-btn');
    const newGenBtn = document.getElementById('new-generation-btn');
    const retryBtn = document.getElementById('retry-generation-btn');
    const resetBtn = document.getElementById('reset-generation-btn');
    
    if (generateBtn) {
        generateBtn.addEventListener('click', startSummaryGeneration);
    }
    
    if (cancelBtn) {
        cancelBtn.addEventListener('click', cancelGeneration);
    }
    
    if (copyBtn) {
        copyBtn.addEventListener('click', copySummaryContent);
    }
    
    if (newGenBtn) {
        newGenBtn.addEventListener('click', resetSummaryUI);
    }
    
    if (retryBtn) {
        retryBtn.addEventListener('click', startSummaryGeneration);
    }
    
    if (resetBtn) {
        resetBtn.addEventListener('click', resetSummaryUI);
    }
}

function showProgressContainer() {
    document.getElementById('generation-progress-container').style.display = 'block';
    document.getElementById('generation-success-container').style.display = 'none';
    document.getElementById('generation-error-container').style.display = 'none';
    
    // 重置日志
    document.querySelector('.stream-log').innerHTML = '';
    generationStartTime = Date.now();
}

function hideProgressContainer() {
    document.getElementById('generation-progress-container').style.display = 'none';
}

function addStreamLog(message, type = 'info') {
    const streamLog = document.querySelector('.stream-log');
    const logItem = document.createElement('div');
    logItem.className = `stream-log-item ${type}`;
    logItem.textContent = message;
    streamLog.appendChild(logItem);
    
    // 自动滚到底部
    streamLog.parentElement.scrollTop = streamLog.parentElement.scrollHeight;
}

function updateProgressStep(stepText) {
    const progressStep = document.getElementById('progress-step');
    if (progressStep) {
        progressStep.textContent = stepText;
    }
    
    addStreamLog(stepText, 'info');
}

async function startSummaryGeneration() {
    if (!aiConfig.enabled) {
        showConfigStatus('❌ 请先启用AI功能', 'error');
        return;
    }
    
    if (!aiConfig.apiKey) {
        showConfigStatus('❌ 请先配置API密钥', 'error');
        return;
    }
    
    if (!appState.currentFile) {
        showConfigStatus('❌ 请先加载文件', 'error');
        return;
    }
    
    const targetType = document.getElementById('summary-target-select').value;
    
    try {
        // 禁用生成按钮
        const generateBtn = document.getElementById('generate-summary-btn');
        generateBtn.disabled = true;
        generateBtn.textContent = '⏳ 生成中...';
        
        // 创建AbortController用于取消
        generationController = new AbortController();
        
        // 显示进度容器
        showProgressContainer();
        
        // 初始化进度信息
        updateProgressStep('正在初始化...');
        
        // 准备请求数据
        updateProgressStep('准备数据...');
        
        const requestData = {
            type: targetType,
            filename: appState.currentFile,
            max_tokens: aiConfig.tokenLimit,
            ai_config: {
                api_key: aiConfig.apiKey,
                api_base: aiConfig.apiBase,
                model: aiConfig.model
            }
        };
        
        // 如果是个人总结，检查QQ
        if (targetType === 'personal') {
            const personalTab = document.getElementById('personal-tab');
            if (!personalTab || !personalTab.querySelector('.qq-input')?.value) {
                throw new Error('请先在个人分析标签页输入QQ号并完成分析');
            }
        }
        
        // 发送请求
        updateProgressStep('正在发送请求到服务器...');
        
        const response = await fetch('/api/ai/summary', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData),
            signal: generationController.signal
        });
        
        // 处理响应
        updateProgressStep('处理服务器响应...');
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || '服务器错误');
        }
        
        if (!data.success) {
            throw new Error(data.error || '生成失败');
        }
        
        // 显示成功
        updateProgressStep('总结生成完成！');
        
        // 延迟显示成功信息
        await new Promise(r => setTimeout(r, 500));
        
        showSuccessContainer(data, targetType);
        
    } catch (error) {
        if (error.name === 'AbortError') {
            addStreamLog('用户取消了生成操作', 'warning');
        } else {
            console.error('生成总结失败:', error);
            addStreamLog(`生成失败: ${error.message}`, 'error');
            showErrorContainer(error.message);
        }
    } finally {
        // 恢复生成按钮
        const generateBtn = document.getElementById('generate-summary-btn');
        generateBtn.disabled = false;
        generateBtn.textContent = '✨ 生成AI总结';
    }
}

function cancelGeneration() {
    if (generationController) {
        generationController.abort();
        addStreamLog('正在取消生成...', 'warning');
    }
}

function showSuccessContainer(data, type) {
    hideProgressContainer();
    
    const successContainer = document.getElementById('generation-success-container');
    const contentDisplay = document.getElementById('summary-content-display');
    const statsDiv = document.getElementById('generation-stats');
    
    // 显示统计信息
    const elapsed = ((Date.now() - generationStartTime) / 1000).toFixed(1);
    const statsText = `使用时间: ${elapsed}s | Tokens: ${data.tokens_used || 'N/A'} | 模型: ${data.model || 'N/A'}`;
    if (statsDiv) {
        statsDiv.textContent = statsText;
    }
    
    // 显示总结内容
    if (contentDisplay) {
        contentDisplay.textContent = data.summary || '无内容';
    }
    
    successContainer.style.display = 'block';
}

function showErrorContainer(errorMessage) {
    hideProgressContainer();
    
    const errorContainer = document.getElementById('generation-error-container');
    const errorMessageDiv = document.getElementById('error-message');
    
    if (errorMessageDiv) {
        errorMessageDiv.textContent = errorMessage;
    }
    
    errorContainer.style.display = 'block';
}

function resetSummaryUI() {
    hideProgressContainer();
    document.getElementById('generation-success-container').style.display = 'none';
    document.getElementById('generation-error-container').style.display = 'none';
}

function copySummaryContent() {
    const contentDisplay = document.getElementById('summary-content-display');
    if (contentDisplay && contentDisplay.textContent) {
        navigator.clipboard.writeText(contentDisplay.textContent).then(() => {
            showConfigStatus('✅ 已复制到剪贴板', 'success');
        }).catch(() => {
            showConfigStatus('❌ 复制失败', 'error');
        });
    }
}

// 在DOMContentLoaded时初始化总结生成
document.addEventListener('DOMContentLoaded', function() {
    // 延迟初始化，确保其他元素已加载
    setTimeout(initializeSummaryGeneration, 100);
});
