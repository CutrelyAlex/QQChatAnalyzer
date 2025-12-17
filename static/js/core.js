/**
 * QQ聊天记录分析系统 - 核心模块
 * 全局变量、初始化、事件绑定、工具函数
 */

// ============ 全局变量 ============

let appState = {
    currentFile: null,
    fileData: null,
    aiEnabled: localStorage.getItem('ai_enabled') === 'true',
    aiOutputTokens: parseInt(localStorage.getItem('ai_output_tokens') || '4000'),
    aiContextTokens: parseInt(localStorage.getItem('ai_context_tokens') || '60000'),
    selectedQQ: null,
    members: [],
    memberIndex: {
        byId: {},
        byQQ: {},
        byName: {}
    },
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

// ============ 成员解析工具 ============

function normalizeMemberQuery(q) {
    return (q ?? '').toString().trim().toLowerCase();
}

function buildMemberIndex(users) {
    const index = { byId: {}, byQQ: {}, byName: {} };
    const list = Array.isArray(users) ? users : [];

    for (const u of list) {
        const id = (u?.id ?? '').toString().trim();
        const qq = (u?.qq ?? '').toString().trim();
        const uid = (u?.uid ?? '').toString().trim();
        // 后端可能返回 names: [历史昵称...]
        const names = Array.isArray(u?.names) ? u.names.filter(Boolean).map(x => x.toString().trim()).filter(Boolean) : [];
        const name = ((u?.name ?? '') || (names.length ? names[names.length - 1] : '')).toString().trim();
        if (!id && !qq && !name) continue;

        const normName = normalizeMemberQuery(name);
        if (id) index.byId[id] = { id, qq, uid, name, names };
        if (qq) index.byQQ[qq] = { id, qq, uid, name, names };
        if (normName) index.byName[normName] = { id, qq, uid, name, names };
    }

    return index;
}

function formatMemberDisplay(member, fallback) {
    const latestFromHistory = Array.isArray(member?.names) && member.names.length
        ? (member.names[member.names.length - 1] ?? '').toString().trim()
        : '';
    const name = (latestFromHistory || (member?.name ?? '').toString().trim() || (fallback ?? '').toString().trim());
    const qq = (member?.qq ?? '').toString().trim();
    const uid = (member?.uid ?? '').toString().trim();

    // 主展示：Name + QQ
    let main = name || qq || uid || '未知成员';
    if (qq && name) main = `${name} (${qq})`;
    else if (qq && !name) main = `QQ:${qq}`;

    // UID 小字：用于补充辨识（UI 可选择是否显示）
    const small = uid ? `uid:${uid}` : '';
    return { main, uidSmall: small };
}

function resolveMemberQuery(query) {
    const raw = (query ?? '').toString().trim();
    const q = normalizeMemberQuery(raw);
    if (!q) return { id: null, member: null };

    // 1) QQ 纯数字精确匹配
    if (/^\d{5,}$/.test(raw)) {
        const m = appState.memberIndex?.byQQ?.[raw];
        if (m?.id) return { id: m.id, member: m };
    }

    // 2) 名称精确（忽略大小写）
    const exactName = appState.memberIndex?.byName?.[q];
    if (exactName?.id) return { id: exactName.id, member: exactName };

    // 3) 模糊：名称包含 或 QQ 包含
    const list = Array.isArray(appState.members) ? appState.members : [];
    for (const u of list) {
        const name = normalizeMemberQuery(u?.name);
        const qq = (u?.qq ?? '').toString().trim();
        const id = (u?.id ?? '').toString().trim();
        if (!id) continue;
        if (name && name.includes(q)) return { id, member: u };
        if (qq && qq.includes(raw)) return { id, member: u };
    }

    return { id: null, member: null };
}

// ============ DOM小工具 ============

function getEl(id) {
    return document.getElementById(id);
}

function setText(id, text) {
    const el = getEl(id);
    if (el) el.textContent = text;
    return el;
}

function setHTML(id, html) {
    const el = getEl(id);
    if (el) el.innerHTML = html;
    return el;
}

function setDisplay(id, display) {
    const el = getEl(id);
    if (el) el.style.display = display;
    return el;
}

// ============ 初始化 ============

document.addEventListener('DOMContentLoaded', () => {
    // 初始化UI
    initializeUI();
    loadFileList();
    checkAIStatus();
    
    // 绑定事件
    bindEvents();
});

function initializeUI() {
    // UI初始化
    updateAIPanel();
    initializeSubtabs();
}

// ============ 子页签（subtabs） ============

function initializeSubtabs() {
    document.querySelectorAll('.subtabs[data-scope]').forEach(container => {
        const scope = container.getAttribute('data-scope');
        if (!scope) return;

        const tabs = Array.from(container.querySelectorAll('.subtab[data-subtab]'));
        if (!tabs.length) return;

        // 点击切换
        tabs.forEach(btn => {
            btn.addEventListener('click', () => {
                if (btn.classList.contains('is-disabled')) return;
                setActiveSubtab(scope, btn.getAttribute('data-subtab'));
            });
        });

        // 初始化：按 is-active 或第一个
        const active = tabs.find(t => t.classList.contains('is-active')) || tabs[0];
        if (active && !active.classList.contains('is-disabled')) {
            setActiveSubtab(scope, active.getAttribute('data-subtab'), { silent: true });
        }
    });
}

function setActiveSubtab(scope, subtab, opts = {}) {
    const silent = !!opts.silent;
    if (!scope || !subtab) return;

    // 激活按钮
    const container = document.querySelector(`.subtabs[data-scope="${CSS.escape(scope)}"]`);
    if (!container) return;

    const tabs = Array.from(container.querySelectorAll('.subtab[data-subtab]'));
    for (const t of tabs) {
        const key = t.getAttribute('data-subtab');
        if (key === subtab) t.classList.add('is-active');
        else t.classList.remove('is-active');
    }

    // 切换面板
    const panels = Array.from(document.querySelectorAll(`.subtab-panel[data-scope="${CSS.escape(scope)}"][data-subtab-panel]`));
    for (const p of panels) {
        const key = p.getAttribute('data-subtab-panel');
        p.hidden = key !== subtab;
    }

    if (!silent) {
        try {
            if (typeof window.onSubtabActivated === 'function') {
                window.onSubtabActivated(scope, subtab);
            }
        } catch (e) {
            // 不影响主流程
            console.warn('[Subtabs] onSubtabActivated failed:', e);
        }
    }
}

function bindEvents() {
    // 文件加载
    const loadBtn = document.getElementById('load-btn');
    if (loadBtn) loadBtn.addEventListener('click', loadFile);
    
    // 标签页切换
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.addEventListener('click', switchTab);
    });
    
    // 分析按钮
    const personalAnalyzeBtn = document.getElementById('personal-analyze-btn');
    if (personalAnalyzeBtn) personalAnalyzeBtn.addEventListener('click', analyzePersonal);
    
    const groupAnalyzeBtn = document.getElementById('group-analyze-btn');
    if (groupAnalyzeBtn) groupAnalyzeBtn.addEventListener('click', analyzeGroup);
    
    const networkAnalyzeBtn = document.getElementById('network-analyze-btn');
    if (networkAnalyzeBtn) networkAnalyzeBtn.addEventListener('click', analyzeNetwork);

    // 对比功能
    const compareRunBtn = document.getElementById('compare-run-btn');
    if (compareRunBtn) {
        compareRunBtn.addEventListener('click', () => {
            if (typeof runCompare === 'function') {
                runCompare();
            } else {
                showStatusMessage('error', '对比模块未加载');
            }
        });
    }
    
    // 导出按钮
    const exportBtn = document.getElementById('export-btn');
    if (exportBtn) exportBtn.addEventListener('click', exportReport);
    
    // 预览功能
    const previewLoadBtn = document.getElementById('preview-load-btn');
    if (previewLoadBtn) previewLoadBtn.addEventListener('click', loadChatRecords);
    
    const previewPrevBtn = document.getElementById('preview-prev-btn');
    if (previewPrevBtn) previewPrevBtn.addEventListener('click', prevPreviewPage);
    
    const previewNextBtn = document.getElementById('preview-next-btn');
    if (previewNextBtn) previewNextBtn.addEventListener('click', nextPreviewPage);
    
    // 预览筛选器重置分页
    const previewDateFilter = document.getElementById('preview-date-filter');
    if (previewDateFilter) {
        previewDateFilter.addEventListener('change', () => {
            appState.previewData.currentPage = 1;
        });
    }
    
    const previewQQFilter = document.getElementById('preview-qq-filter');
    if (previewQQFilter) {
        previewQQFilter.addEventListener('change', () => {
            appState.previewData.currentPage = 1;
        });
    }
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

    // 预览筛选器
    if (tabName === 'preview' && appState.currentFile) {
        if (typeof ensurePreviewFiltersLoaded === 'function') {
            ensurePreviewFiltersLoaded(appState.currentFile);
        }
    }
}

// ============ AI功能 ============

async function checkAIStatus() {
    try {
        const response = await fetch(`${API_BASE}/ai/status`);
        const data = await response.json();
        
        const statusBadge = getEl('ai-status');
        const aiToggle = getEl('ai-enable-toggle');
        
        if (data.available) {
            statusBadge.textContent = '✅ AI在线';
            statusBadge.classList.remove('disabled');
            statusBadge.classList.add('enabled');
        } else {
            statusBadge.textContent = '❌ AI离线';
            statusBadge.classList.add('disabled');
            statusBadge.classList.remove('enabled');
            if (aiToggle) {
                aiToggle.disabled = true;
                aiToggle.checked = false;
            }
        }
    } catch (error) {
        console.error('检查AI状态失败:', error);
        setText('ai-status', '⚠️ 检查失败');
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

// ============ 主功能区显示控制 ============

function setMainTabsVisible(visible) {
    const el = document.getElementById('main-tabs');
    if (!el) return;
    el.style.display = visible ? 'flex' : 'none';
}

// 初始：未加载文件时隐藏主功能区
document.addEventListener('DOMContentLoaded', () => {
    try {
        setMainTabsVisible(!!appState.currentFile);
    } catch (e) {
        // ignore
    }
});

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
    // 确保曾被隐藏的状态条可以重新显示
    statusDiv.style.display = 'block';

    const msg = (message ?? '').toString().trim();
    const keepInfo = type === 'info' && msg.startsWith('⏳');

    if (type !== 'error' && !keepInfo) {
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
    setText('footer-status', message);
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