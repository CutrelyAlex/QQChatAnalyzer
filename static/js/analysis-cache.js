/**
 * 分析数据缓存管理模块
 * 支持保存、加载和管理分析数据
 * AI总结必须依赖缓存数据，不再支持实时分析
 */

const analysisCacheManager = {
    // 缓存列表
    cacheList: [],
    // 当前选中的缓存
    selectedCache: null,
    
    // 初始化缓存管理
    async init() {
        await this.loadCacheList();
        this.setupGenerateButton();
    },
    
    // 加载缓存列表
    async loadCacheList() {
        try {
            const response = await fetch('/api/analysis/cache/list');
            const data = await response.json();
            
            if (data.success) {
                this.cacheList = data.cache_list;              
                this.renderCacheUI();
            }
        } catch (error) {
            console.error('[Cache] Failed to load cache list:', error);
        }
    },
    
    // 设置生成按钮逻辑
    setupGenerateButton() {
        const generateBtn = document.getElementById('generate-summary-btn');
        if (!generateBtn) return;
        
        // 默认禁用，必须选择缓存才能生成
        generateBtn.disabled = true;
        generateBtn.title = '请先选择一个缓存的分析数据';
        
        // 更新按钮文本
        generateBtn.innerHTML = '⚠️ 请先选择缓存数据';
    },
    
    // 渲染缓存UI
    renderCacheUI() {
        const cacheListDiv = document.getElementById('analysis-cache-list');
        if (!cacheListDiv) return;
        
        if (this.cacheList.length === 0) {
            cacheListDiv.innerHTML = `
                <div style="text-align: center; padding: 20px; color: #999;">
                    <p>📭 暂无缓存分析数据</p>
                    <p style="font-size: 12px; margin-top: 10px;">
                        请先到「个人分析」「群体分析」或「社交网络」页面进行分析，<br>
                        分析完成后点击「保存分析数据」按钮
                    </p>
                </div>
            `;
            return;
        }
        
        // 按文件名分组缓存
        const fileGroups = {};
        for (const cache of this.cacheList) {
            const filename = cache.filename || '未知文件';
            if (!fileGroups[filename]) {
                fileGroups[filename] = { personal: [], group: null, network: null };
            }
            if (cache.type === 'personal') {
                fileGroups[filename].personal.push(cache);
            } else if (cache.type === 'group') {
                fileGroups[filename].group = cache;
            } else if (cache.type === 'network') {
                fileGroups[filename].network = cache;
            }
        }
        
        let html = '<div class="cache-groups">';
        
        for (const [filename, caches] of Object.entries(fileGroups)) {
            const hasGroup = caches.group !== null;
            const hasNetwork = caches.network !== null;
            const hasBoth = hasGroup && hasNetwork;
            
            html += `<div class="cache-file-group">`;
            html += `<div class="cache-file-header">📁 ${filename}</div>`;
            
            // 如果同时有群体分析和网络分析，显示合并生成选项
            if (hasBoth) {
                html += `
                    <div class="cache-item merged-option" data-filename="${filename}" data-group-id="${caches.group.id}" data-network-id="${caches.network.id}">
                        <div class="cache-info">
                            <div class="cache-name">
                                <span class="cache-type-badge type-merged">🎯 群体+网络 综合分析</span>
                                完整社交报告
                            </div>
                            <div class="cache-meta">
                                <span>👥 群体分析 + 🕸️ 网络分析</span>
                            </div>
                        </div>
                        <div class="cache-actions">
                            <button class="btn btn-primary btn-small merged-generate-btn" data-group-id="${caches.group.id}" data-network-id="${caches.network.id}">
                                ✨ 生成综合报告
                            </button>
                        </div>
                    </div>
                `;
            }
            
            // 显示群体分析缓存
            if (hasGroup) {
                const cache = caches.group;
                const createdDate = new Date(cache.created_at).toLocaleString('zh-CN');
                html += this._renderCacheItem(cache, createdDate, !hasBoth);
            }
            
            // 显示网络分析缓存
            if (hasNetwork) {
                const cache = caches.network;
                const createdDate = new Date(cache.created_at).toLocaleString('zh-CN');
                html += this._renderCacheItem(cache, createdDate, !hasBoth);
            }
            
            // 显示个人分析缓存
            for (const cache of caches.personal) {
                const createdDate = new Date(cache.created_at).toLocaleString('zh-CN');
                html += this._renderCacheItem(cache, createdDate, true);
            }
            
            html += `</div>`;
        }
        
        html += '</div>';
        cacheListDiv.innerHTML = html;
        
        // 绑定按钮事件
        this.attachCacheButtonListeners();
    },
    
    // 渲染单个缓存项
    _renderCacheItem(cache, createdDate, showGenerateBtn = true) {
        const sizeKB = (cache.file_size / 1024).toFixed(2);
        const typeLabel = this.getTypeLabel(cache.type);
        const typeClass = cache.type === 'personal' ? 'type-personal' : 'type-group';
        
        return `
            <div class="cache-item" data-cache-id="${cache.id}" data-cache-type="${cache.type}">
                <div class="cache-info">
                    <div class="cache-name">
                        <span class="cache-type-badge ${typeClass}">${typeLabel}</span>
                        ${cache.display_name}
                    </div>
                    <div class="cache-meta">
                        <span>📅 ${createdDate}</span>
                        <span>💾 ${sizeKB} KB</span>
                    </div>
                </div>
                <div class="cache-actions">
                    ${showGenerateBtn ? `
                    <button class="btn btn-secondary btn-small use-cache-btn" data-cache-id="${cache.id}" data-cache-type="${cache.type}">
                        ✨ 单独生成
                    </button>
                    ` : ''}
                    <button class="btn btn-danger btn-small delete-cache-btn" data-cache-id="${cache.id}">
                        🗑️
                    </button>
                </div>
            </div>
        `;
    },
    
    // 获取类型标签
    getTypeLabel(type) {
        switch (type) {
            case 'personal': return '👤 个人';
            case 'group': return '👥 群体';
            case 'network': return '🕸️ 网络';
            default: return type;
        }
    },
    
    // 绑定缓存按钮事件
    attachCacheButtonListeners() {
        // 单独生成按钮
        document.querySelectorAll('.use-cache-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const cacheId = e.target.dataset.cacheId;
                const cacheType = e.target.dataset.cacheType;
                await this.generateFromCache(cacheId, cacheType);
            });
        });
        
        // 合并生成按钮（群体+网络）
        document.querySelectorAll('.merged-generate-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const groupId = e.target.dataset.groupId;
                const networkId = e.target.dataset.networkId;
                await this.generateMergedSummary(groupId, networkId);
            });
        });
        
        // 删除按钮
        document.querySelectorAll('.delete-cache-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const cacheId = e.target.dataset.cacheId;
                await this.deleteCache(cacheId);
            });
        });
    },
    
    // 合并生成群体+网络综合报告
    async generateMergedSummary(groupCacheId, networkCacheId) {
        // 检查AI是否启用
        if (typeof appState !== 'undefined' && !appState.aiEnabled) {
            showConfigStatus('❌ 请先启用AI功能', 'error');
            return;
        }
        
        // 高亮选中的合并选项
        document.querySelectorAll('.cache-item').forEach(item => {
            item.classList.remove('selected');
        });
        const selectedItem = document.querySelector(`[data-group-id="${groupCacheId}"][data-network-id="${networkCacheId}"]`);
        if (selectedItem) {
            selectedItem.classList.add('selected');
        }
        
        showConfigStatus('🚀 正在合并群体分析和网络分析数据，生成综合报告...', 'info');
        
        // 调用合并生成API
        await generateMergedSummaryFromCache(groupCacheId, networkCacheId);
    },
    
    // 从缓存生成AI总结（单独）
    async generateFromCache(cacheId, cacheType) {
        const cache = this.cacheList.find(c => c.id === cacheId);
        if (!cache) {
            showConfigStatus('❌ 找不到缓存数据', 'error');
            return;
        }
        
        // 检查AI是否启用
        if (typeof appState !== 'undefined' && !appState.aiEnabled) {
            showConfigStatus('❌ 请先启用AI功能', 'error');
            return;
        }
        
        // 高亮选中的缓存
        document.querySelectorAll('.cache-item').forEach(item => {
            item.classList.remove('selected');
        });
        const selectedItem = document.querySelector(`[data-cache-id="${cacheId}"]`);
        if (selectedItem) {
            selectedItem.classList.add('selected');
        }
        
        // 存储缓存ID和类型
        sessionStorage.setItem('selected_cache_id', cacheId);
        sessionStorage.setItem('selected_cache_type', cacheType);
        
        // 设置正确的分析类型
        const targetSelect = document.getElementById('summary-target-select');
        if (targetSelect) {
            // 将缓存类型直接映射到目标选择
            if (cacheType === 'personal') {
                targetSelect.value = 'personal';
            } else if (cacheType === 'group') {
                targetSelect.value = 'group';
            } else if (cacheType === 'network') {
                targetSelect.value = 'group';  // 网络分析也作为群体总结处理
            }
        }
        
        showConfigStatus(`🚀 正在使用缓存生成AI总结: ${cache.display_name}`, 'info');
        
        // 直接触发生成
        await generateSummaryFromCache(cacheId, cacheType);
    },
    
    // 删除缓存
    async deleteCache(cacheId) {
        if (!confirm('确定要删除这个缓存吗？')) return;
        
        try {
            const response = await fetch(`/api/analysis/delete/${cacheId}`, {
                method: 'DELETE'
            });
            const data = await response.json();
            
            if (data.success) {
                showConfigStatus('✅ 缓存已删除', 'success');
                // 清除选中状态
                if (sessionStorage.getItem('selected_cache_id') === cacheId) {
                    sessionStorage.removeItem('selected_cache_id');
                    sessionStorage.removeItem('selected_cache_type');
                }
                await this.loadCacheList();
            } else {
                showConfigStatus('❌ 删除失败: ' + data.error, 'error');
            }
        } catch (error) {
            console.error('[Cache] Delete failed:', error);
            showConfigStatus('❌ 删除失败', 'error');
        }
    },
    
    // 保存分析数据到缓存
    async saveAnalysis(type, filename, data, qq, nickname) {
        try {
            showConfigStatus('💾 正在保存分析数据...', 'info');
            
            const response = await fetch('/api/analysis/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    type,
                    filename,
                    data,
                    qq: qq || '',
                    nickname: nickname || ''
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                showConfigStatus(`✅ ${result.message}`, 'success');
                await this.loadCacheList();
                return true;
            } else {
                showConfigStatus(`❌ 保存失败: ${result.error}`, 'error');
                return false;
            }
        } catch (error) {
            console.error('[Cache] Save failed:', error);
            showConfigStatus('❌ 保存失败', 'error');
            return false;
        }
    }
};

// ============ 从缓存生成AI总结 ============

function getAiGenerationParamsForCache() {
    // 与 config.js 的 aiConfig 保持一致；analysis-cache.js 先加载，但调用时 window.aiConfig 应已存在
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

async function generateSummaryFromCache(cacheId, cacheType) {
    if (!cacheId) {
        showConfigStatus('❌ 未选择缓存数据', 'error');
        return;
    }
    
    // 检查AI配置
    if (typeof appState !== 'undefined' && !appState.aiEnabled) {
        showConfigStatus('❌ 请先启用AI功能', 'error');
        return;
    }
    
    try {
        // 显示进度
        const progressContainer = document.getElementById('generation-progress-container');
        const successContainer = document.getElementById('generation-success-container');
        const errorContainer = document.getElementById('generation-error-container');
        
        if (progressContainer) progressContainer.style.display = 'block';
        if (successContainer) successContainer.style.display = 'none';
        if (errorContainer) errorContainer.style.display = 'none';
        
        const progressStep = document.getElementById('progress-step');
        if (progressStep) progressStep.textContent = '正在从缓存加载数据...';
        
        // 构建请求数据
        const requestData = {
            type: cacheType,
            cache_id: cacheId,
            max_tokens: appState?.aiOutputTokens || 4000,
            context_budget: appState?.aiContextTokens || 60000,
            ...getAiGenerationParamsForCache()
        };
        
        // 调用流式API
        if (progressStep) progressStep.textContent = '正在生成AI总结...';
        
        const response = await fetch('/api/ai/summary/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestData)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        // 处理流式响应
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullContent = '';
        
        const streamDiv = document.getElementById('generation-stream');
        if (streamDiv) {
            streamDiv.innerHTML = '<div class="stream-content"></div>';
        }
        const streamContent = streamDiv?.querySelector('.stream-content');
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        
                        if (data.type === 'content' && data.content) {
                            fullContent += data.content;
                            if (streamContent) {
                                streamContent.textContent = fullContent;
                                streamContent.scrollTop = streamContent.scrollHeight;
                            }
                        } else if (data.type === 'done') {
                            // 完成
                            if (progressContainer) progressContainer.style.display = 'none';
                            if (successContainer) {
                                successContainer.style.display = 'block';
                                const contentDisplay = document.getElementById('summary-content-display');
                                if (contentDisplay) contentDisplay.textContent = fullContent;
                            }
                            showConfigStatus('✅ AI总结生成完成！', 'success');
                        } else if (data.type === 'error') {
                            throw new Error(data.message || '生成失败');
                        }
                    } catch (e) {
                        if (e.message !== 'Unexpected end of JSON input') {
                            console.warn('[Cache] Parse error:', e);
                        }
                    }
                }
            }
        }
        
    } catch (error) {
        console.error('[Cache] Generation failed:', error);
        
        const progressContainer = document.getElementById('generation-progress-container');
        const errorContainer = document.getElementById('generation-error-container');
        const errorMessage = document.getElementById('error-message');
        
        if (progressContainer) progressContainer.style.display = 'none';
        if (errorContainer) errorContainer.style.display = 'block';
        if (errorMessage) errorMessage.textContent = error.message;
        
        showConfigStatus('❌ 生成失败: ' + error.message, 'error');
    }
}

// ============ 合并生成群体+网络综合报告 ============

async function generateMergedSummaryFromCache(groupCacheId, networkCacheId) {
    if (!groupCacheId || !networkCacheId) {
        showConfigStatus('❌ 缺少群体分析或网络分析缓存', 'error');
        return;
    }
    
    // 检查AI配置
    if (typeof appState !== 'undefined' && !appState.aiEnabled) {
        showConfigStatus('❌ 请先启用AI功能', 'error');
        return;
    }
    
    try {
        // 显示进度
        const progressContainer = document.getElementById('generation-progress-container');
        const successContainer = document.getElementById('generation-success-container');
        const errorContainer = document.getElementById('generation-error-container');
        
        if (progressContainer) progressContainer.style.display = 'block';
        if (successContainer) successContainer.style.display = 'none';
        if (errorContainer) errorContainer.style.display = 'none';
        
        const progressStep = document.getElementById('progress-step');
        if (progressStep) progressStep.textContent = '正在合并群体分析和网络分析数据...';
        
        // 构建请求数据 - 合并模式
        const requestData = {
            type: 'group_and_network',
            group_cache_id: groupCacheId,
            network_cache_id: networkCacheId,
            max_tokens: appState?.aiOutputTokens || 4000,
            context_budget: appState?.aiContextTokens || 60000,
            ...getAiGenerationParamsForCache()
        };
        
        
        // 调用流式API
        if (progressStep) progressStep.textContent = '正在生成综合社交分析报告...';
        
        const response = await fetch('/api/ai/summary/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestData)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        // 处理流式响应
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullContent = '';
        
        const streamDiv = document.getElementById('generation-stream');
        if (streamDiv) {
            streamDiv.innerHTML = '<div class="stream-content"></div>';
        }
        const streamContent = streamDiv?.querySelector('.stream-content');
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        
                        if (data.type === 'content' && data.content) {
                            fullContent += data.content;
                            if (streamContent) {
                                streamContent.textContent = fullContent;
                                streamContent.scrollTop = streamContent.scrollHeight;
                            }
                        } else if (data.type === 'done') {
                            // 完成
                            if (progressContainer) progressContainer.style.display = 'none';
                            if (successContainer) {
                                successContainer.style.display = 'block';
                                const contentDisplay = document.getElementById('summary-content-display');
                                if (contentDisplay) contentDisplay.textContent = fullContent;
                            }
                            showConfigStatus('✅ 综合社交分析报告生成完成！', 'success');
                        } else if (data.type === 'error') {
                            throw new Error(data.message || '生成失败');
                        }
                    } catch (e) {
                        if (e.message !== 'Unexpected end of JSON input') {
                            console.warn('[Cache] Parse error:', e);
                        }
                    }
                }
            }
        }
        
    } catch (error) {
        console.error('[Cache] Merged generation failed:', error);
        
        const progressContainer = document.getElementById('generation-progress-container');
        const errorContainer = document.getElementById('generation-error-container');
        const errorMessage = document.getElementById('error-message');
        
        if (progressContainer) progressContainer.style.display = 'none';
        if (errorContainer) errorContainer.style.display = 'block';
        if (errorMessage) errorMessage.textContent = error.message;
        
        showConfigStatus('❌ 综合报告生成失败: ' + error.message, 'error');
    }
}

// ============ 分析完成后的保存按钮处理 ============

// 绑定保存按钮事件（按钮已在HTML中定义）
function addSaveButtons() {
    // 个人分析保存按钮
    const savePersonalBtn = document.getElementById('save-personal-cache-btn');
    if (savePersonalBtn && !savePersonalBtn.hasAttribute('data-bound')) {
        savePersonalBtn.setAttribute('data-bound', 'true');
        savePersonalBtn.onclick = () => saveCurrentAnalysis('personal');
    }
    
    // 群体分析保存按钮
    const saveGroupBtn = document.getElementById('save-group-cache-btn');
    if (saveGroupBtn && !saveGroupBtn.hasAttribute('data-bound')) {
        saveGroupBtn.setAttribute('data-bound', 'true');
        saveGroupBtn.onclick = () => saveCurrentAnalysis('group');
    }
    
    // 社交网络保存按钮
    const saveNetworkBtn = document.getElementById('save-network-cache-btn');
    if (saveNetworkBtn && !saveNetworkBtn.hasAttribute('data-bound')) {
        saveNetworkBtn.setAttribute('data-bound', 'true');
        saveNetworkBtn.onclick = () => saveCurrentAnalysis('network');
    }
}

// 显示保存按钮
function showSaveButton(type) {
    const btnId = `save-${type}-cache-btn`;
    const btn = document.getElementById(btnId);
    if (btn) {
        btn.style.display = 'inline-block';
        
    } else {
        console.warn(`[Cache] Save button not found: ${btnId}`);
    }
}

// 保存当前分析数据
async function saveCurrentAnalysis(type) {
    if (typeof appState === 'undefined' || !appState.currentFile) {
        alert('请先加载文件');
        return;
    }
    
    const analysisData = appState.analysisData?.[type];
    if (!analysisData) {
        alert('没有找到分析数据，请先进行分析');
        return;
    }
    
    let data = {};
    let qq = '';
    let nickname = '';
    
    if (type === 'personal') {
        qq = document.getElementById('qq-input')?.value || '';
        nickname = analysisData.nickname || '';
        data = { stats: analysisData };
    } else if (type === 'group') {
        data = { group_stats: analysisData };
    } else if (type === 'network') {
        data = { network_stats: analysisData };
    }
    
    const success = await analysisCacheManager.saveAnalysis(
        type,
        appState.currentFile,
        data,
        qq,
        nickname
    );
    
    if (success) {
        alert('分析数据已保存！您可以在「AI总结」页面使用此数据生成报告。');
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    // 延迟初始化，确保其他模块已加载
    setTimeout(() => {
        analysisCacheManager.init();
        addSaveButtons();
    }, 500);
});
