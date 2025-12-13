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
    
    if (!filename) {
        showStatusMessage('error', '请先选择文件');
        return;
    }
    
    try {
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
        document.getElementById('export-btn').disabled = false;
        
        // 启用生成按钮
        updateAIPanel();
        
        // 加载预览筛选器
        await loadPreviewFilters();
        
        // 加载QQ列表到datalist
        await loadQQList(filename);
        
        // 异步估算Token（不阻塞UI）
        estimateTokensForFile(filename);
        
        showStatusMessage('success', data.message);
        updateFooterStatus(`已加载 ${filename}`);
        
    } catch (error) {
        console.error('加载文件失败:', error);
        showStatusMessage('error', '加载文件失败');
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

async function loadPreviewFilters() {
    if (!appState.currentFile) return;
    
    try {
        const response = await fetch(`${API_BASE}/preview/${appState.currentFile}/stats`);
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
        
        // 填充QQ筛选器
        const qqSelect = document.getElementById('preview-qq-filter');
        qqSelect.innerHTML = '<option value="">-- 所有成员 --</option>';
        data.qqs.forEach(item => {
            const option = document.createElement('option');
            option.value = item.qq;
            option.textContent = `${item.sender}(${item.qq})`;
            qqSelect.appendChild(option);
        });
        
    } catch (error) {
        console.error('加载预览数据失败:', error);
    }
}

async function loadQQList(filename) {
    /**加载QQ列表到datalist中以供选择*/
    try {
        const response = await fetch(`${API_BASE}/personal/list/${filename}`);
        const data = await response.json();
        
        if (!data.success) {
            console.error('加载QQ列表失败');
            return;
        }
        
        const datalist = document.getElementById('qq-list');
        datalist.innerHTML = '';
        
        if (data.users && data.users.length > 0) {
            data.users.forEach(user => {
                const option = document.createElement('option');
                option.value = user.qq;
                option.textContent = `${user.name}(${user.qq})`;
                datalist.appendChild(option);
            });
        }
    } catch (error) {
        console.error('加载QQ列表失败:', error);
    }
}

async function loadChatRecords() {
    if (!appState.currentFile) {
        showStatusMessage('error', '请先加载文件');
        return;
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

async function exportReport() {
    if (!appState.currentFile) {
        showStatusMessage('error', '请先加载文件');
        return;
    }
    
    const format = document.querySelector('input[name="export-format"]:checked').value;
    
    try {
        const response = await fetch(`${API_BASE}/export/${format}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                file: appState.currentFile
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showStatusMessage('success', data.message);
        } else {
            showStatusMessage('error', data.message);
        }
    } catch (error) {
        console.error('导出失败:', error);
        showStatusMessage('error', '导出失败');
    }
}
