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
        
        // 加载成员列表到 datalist（QQ号/昵称）
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
