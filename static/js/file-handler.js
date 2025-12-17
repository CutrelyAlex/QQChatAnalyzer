/**
 * QQ聊天记录分析系统 - 文件处理模块
 * 文件加载、预览、导出等功能
 */

// ============ 文件管理 ============

async function loadFileList() {
    try {
        const response = await fetch(`${API_BASE}/files`);
        const data = await response.json();
        
        if (!data.success) {
            showStatusMessage('error', '无法加载文件列表');
            return;
        }
        
        const fileSelect = document.getElementById('file-select');
        fileSelect.innerHTML = '<option value="">-- 选择文件 --</option>';
        
        data.files.forEach(file => {
            const option = document.createElement('option');
            option.value = file.name;
            option.textContent = `${file.name} (${formatFileSize(file.size)})`;
            fileSelect.appendChild(option);
        });
        
    } catch (error) {
        console.error('加载文件列表失败:', error);
        showStatusMessage('error', '加载文件列表失败');
    }
}

async function loadFile() {
    const fileSelect = document.getElementById('file-select');
    const filename = fileSelect.value;
    const loadBtn = document.getElementById('load-btn');
    
    if (!filename) {
        showStatusMessage('error', '请先选择文件');
        return;
    }
    
    try {
        // 加载中：隐藏主功能区，避免用户误操作
        if (typeof setMainTabsVisible === 'function') {
            setMainTabsVisible(false);
        }
        if (loadBtn) {
            loadBtn.disabled = true;
            loadBtn.classList.add('is-loading');
        }
        showStatusMessage('info', '⏳ 正在加载文件，请稍候...');

        const response = await fetch(`${API_BASE}/load`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename })
        });
        
        const data = await response.json();
        
        if (!data.success) {
            showStatusMessage('error', data.error);
            return;
        }
        
        appState.currentFile = filename;
        
        // 更新UI
        document.getElementById('loaded-file').textContent = `✅ 已加载: ${filename} (${data.size_mb}MB)`;
        document.getElementById('personal-analyze-btn').disabled = false;
        document.getElementById('group-analyze-btn').disabled = false;
        document.getElementById('network-analyze-btn').disabled = false;

        // 文件加载完成后显示主功能区
        if (typeof setMainTabsVisible === 'function') {
            setMainTabsVisible(true);
        }
        
        // 启用生成按钮
        updateAIPanel();

        // 标记预览筛选器为“未加载”（切换文件时必须重新加载）
        markPreviewFiltersStale(filename);

        // 加载成员列表到 datalist（QQ号/昵称）
        await loadQQList(filename);
        
        // 异步估算Token（不阻塞UI）
        estimateTokensForFile(filename);
        
        showStatusMessage('success', data.message);
        updateFooterStatus(`已加载 ${filename}`);
        
    } catch (error) {
        console.error('加载文件失败:', error);
        showStatusMessage('error', '加载文件失败');
    } finally {
        if (loadBtn) {
            loadBtn.disabled = false;
            loadBtn.classList.remove('is-loading');
        }
    }
}

/**
 * 估算文件的Token数
 * @param {string} filename - 文件名
 */
async function estimateTokensForFile(filename) {
    try {
        const payload = { filename: filename };
        // 这里的 max_tokens 指“输入聊天采样预算”，对应后端的 DataPruner.max_tokens
        if (typeof appState.aiContextTokens === 'number') {
            payload.max_tokens = appState.aiContextTokens;
        }

        const response = await fetch(`${API_BASE}/ai/token-estimate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ...payload
            })
        });
        
        if (!response.ok) {
            return;
        }
        
        const result = await response.json();
        
        if (result.success && result.estimate) {
            // 保存估算信息供AI配置使用
            appState.tokenEstimate = result.estimate;
            // Token估算完成（日志移除：避免控制台噪音）
        }
    } catch (error) {
        console.error('估算Token时出错:', error);
        // 不显示错误，静默失败
    }
}

// ============ 聊天记录预览 ============

function markPreviewFiltersStale(_filename) {
    appState.previewFiltersLoadedForFile = null;
    appState.previewFiltersLoadingPromise = null;
}

async function ensurePreviewFiltersLoaded(filename) {
    const file = filename || appState.currentFile;
    if (!file) return;

    if (appState.previewFiltersLoadedForFile === file) return;
    if (appState.previewFiltersLoadingPromise) return appState.previewFiltersLoadingPromise;

    // UI：显示“加载中”并禁用筛选器，避免用户误操作
    const dateSelect = document.getElementById('preview-date-filter');
    const qqSelect = document.getElementById('preview-qq-filter');
    if (dateSelect) {
        dateSelect.disabled = true;
        dateSelect.innerHTML = '<option value="">-- 加载中... --</option>';
    }
    if (qqSelect) {
        qqSelect.disabled = true;
        qqSelect.innerHTML = '<option value="">-- 加载中... --</option>';
    }

    const p = (async () => {
        try {
            await loadPreviewFilters(file);
        } finally {
            appState.previewFiltersLoadingPromise = null;
            // 仅当仍是当前文件时，恢复 UI 状态
            if (appState.currentFile === file) {
                if (dateSelect) dateSelect.disabled = false;
                if (qqSelect) qqSelect.disabled = false;
            }
        }
    })();

    appState.previewFiltersLoadingPromise = p;
    return p;
}

async function loadPreviewFilters(filename) {
    const file = filename || appState.currentFile;
    if (!file) return;
    
    try {
        const response = await fetch(`${API_BASE}/preview/${file}/stats`);
        const data = await response.json();
        
        if (!data.success) {
            console.error('加载预览数据失败');
            return;
        }
        
        // 填充日期筛选器
        const dateSelect = document.getElementById('preview-date-filter');
        dateSelect.innerHTML = '<option value="">-- 所有日期 --</option>';
        data.dates.forEach(date => {
            const option = document.createElement('option');
            option.value = date;
            option.textContent = date;
            dateSelect.appendChild(option);
        });
        
        // 填充成员筛选器（QQ号/昵称）
        const qqSelect = document.getElementById('preview-qq-filter');
        qqSelect.innerHTML = '<option value="">-- 所有成员 --</option>';
        data.qqs.forEach(item => {
            const option = document.createElement('option');
            option.value = item.qq;
            const sender = (item.sender || '').toString().trim();
            option.textContent = sender && sender !== item.qq ? `${sender}(${item.qq})` : `QQ:${item.qq}`;
            qqSelect.appendChild(option);
        });

        // 仅当 still-current 时记录已加载（避免快速切文件导致串数据）
        if (appState.currentFile === file) {
            appState.previewFiltersLoadedForFile = file;
        }
        
    } catch (error) {
        console.error('加载预览数据失败:', error);
    }
}

async function loadQQList(filename) {
    /**加载成员列表到 datalist 中以供选择（QQ号/昵称）*/
    try {
        const response = await fetch(`${API_BASE}/personal/list/${filename}`);
        const data = await response.json();
        
        if (!data.success) {
            console.error('加载成员列表失败');
            return;
        }
        
        const datalist = document.getElementById('qq-list');
        datalist.innerHTML = '';

        // 保存到全局索引：用于“输入QQ或昵称 -> internal id” 的解析
        if (Array.isArray(data.users)) {
            appState.members = data.users;
            if (typeof buildMemberIndex === 'function') {
                appState.memberIndex = buildMemberIndex(data.users);
            }
        }
        
        if (data.users && data.users.length > 0) {
            data.users.forEach(user => {
                const qq = (user.qq || '').toString().trim();
                const name = (user.name || '').toString().trim();

                // 1) 以昵称作为主要可选值（更符合“默认检索用昵称”）
                if (name) {
                    const optionByName = document.createElement('option');
                    optionByName.value = name;
                    optionByName.textContent = qq ? `${name}(${qq})` : name;
                    datalist.appendChild(optionByName);
                }

                // 2) 同时保留 QQ 作为可选值（方便输入数字快速定位）
                if (qq && qq !== name) {
                    const optionByQQ = document.createElement('option');
                    optionByQQ.value = qq;
                    optionByQQ.textContent = name ? `${name}(${qq})` : `QQ:${qq}`;
                    datalist.appendChild(optionByQQ);
                }
            });
        }
    } catch (error) {
        console.error('加载成员列表失败:', error);
    }
}

async function loadChatRecords() {
    if (!appState.currentFile) {
        showStatusMessage('error', '请先加载文件');
        return;
    }

    // 懒加载预览筛选器（首次进入预览时才拉 stats）
    if (typeof ensurePreviewFiltersLoaded === 'function') {
        await ensurePreviewFiltersLoaded(appState.currentFile);
    }
    
    const dateFilter = document.getElementById('preview-date-filter');
    const qqFilter = document.getElementById('preview-qq-filter');
    const filterType = dateFilter.value ? 'date' : (qqFilter.value ? 'qq' : 'all');
    const filterValue = dateFilter.value || qqFilter.value || '';
    
    try {
        let url = `${API_BASE}/preview/${appState.currentFile}?page=${appState.previewData.currentPage}&page_size=${appState.previewData.pageSize}`;
        if (filterType !== 'all') {
            url += `&filter_type=${filterType}&filter_value=${filterValue}`;
        }
        
        const response = await fetch(url);
        const data = await response.json();
        
        if (!data.success) {
            showStatusMessage('error', '加载失败');
            return;
        }
        
        appState.previewData.totalRecords = data.total;
        appState.previewData.totalPages = data.total_pages;
        
        displayChatRecords(data.records);
        updatePreviewPagination(data);
        
    } catch (error) {
        console.error('加载聊天记录失败:', error);
        showStatusMessage('error', '加载聊天记录失败');
    }
}

function displayChatRecords(records) {
    const tbody = document.getElementById('preview-records-body');
    tbody.innerHTML = '';
    
    if (records.length === 0) {
        document.getElementById('preview-records').style.display = 'none';
        document.getElementById('preview-empty').style.display = 'block';
        document.getElementById('preview-pagination').style.display = 'none';
        document.getElementById('preview-stats').style.display = 'none';
        return;
    }
    
    document.getElementById('preview-records').style.display = 'block';
    document.getElementById('preview-empty').style.display = 'none';
    document.getElementById('preview-pagination').style.display = 'flex';
    document.getElementById('preview-stats').style.display = 'block';
    
    records.forEach(record => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="record-time">${record.timestamp}</td>
            <td>
                <div class="record-sender">${record.sender}</div>
                <div class="record-qq">${record.qq}</div>
            </td>
            <td class="record-content">${escapeHtml(record.content)}</td>
        `;
        tbody.appendChild(row);
    });
}

function updatePreviewPagination(data) {
    // """更新分页信息"""
    document.getElementById('preview-total').textContent = data.total;
    document.getElementById('preview-current-page').textContent = data.page;
    document.getElementById('preview-total-pages').textContent = data.total_pages;
    document.getElementById('preview-page-info').textContent = `第 ${data.page} / ${data.total_pages} 页`;
    
    document.getElementById('preview-prev-btn').disabled = data.page <= 1;
    document.getElementById('preview-next-btn').disabled = data.page >= data.total_pages;
}

function nextPreviewPage() {
    //"""下一页"""
    if (appState.previewData.currentPage < appState.previewData.totalPages) {
        appState.previewData.currentPage++;
        loadChatRecords();
    }
}

function prevPreviewPage() {
    // """上一页"""
    if (appState.previewData.currentPage > 1) {
        appState.previewData.currentPage--;
        loadChatRecords();
    }
}

// ============ 报告导出 ============

const exportYearSummary = {
    cacheList: [],
    selectedCache: null, // {id, filename, created_at, ...}
    hotWords: [], // [{word,count}]
    selectedWords: new Set(),
};

function _getExportTemplate() {
    // UI 已简化：仅支持年度总结
    return 'group_year_summary';
}

function _setExportYearSummaryVisible(visible) {
    const box = document.getElementById('export-year-summary-config');
    if (box) box.style.display = visible ? 'block' : 'none';
}

function _renderExportYearHotwords() {
    const container = document.getElementById('export-year-hotwords');
    if (!container) return;

    if (!exportYearSummary.selectedCache) {
        container.innerHTML = '<div style="color: #999; grid-column: 1 / -1;">请先选择群体分析缓存</div>';
        return;
    }

    if (!exportYearSummary.hotWords.length) {
        container.innerHTML = '<div style="color: #999; grid-column: 1 / -1;">该缓存未包含热词数据（hot_words）</div>';
        return;
    }

    container.innerHTML = exportYearSummary.hotWords
        .map((it, idx) => {
            const word = (it?.word ?? '').toString();
            const count = Number(it?.count ?? 0);
            const checked = exportYearSummary.selectedWords.has(word) ? 'checked' : '';
            const id = `export-hotword-${idx}`;
            return `
                <label for="${id}" class="checkbox-item" style="display:flex; align-items:center; gap:8px; padding:8px 10px; border:1px solid #eee; border-radius:10px; background:#fff;">
                    <input id="${id}" type="checkbox" data-word="${escapeHtml(word)}" ${checked}>
                    <span style="flex:1; min-width:0;">${escapeHtml(word)}</span>
                    <small style="color:#999; font-variant-numeric: tabular-nums;">${Number.isFinite(count) ? count : 0}</small>
                </label>
            `;
        })
        .join('');

    // bind
    container.querySelectorAll('input[type="checkbox"][data-word]').forEach(cb => {
        cb.addEventListener('change', (e) => {
            const w = (e.target?.dataset?.word || '').toString();
            if (!w) return;
            const want = !!e.target.checked;
            if (want) {
                if (exportYearSummary.selectedWords.size >= 8) {
                    e.target.checked = false;
                    showStatusMessage('error', '最多只能选择 8 个热词');
                    return;
                }
                exportYearSummary.selectedWords.add(w);
            } else {
                exportYearSummary.selectedWords.delete(w);
            }
            _updateExportYearSelectedCount();
            _updateExportButtonState();
        });
    });
}

function _updateExportYearSelectedCount() {
    const el = document.getElementById('export-year-selected-count');
    if (!el) return;
    el.textContent = `已选择 ${exportYearSummary.selectedWords.size} / 8`;
}

function _updateExportButtonState() {
    const btn = document.getElementById('export-btn');
    if (!btn) return;

    const ok = !!exportYearSummary.selectedCache && exportYearSummary.selectedWords.size === 8;
    btn.disabled = !ok;
    btn.title = ok ? '' : '请选择群体分析缓存并勾选 8 个热词';
}

function _setExportBusy(isBusy, message) {
    const btn = document.getElementById('export-btn');
    const status = document.getElementById('export-status');

    if (btn) {
        if (!btn.dataset.defaultText) {
            btn.dataset.defaultText = (btn.textContent || '').toString();
        }

        if (isBusy) {
            btn.disabled = true;
            btn.classList.add('is-loading');
            btn.textContent = '⏳ 正在导出...';
            btn.title = '正在导出，请稍候...';
        } else {
            btn.classList.remove('is-loading');
            btn.textContent = btn.dataset.defaultText || '📥 导出年度总结（HTML）';
            // 恢复基于选择条件的可用状态
            _updateExportButtonState();
        }
    }

    if (status) {
        const msg = (message || '').toString();
        status.textContent = msg;
        status.className = 'status-message' + (isBusy ? ' info' : '');
        status.style.display = msg ? 'block' : 'none';
    }
}

async function _loadGroupCacheList() {
    const sel = document.getElementById('export-group-cache');
    if (!sel) return;

    sel.innerHTML = '<option value="">-- 加载中... --</option>';

    try {
        const resp = await fetch(`${API_BASE}/analysis/cache/list`);
        const data = await resp.json();
        if (!data.success) {
            sel.innerHTML = '<option value="">-- 加载失败 --</option>';
            return;
        }

        exportYearSummary.cacheList = (data.cache_list || []).filter(x => x?.type === 'group');
        sel.innerHTML = '<option value="">-- 请选择群体分析缓存 --</option>';
        exportYearSummary.cacheList.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c.id;
            opt.textContent = c.display_name || `${c.filename || '未知文件'} (group)`;
            sel.appendChild(opt);
        });

        if (!exportYearSummary.cacheList.length) {
            const meta = document.getElementById('export-year-cache-meta');
            if (meta) meta.textContent = '暂无群体分析缓存：请先在「群体分析」页分析并保存分析数据。';
        }
    } catch (e) {
        console.error('[Export] Failed to load cache list:', e);
        sel.innerHTML = '<option value="">-- 加载失败 --</option>';
    }
}

async function _loadGroupCacheDetail(cacheId) {
    const meta = document.getElementById('export-year-cache-meta');
    if (meta) meta.textContent = '';

    exportYearSummary.selectedCache = null;
    exportYearSummary.hotWords = [];
    exportYearSummary.selectedWords = new Set();
    _updateExportYearSelectedCount();

    if (!cacheId) {
        _renderExportYearHotwords();
        _updateExportButtonState();
        return;
    }

    try {
        const resp = await fetch(`${API_BASE}/analysis/load/${encodeURIComponent(cacheId)}`);
        const data = await resp.json();
        if (!data.success) {
            showStatusMessage('error', data.error || '加载缓存失败');
            _renderExportYearHotwords();
            _updateExportButtonState();
            return;
        }

        exportYearSummary.selectedCache = {
            id: cacheId,
            type: data.type,
            filename: data.filename,
        };
        const stats = (data?.data?.group_stats && typeof data.data.group_stats === 'object')
            ? data.data.group_stats
            : (data?.data && typeof data.data === 'object')
                ? data.data
                : null;
        exportYearSummary.hotWords = Array.isArray(stats?.hot_words) ? stats.hot_words : [];

        if (meta) {
            meta.textContent = `已选缓存文件：${data.filename || '-'}（热词 ${exportYearSummary.hotWords.length} 个）`;
        }

        _renderExportYearHotwords();
        _updateExportButtonState();
    } catch (e) {
        console.error('[Export] Failed to load cache:', e);
        showStatusMessage('error', '加载缓存失败');
        _renderExportYearHotwords();
        _updateExportButtonState();
    }
}

function initExportTabEnhancements() {
    _setExportYearSummaryVisible(true);

    document.getElementById('export-year-refresh')?.addEventListener('click', async () => {
        await _loadGroupCacheList();
    });

    document.getElementById('export-group-cache')?.addEventListener('change', async (e) => {
        await _loadGroupCacheDetail(e.target.value);
    });

    document.getElementById('export-year-auto-pick')?.addEventListener('click', () => {
        exportYearSummary.selectedWords = new Set();
        (exportYearSummary.hotWords || []).slice(0, 8).forEach(it => {
            const w = (it?.word ?? '').toString().trim();
            if (w) exportYearSummary.selectedWords.add(w);
        });
        _renderExportYearHotwords();
        _updateExportYearSelectedCount();
        _updateExportButtonState();
    });

    document.getElementById('export-year-clear')?.addEventListener('click', () => {
        exportYearSummary.selectedWords = new Set();
        _renderExportYearHotwords();
        _updateExportYearSelectedCount();
        _updateExportButtonState();
    });

    document.getElementById('export-btn')?.addEventListener('click', async () => {
        await exportReport();
    });

    // init
    _loadGroupCacheList();
    _renderExportYearHotwords();
    _updateExportYearSelectedCount();
    _updateExportButtonState();
}

async function exportReport() {
    // 年度总结：从缓存导出，不强制要求当前文件已加载
    if (!exportYearSummary.selectedCache?.id) {
        showStatusMessage('error', '请先选择群体分析缓存');
        return;
    }
    if (exportYearSummary.selectedWords.size !== 8) {
        showStatusMessage('error', '请恰好选择 8 个热词');
        return;
    }

    try {
        _setExportBusy(true, '⏳ 正在导出年度总结（HTML），请稍候...');
        const response = await fetch(`${API_BASE}/export/html`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                template: 'group_year_summary',
                cache_id: exportYearSummary.selectedCache.id,
                words: Array.from(exportYearSummary.selectedWords),
            })
        });

        const contentType = (response.headers.get('content-type') || '').toLowerCase();
        if (contentType.includes('application/json')) {
            const data = await response.json();
            showStatusMessage('error', data.error || data.message || '导出失败');
            _setExportBusy(false, data.error || data.message || '导出失败');
            return;
        }

        if (!response.ok) {
            showStatusMessage('error', `导出失败（HTTP ${response.status}）`);
            _setExportBusy(false, `导出失败（HTTP ${response.status}）`);
            return;
        }

        const blob = await response.blob();
        const cd = response.headers.get('content-disposition') || '';
        let filename = '群聊年度总结.html';
        const m = cd.match(/filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i);
        if (m) {
            filename = decodeURIComponent(m[1] || m[2] || filename);
        }

        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);

        showStatusMessage('success', '年度总结已导出（HTML）');
        _setExportBusy(false, '✅ 已导出（HTML），如未弹出下载请检查浏览器下载设置/拦截。');
    } catch (error) {
        console.error('导出失败:', error);
        showStatusMessage('error', '导出失败');
        _setExportBusy(false, '❌ 导出失败：网络或服务异常（请重试，或查看控制台/Network 详情）');
    } finally {
        // 如果中途 return 已恢复状态，这里不会影响；否则确保按钮不一直处于 busy
        // 注意：_setExportBusy(false) 会按当前选择恢复按钮是否可用
        _setExportBusy(false, document.getElementById('export-status')?.textContent || '');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    try {
        initExportTabEnhancements();
    } catch (e) {
        console.warn('[Export] init failed:', e);
    }
});
