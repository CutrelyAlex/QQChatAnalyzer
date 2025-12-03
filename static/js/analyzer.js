/**
 * QQ聊天记录分析系统 - 分析模块
 * 个人、群体、社交网络分析功能
 */

// ============ 分析功能 ============

async function analyzePersonal() {
    if (!appState.currentFile) {
        showStatusMessage('error', '请先加载文件');
        return;
    }
    
    // 清空热词缓存
    if (typeof clearHotWordsCache === 'function') {
        clearHotWordsCache();
    }
    
    const qq = document.getElementById('qq-input').value;
    if (!qq) {
        showStatusMessage('error', '请输入QQ号');
        return;
    }
    
    // 显示进度条
    showProgress('personal', '正在分析个人数据...');
    
    try {
        updateProgress('personal', 40, '获取分析结果...');
        const response = await fetch(`${API_BASE}/personal/${qq}?file=${appState.currentFile}`);
        const data = await response.json();
        
        if (!data.success) {
            hideProgress('personal', false);
            showStatusMessage('error', data.error);
            return;
        }
        
        updateProgress('personal', 80, '渲染图表...');
        
        // 显示统计信息
        const stats = data.data;
        displayPersonalStats(stats);
        
        // 存储分析数据供后续使用
        appState.analysisData.personal = stats;
        document.getElementById('personal-summary-btn').disabled = !appState.aiEnabled;
        
        hideProgress('personal', true);
        showStatusMessage('success', `成功分析 ${stats.nickname}(${stats.qq}) 的数据`);
    } catch (error) {
        console.error('个人分析失败:', error);
        hideProgress('personal', false);
        showStatusMessage('error', '分析失败');
    }
}

function displayPersonalStats(stats) {
    // """显示个人统计数据"""
    document.getElementById('personal-stats').style.display = 'block';
    document.getElementById('personal-charts').style.display = 'block';
    
    // 更新统计卡片
    document.getElementById('stat-messages').textContent = stats.total_messages;
    document.getElementById('stat-active-days').textContent = stats.active_days;
    document.getElementById('stat-peak-time').textContent = getPeakTimeLabel(stats.time_distribution);
    document.getElementById('stat-max-streak').textContent = stats.max_streak_days + '天';
    document.getElementById('stat-at-count').textContent = stats.at_count;
    document.getElementById('stat-avg-length').textContent = Math.round(stats.avg_message_length) + '字';
    
    // 绘制图表
    drawTimeDistributionChart(stats.time_distribution);
    drawWeeklyChart(stats.monthly_messages);
    
    // 渲染热词云
    if (stats.top_words && stats.top_words.length > 0) {
        renderHotWords('personal-hot-words', stats.top_words);
    }
}

async function analyzeGroup() {
    if (!appState.currentFile) {
        showStatusMessage('error', '请先加载文件');
        return;
    }
    
    // 清空热词缓存
    if (typeof clearHotWordsCache === 'function') {
        clearHotWordsCache();
    }
    
    // 显示进度条
    showProgress('group', '正在分析群体数据...');
    
    try {
        updateProgress('group', 40, '获取分析结果...');
        
        // T028-T030: 调用群体分析API
        const response = await fetch(`${API_BASE}/group?file=${appState.currentFile}`);
        const data = await response.json();
        
        if (data.success) {
            updateProgress('group', 80, '渲染图表...');
            
            const stats = data.data;
            appState.analysisData.group = stats;
            
            // 显示统计卡片
            document.getElementById('group-stats').style.display = 'block';
            document.getElementById('group-charts').style.display = 'block';
            
            // 更新统计数据
            document.getElementById('stat-total-messages').textContent = stats.total_messages;
            
            // 计算参与成员数
            const totalMembers = stats.core_members.length + stats.active_members.length + 
                                stats.normal_members.length + stats.lurkers.length;
            document.getElementById('stat-members').textContent = totalMembers;
            
            document.getElementById('stat-daily-avg').textContent = stats.daily_average.toFixed(1);
            
            // 最活跃时段
            const peakHours = stats.peak_hours.length > 0 ? 
                             stats.peak_hours.map(h => `${h}:00`).join(', ') : '无数据';
            document.getElementById('stat-peak-hour').textContent = peakHours;
            
            // 绘制图表
            drawMonthlyTrendChart(stats.monthly_trend);
            drawMemberRankingChart(stats.member_message_count);
            drawMessageTypeChart(stats);
            
            // 渲染群体热词云
            if (stats.hot_words && stats.hot_words.length > 0) {
                renderHotWords('group-hot-words', stats.hot_words);
            }
            
            hideProgress('group', true);
            showStatusMessage('success', '群体分析完成');
        } else {
            hideProgress('group', false);
            showStatusMessage('error', data.error || '分析失败');
        }
    } catch (error) {
        console.error('群体分析失败:', error);
        hideProgress('group', false);
        showStatusMessage('error', '分析失败: ' + error.message);
    }
}

async function analyzeNetwork() {
    if (!appState.currentFile) {
        showStatusMessage('error', '请先加载文件');
        return;
    }
    
    // 清空热词缓存
    if (typeof clearHotWordsCache === 'function') {
        clearHotWordsCache();
    }
    
    // 显示进度条
    showProgress('network', '正在分析社交网络...');
    
    try {
        updateProgress('network', 30, '构建社交图...');
        
        // T037-T039: 调用社交网络分析API
        const response = await fetch(`${API_BASE}/network?file=${appState.currentFile}`);
        const data = await response.json();
        
        if (data.success) {
            updateProgress('network', 70, '计算中心度...');
            
            const stats = data.data;
            appState.analysisData.network = stats;
            
            // 显示统计卡片
            document.getElementById('network-stats').style.display = 'block';
            document.getElementById('network-graph-container').style.display = 'block';
            
            // 更新统计数据 - 显示优化信息
            let nodesText = `${stats.total_nodes}`;
            if (stats.original_nodes_count && stats.original_nodes_count > stats.total_nodes) {
                nodesText += ` (优化自 ${stats.original_nodes_count})`;
            }
            document.getElementById('stat-nodes').textContent = nodesText;
            
            let edgesText = `${stats.total_edges}`;
            if (stats.original_edges_count && stats.original_edges_count > stats.total_edges) {
                edgesText += ` (优化自 ${stats.original_edges_count})`;
            }
            document.getElementById('stat-edges').textContent = edgesText;
            
            // 最受欢迎成员 - 显示昵称
            const popularUser = stats.most_popular_user;
            if (popularUser) {
                const popularName = popularUser.name || `QQ:${popularUser.qq}`;
                document.getElementById('stat-most-popular').textContent = 
                    `${popularName} (${(popularUser.centrality * 100).toFixed(1)}%)`;
            } else {
                document.getElementById('stat-most-popular').textContent = '无';
            }
            
            // 最活跃互动对
            const activePair = stats.most_active_pair;
            if (activePair) {
                const name1 = activePair.name1 || activePair.pair[0];
                const name2 = activePair.name2 || activePair.pair[1];
                document.getElementById('stat-active-pair').textContent = 
                    `${name1} ↔ ${name2} (${activePair.weight.toFixed(1)})`;
            } else {
                document.getElementById('stat-active-pair').textContent = '无';
            }
            
            updateProgress('network', 90, '渲染网络图 (稳定中)...');
            
            // 渲染网络图
            renderNetworkGraph(stats.nodes, stats.edges);
            
            hideProgress('network', true);
            
            // 显示详细信息
            let msg = '社交网络分析完成';
            if (stats.original_nodes_count && stats.original_nodes_count > stats.total_nodes) {
                msg += ` - 已优化: ${stats.original_nodes_count}→${stats.total_nodes} 节点`;
            }
            showStatusMessage('success', msg);
        } else {
            hideProgress('network', false);
            showStatusMessage('error', data.error || '分析失败');
        }
    } catch (error) {
        console.error('社交网络分析失败:', error);
        hideProgress('network', false);
        showStatusMessage('error', '分析失败: ' + error.message);
    }
}

// ============ 辅助函数 ============

function getPeakTimeLabel(timeDistribution) {
    // """获取高峰时段标签"""
    const times = {
        'night': '夜间(00-06)',
        'early_morning': '早晨(06-09)',
        'morning': '上午(09-12)',
        'afternoon': '中午(12-18)',
        'evening': '晚上(18-21)',
        'night_late': '深夜(21-24)'
    };
    
    let maxTime = 'afternoon';
    let maxCount = 0;
    
    for (const [time, count] of Object.entries(timeDistribution)) {
        if (count > maxCount) {
            maxCount = count;
            maxTime = time;
        }
    }
    
    return times[maxTime] || '未知';
}
