/**
 * QQ聊天记录分析系统 - 核心模块
 * 全局变量、初始化、事件绑定、工具函数
 */

// ============ 全局变量 ============

let appState = {
    currentFile: null,
    fileData: null,
    aiEnabled: localStorage.getItem('ai_enabled') === 'true',
    aiMaxTokens: parseInt(localStorage.getItem('ai_max_tokens') || '100000'),
    selectedQQ: null,
    analysisData: {
        personal: null,
        group: null,
        network: null
    },
    previewData: {
        currentPage: 1,
        pageSize: 50,
        filterType: 'all',
        filterValue: '',
        totalRecords: 0,
        totalPages: 1
    }
};

const API_BASE = '/api';

// ============ 初始化 ============

document.addEventListener('DOMContentLoaded', () => {
    console.log('应用初始化中...');
    
    // 初始化UI
    initializeUI();
    loadFileList();
    checkAIStatus();
    
    // 绑定事件
    bindEvents();
    
    console.log('应用初始化完成');
});

function initializeUI() {
    // UI初始化
    updateAIPanel();
}

function bindEvents() {
    // 文件加载
    document.getElementById('load-btn').addEventListener('click', loadFile);
    
    // 标签页切换
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.addEventListener('click', switchTab);
    });
    
    // 分析按钮
    document.getElementById('personal-analyze-btn').addEventListener('click', analyzePersonal);
    document.getElementById('group-analyze-btn').addEventListener('click', analyzeGroup);
    document.getElementById('network-analyze-btn').addEventListener('click', analyzeNetwork);
    
    // AI总结按钮
    document.getElementById('personal-summary-btn').addEventListener('click', () => generateSummary('personal'));
    document.getElementById('group-summary-btn').addEventListener('click', () => generateSummary('group'));
    document.getElementById('network-summary-btn').addEventListener('click', () => generateSummary('network'));
    
    // 导出按钮
    document.getElementById('export-btn').addEventListener('click', exportReport);
    
    // 预览功能
    document.getElementById('preview-load-btn').addEventListener('click', loadChatRecords);
    document.getElementById('preview-prev-btn').addEventListener('click', prevPreviewPage);
    document.getElementById('preview-next-btn').addEventListener('click', nextPreviewPage);
    
    // 预览筛选器重置分页
    document.getElementById('preview-date-filter').addEventListener('change', () => {
        appState.previewData.currentPage = 1;
    });
    document.getElementById('preview-qq-filter').addEventListener('change', () => {
        appState.previewData.currentPage = 1;
    });
}

// ============ 标签页切换 ============

function switchTab(event) {
    const tabName = event.target.dataset.tab;
    
    // 移除所有活跃状态
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.classList.remove('active');
    });
    
    // 激活选中标签页
    event.target.classList.add('active');
    document.getElementById(`${tabName}-tab`).classList.add('active');
}

// ============ AI功能 ============

async function checkAIStatus() {
    try {
        const response = await fetch(`${API_BASE}/ai/status`);
        const data = await response.json();
        
        const statusBadge = document.getElementById('ai-status');
        
        if (data.available) {
            statusBadge.textContent = '✅ AI在线';
            statusBadge.classList.remove('disabled');
            statusBadge.classList.add('enabled');
        } else {
            statusBadge.textContent = '❌ AI离线';
            statusBadge.classList.add('disabled');
            statusBadge.classList.remove('enabled');
            aiToggle.disabled = true;
            aiToggle.checked = false;
        }
    } catch (error) {
        console.error('检查AI状态失败:', error);
        document.getElementById('ai-status').textContent = '⚠️ 检查失败';
    }
}


function updateAIPanel() {
    const generateBtn = document.getElementById('generate-summary-btn');
    const hasFile = !!appState.currentFile;
    
    if (generateBtn) {
        generateBtn.disabled = !hasFile;
        if (hasFile) {
            generateBtn.title = '点击生成AI总结';
        } else {
            generateBtn.title = '请先加载文件';
        }
    }
}

// ============ 工具函数 ============

function showStatusMessage(type, message) {
    const filePanel = document.querySelector('.file-panel');
    let statusDiv = filePanel.querySelector('.status-message');
    
    if (!statusDiv) {
        statusDiv = document.createElement('div');
        statusDiv.className = 'status-message';
        filePanel.appendChild(statusDiv);
    }
    
    statusDiv.textContent = message;
    statusDiv.className = `status-message ${type}`;
    
    if (type !== 'error') {
        setTimeout(() => {
            statusDiv.className = 'status-message';
            statusDiv.style.display = 'none';
        }, 3000);
    }
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function updateFooterStatus(message) {
    document.getElementById('footer-status').textContent = message;
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}