/**
 * QQ聊天记录分析系统 - 热词模块 (优化版)
 * 表格形式展示热词，自动显示示例，优化加载速度
 */

// ============ 热词数据缓存 ============
const hotWordsCache = {
    examples: {},  // 缓存已加载的示例
    loading: {}    // 记录正在加载的词
};

// ============ 热词可视化 ============

/**
 * 渲染热词表格
 * @param {string} containerId - 容器元素ID
 * @param {Array} hotWords - 热词数组 [{word, count}, ...]
 */
function renderHotWords(containerId, hotWords) {
    const container = document.getElementById(containerId);
    if (!container || !hotWords || hotWords.length === 0) {
        if (container) container.innerHTML = '<span style="color: #666;">暂无热词数据</span>';
        return;
    }
    
    // 过滤掉 @昵称 的热词
    const filteredWords = filterMentionedNames(hotWords);
    
    // 排序并取前50个
    const sortedWords = filteredWords.sort((a, b) => b.count - a.count).slice(0, 50);
    
    if (sortedWords.length === 0) {
        container.innerHTML = '<span style="color: #666;">暂无热词数据</span>';
        return;
    }
    
    // 清空容器
    container.innerHTML = '';
    
    // 创建表格容器
    const tableWrapper = document.createElement('div');
    tableWrapper.className = 'hot-words-table-wrapper';
    tableWrapper.dataset.containerId = containerId;
    tableWrapper.dataset.allWords = JSON.stringify(sortedWords);
    
    // 创建表格
    const table = document.createElement('table');
    table.className = 'hot-words-table';
    
    // 表头
    const thead = document.createElement('thead');
    thead.innerHTML = `
        <tr>
            <th style="width: 10%; text-align: center;">排名</th>
            <th style="width: 25%;">热词</th>
            <th style="width: 15%; text-align: center;">出现次数</th>
            <th style="width: 50%; text-align: center;">示例预览</th>
        </tr>
    `;
    table.appendChild(thead);
    
    // 表体 - 只显示前15个
    const tbody = document.createElement('tbody');
    tbody.className = 'hot-words-tbody';
    tbody.dataset.displayLimit = 15;
    tbody.dataset.currentLimit = 15;
    
    const displayLimit = 15;
    const initialWords = sortedWords.slice(0, displayLimit);
    
    initialWords.forEach((item, index) => {
        const row = renderWordRow(item, index + 1, containerId);
        tbody.appendChild(row);
    });
    
    table.appendChild(tbody);
    tableWrapper.appendChild(table);
    container.appendChild(tableWrapper);
    
    // 添加展开按钮（如果有更多数据）
    if (sortedWords.length > displayLimit) {
        const expandBtn = document.createElement('button');
        expandBtn.className = 'expand-words-btn';
        expandBtn.textContent = `▼ 展开更多热词 (还有 ${sortedWords.length - displayLimit} 个)`;
        expandBtn.onclick = () => expandHotWordsTable(tableWrapper, sortedWords, containerId);
        container.appendChild(expandBtn);
    }
}

/**
 * 过滤掉 @昵称 的热词
 * @param {Array} hotWords - 热词数组
 * @returns {Array} - 过滤后的热词数组
 */
function filterMentionedNames(hotWords) {
    return hotWords.filter(word => {
        const w = word.word || '';
        
        // 过滤以 @ 开头的词
        if (w.startsWith('@')) {
            return false;
        }
        
        return true;
    });
}

/**
 * 渲染单行热词
 * @param {Object} item - 热词对象 {word, count}
 * @param {number} rank - 排名
 * @param {string} containerId - 容器ID
 * @returns {HTMLElement} - 表格行
 */
function renderWordRow(item, rank, containerId) {
    const row = document.createElement('tr');
    row.className = 'hot-words-row';
    row.dataset.word = item.word;
    row.dataset.containerId = containerId;
    
    // 排名列
    const rankCell = document.createElement('td');
    rankCell.textContent = rank;
    rankCell.style.textAlign = 'center';
    rankCell.style.fontWeight = 'bold';
    rankCell.style.color = rank <= 3 ? '#ff6b6b' : '#666';
    row.appendChild(rankCell);
    
    // 热词列
    const wordCell = document.createElement('td');
    wordCell.innerHTML = `<span class="word-highlight">${escapeHtml(item.word)}</span>`;
    row.appendChild(wordCell);
    
    // 次数列
    const countCell = document.createElement('td');
    countCell.textContent = item.count;
    countCell.style.textAlign = 'center';
    row.appendChild(countCell);
    
    // 示例列
    const exampleCell = document.createElement('td');
    exampleCell.className = 'examples-cell';
    exampleCell.innerHTML = '<span class="loading-text">加载中...</span>';
    row.appendChild(exampleCell);
    
    // 点击行时展开/折叠示例详情
    row.style.cursor = 'pointer';
    row.onclick = (e) => {
        if (e.target === exampleCell || e.target.parentElement === exampleCell) {
            return;  // 示例列不触发
        }
        toggleRowDetails(row);
    };
    
    // 异步加载示例（优化：使用微任务批量加载）
    loadWordExamplesAsync(item.word, exampleCell, containerId);
    
    return row;
}

/**
 * 异步加载热词示例（使用微任务优化加载速度）
 * @param {string} word - 热词
 * @param {HTMLElement} cell - 示例单元格
 * @param {string} containerId - 容器ID
 */
function loadWordExamplesAsync(word, cell, containerId) {
    // 如果已缓存，直接显示
    if (hotWordsCache.examples[word]) {
        displayExamplePreview(cell, hotWordsCache.examples[word], word);
        return;
    }
    
    // 如果已在加载，避免重复请求
    if (hotWordsCache.loading[word]) {
        return;
    }
    
    hotWordsCache.loading[word] = true;
    
    // 使用微任务优化加载序列
    queueMicrotask(() => {
        fetchWordExamples(word, containerId)
            .then(examples => {
                hotWordsCache.examples[word] = examples;
                delete hotWordsCache.loading[word];
                displayExamplePreview(cell, examples, word);
            })
            .catch(error => {
                console.error(`加载"${word}"示例失败:`, error);
                delete hotWordsCache.loading[word];
                cell.innerHTML = '<span style="color: #999; font-size: 12px;">加载失败</span>';
            });
    });
}

/**
 * 获取热词示例（API调用）
 * @param {string} word - 热词
 * @param {string} containerId - 容器ID
 * @returns {Promise<Array>} - 示例数组
 */
async function fetchWordExamples(word, containerId) {
    const isPersonal = containerId === 'personal-hot-words';

    if (!appState.currentFile) {
        return [];
    }

    // 避免对明显无意义的热词发起请求（例如纯数字）
    if (/^\d+$/.test(word)) {
        return [];
    }
    
    let url = `${API_BASE}/chat-examples?word=${encodeURIComponent(word)}&file=${encodeURIComponent(appState.currentFile)}`;
    if (isPersonal) {
        const qq = document.getElementById('qq-input')?.value;
        if (qq) {
            url += `&qq=${encodeURIComponent(qq)}`;
        }
    }
    
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`API返回 ${response.status}`);
    }
    
    const data = await response.json();
    if (!data.success || !data.examples) {
        return [];
    }
    
    return data.examples.slice(0, 4);  // 最多4条
}

/**
 * 显示示例预览
 * @param {HTMLElement} cell - 示例单元格
 * @param {Array} examples - 示例数组
 * @param {string} word - 热词
 */
function displayExamplePreview(cell, examples, word) {
    if (examples.length === 0) {
        cell.innerHTML = '<span style="color: #999; font-size: 12px;">无示例</span>';
        return;
    }
    
    // 只显示第一条作为预览
    const first = examples[0];
    const preview = `${first.sender}: ${escapeHtml(first.content).substring(0, 30)}${escapeHtml(first.content).length > 30 ? '...' : ''}`;
    
    cell.innerHTML = `<span class="example-preview" title="点击查看全部示例">${preview}</span>`;
    
    // 点击预览显示所有示例
    cell.querySelector('.example-preview').onclick = (e) => {
        e.stopPropagation();
        showExamplesInline(cell, examples, word);
    };
}

/**
 * 在单元格内显示所有示例
 * @param {HTMLElement} cell - 示例单元格
 * @param {Array} examples - 示例数组
 * @param {string} word - 热词
 */
function showExamplesInline(cell, examples, word) {
    const isExpanded = cell.dataset.expanded === 'true';
    
    if (isExpanded) {
        // 收起
        cell.dataset.expanded = 'false';
        displayExamplePreview(cell, examples, word);
        return;
    }
    
    // 展开显示所有示例
    cell.dataset.expanded = 'true';
    let html = `<div class="examples-inline"><div class="examples-inline-title">📝 "${escapeHtml(word)}" 的聊天示例：</div>`;
    
    examples.forEach((example, index) => {
        html += `
            <div class="inline-example-item">
                <div class="inline-example-meta">
                    <span class="inline-example-sender">${escapeHtml(example.sender)}</span>
                    <span class="inline-example-time">${escapeHtml(example.timestamp)}</span>
                </div>
                <div class="inline-example-content">${escapeHtml(example.content)}</div>
            </div>
        `;
    });
    
    html += '</div>';
    cell.innerHTML = html;
    
    // 点击收起
    cell.querySelector('.examples-inline').onclick = (e) => {
        e.stopPropagation();
        showExamplesInline(cell, examples, word);
    };
}

/**
 * 展开表格显示更多热词
 * @param {HTMLElement} tableWrapper - 表格容器
 * @param {Array} sortedWords - 全部热词
 * @param {string} containerId - 容器ID
 */
function expandHotWordsTable(tableWrapper, sortedWords, containerId) {
    const tbody = tableWrapper.querySelector('tbody');
    const currentLimit = parseInt(tbody.dataset.currentLimit);
    const newLimit = Math.min(currentLimit + 5, sortedWords.length);
    
    // 添加新行
    for (let i = currentLimit; i < newLimit; i++) {
        const item = sortedWords[i];
        const row = renderWordRow(item, i + 1, containerId);
        tbody.appendChild(row);
    }
    
    tbody.dataset.currentLimit = newLimit;
    
    // 更新或移除展开按钮
    const container = document.getElementById(containerId);
    const expandBtn = container.querySelector('.expand-words-btn');
    
    if (newLimit >= sortedWords.length) {
        if (expandBtn) expandBtn.remove();
    } else {
        const remaining = sortedWords.length - newLimit;
        expandBtn.textContent = `▼ 展开更多热词 (还有 ${remaining} 个)`;
    }
}

/**
 * 切换行详情展开/收起
 * @param {HTMLElement} row - 表格行
 */
function toggleRowDetails(row) {
    row.classList.toggle('expanded');
}

/**
 * 清空热词缓存（在新的分析开始时调用）
 */
function clearHotWordsCache() {
    hotWordsCache.examples = {};
    hotWordsCache.loading = {};
}
