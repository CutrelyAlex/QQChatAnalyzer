/**
 * AI配置管理模块
 * 处理AI配置Tab中的所有交互和功能
 * 注：API密钥、基础URL、模型等敏感配置统一通过.env文件管理
 */

// ============ 配置对象 ============
const aiConfig = {
    // 基础配置
    enabled: localStorage.getItem('ai_enabled') !== 'false',
    target: localStorage.getItem('ai_target') || 'group',
    outputTokens: parseInt(localStorage.getItem('ai_output_tokens') || '4000'),
    contextTokens: parseInt(localStorage.getItem('ai_context_tokens') || '60000'),
    
    // 生成参数（从localStorage读取）
    temperature: parseFloat(localStorage.getItem('ai_temperature') || '0.7'),
    topP: parseFloat(localStorage.getItem('ai_top_p') || '0.9'),

    // 环境配置的默认值
    envDefaults: {
        apiBase: 'https://api.openai.com/v1',
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
            // 从后端获取环境配置的默认值
            if (data.apiBase) {
                aiConfig.envDefaults.apiBase = data.apiBase;
            }
            if (data.model) {
                aiConfig.envDefaults.model = data.model;
            }
        }
    } catch (error) {
        console.warn('Failed to fetch env defaults:', error);
        // 使用硬编码的默认值作为后备
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
    
    // 输出Token限制滑块
    const outputTokensSlider = document.getElementById('ai-output-tokens');
    const outputTokensValue = document.getElementById('ai-output-tokens-value');
    if (outputTokensSlider && outputTokensValue) {
        outputTokensSlider.value = aiConfig.outputTokens;
        outputTokensValue.textContent = aiConfig.outputTokens.toLocaleString();
    }
    
    // 输入Token预算滑块
    const contextTokensSlider = document.getElementById('ai-context-tokens');
    const contextTokensValue = document.getElementById('ai-context-tokens-value');
    if (contextTokensSlider && contextTokensValue) {
        contextTokensSlider.value = aiConfig.contextTokens;
        contextTokensValue.textContent = aiConfig.contextTokens.toLocaleString();
    }
    
    // 高级配置初始化
    
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
    
    // 输出Token限制滑块事件
    const outputTokensSlider = document.getElementById('ai-output-tokens');
    const outputTokensValue = document.getElementById('ai-output-tokens-value');
    if (outputTokensSlider && outputTokensValue) {
        outputTokensSlider.addEventListener('input', function() {
            aiConfig.outputTokens = parseInt(this.value);
            outputTokensValue.textContent = aiConfig.outputTokens.toLocaleString();
        });
    }
    
    // 输入Token预算滑块事件
    const contextTokensSlider = document.getElementById('ai-context-tokens');
    const contextTokensValue = document.getElementById('ai-context-tokens-value');
    if (contextTokensSlider && contextTokensValue) {
        contextTokensSlider.addEventListener('input', function() {
            aiConfig.contextTokens = parseInt(this.value);
            contextTokensValue.textContent = aiConfig.contextTokens.toLocaleString();
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
    
    // 测试连接按钮
    const testConfigBtn = document.getElementById('test-config-btn');
    if (testConfigBtn) {
        testConfigBtn.addEventListener('click', testAIConnection);
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

// ============ AI连接测试 ============

async function testAIConnection() {
    const testBtn = document.getElementById('test-config-btn');
    if (!testBtn) return;
    
    // 禁用按钮并显示加载状态
    testBtn.disabled = true;
    const originalText = testBtn.textContent;
    testBtn.textContent = '⏳ 测试中...';
    
    try {
        // 调用后端的测试连接端点
        const response = await fetch('/api/ai/status');
        const data = await response.json();
        
        if (data.success && data.available) {
            // 连接成功
            showConfigStatus(`✅ AI服务连接成功！\n模型: ${data.model}\nAPI基础URL: ${data.apiBase}`, 'success');
            testBtn.textContent = '✅ ' + originalText;
        } else if (data.success && !data.available) {
            // API未配置
            showConfigStatus('❌ API密钥未配置，请检查 .env 文件中的 OPENAI_API_KEY', 'error');
            testBtn.textContent = '❌ ' + originalText;
        } else {
            // 其他错误
            showConfigStatus(`❌ 连接失败: ${data.error || '未知错误'}`, 'error');
            testBtn.textContent = '❌ ' + originalText;
        }
    } catch (error) {
        // 网络错误
        console.error('测试连接失败:', error);
        showConfigStatus(`❌ 连接失败: ${error.message}`, 'error');
        testBtn.textContent = '❌ ' + originalText;
    } finally {
        // 3秒后恢复按钮状态
        setTimeout(() => {
            testBtn.disabled = false;
            testBtn.textContent = originalText;
        }, 3000);
    }
}


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
            max_tokens: aiConfig.outputTokens,
            context_budget: aiConfig.contextTokens,
            temperature: aiConfig.temperature,
            top_p: aiConfig.topP
        };
        
        // 如果是个人总结，检查QQ
        if (targetType === 'personal') {
            const personalTab = document.getElementById('personal-tab');
            if (!personalTab || !personalTab.querySelector('.qq-input')?.value) {
                throw new Error('请先在个人分析标签页输入QQ号或昵称并完成分析');
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
