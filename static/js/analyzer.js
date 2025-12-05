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
        
        // 更新UI（如果相关元素存在）
        const summaryBtn = document.getElementById('personal-summary-btn');
        if (summaryBtn) {
            summaryBtn.disabled = !appState.aiEnabled;
        }
        
        // 显示保存按钮
        if (typeof showSaveButton === 'function') {
            showSaveButton('personal');
        }
        
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
            
            // 渲染新增的时段分析
            if (stats.hourly_top_users) {
                renderHourlyTopUsers(stats.hourly_top_users);
            }
            if (stats.weekday_top_users) {
                renderWeekdayTopUsers(stats.weekday_top_users);
            }
            if (stats.weekday_totals) {
                renderWeekdayTotals(stats.weekday_totals);
            }
            
            // 显示保存按钮
            if (typeof showSaveButton === 'function') {
                showSaveButton('group');
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
            
            // 显示保存按钮
            if (typeof showSaveButton === 'function') {
                showSaveButton('network');
            }
            
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

// ============ 新增：时段分析渲染函数 ============

/**
 * 渲染每小时最活跃用户
 */
function renderHourlyTopUsers(hourlyTopUsers) {
    const container = document.getElementById('hourly-top-users');
    if (!container) return;
    
    console.log('renderHourlyTopUsers data:', hourlyTopUsers);
    
    // 按时段分组：凌晨(0-6)、早上(6-12)、下午(12-18)、晚上(18-24)
    const timeGroups = [
        { name: '🌙 凌晨', range: [0, 1, 2, 3, 4, 5], color: '#9775fa' },
        { name: '🌅 早上', range: [6, 7, 8, 9, 10, 11], color: '#ffa94d' },
        { name: '☀️ 下午', range: [12, 13, 14, 15, 16, 17], color: '#69db7c' },
        { name: '🌆 晚上', range: [18, 19, 20, 21, 22, 23], color: '#74c0fc' }
    ];
    
    let html = '<div class="hourly-grid">';
    
    for (const group of timeGroups) {
        html += `<div class="time-group">
            <div class="time-group-header" style="background: ${group.color}20; border-left: 3px solid ${group.color};">
                ${group.name}
            </div>
            <div class="time-group-items">`;
        
        for (const hour of group.range) {
            // JSON序列化后整数键变成字符串，需要用字符串访问
            const userData = hourlyTopUsers[hour] || hourlyTopUsers[hour.toString()];
            if (userData) {
                html += `
                    <div class="hourly-item">
                        <span class="hour-label">${hour.toString().padStart(2, '0')}:00</span>
                        <span class="user-name" title="QQ: ${userData.qq}">${userData.name}</span>
                        <span class="msg-count">${userData.count}条</span>
                    </div>`;
            } else {
                html += `
                    <div class="hourly-item inactive">
                        <span class="hour-label">${hour.toString().padStart(2, '0')}:00</span>
                        <span class="user-name">无数据</span>
                    </div>`;
            }
        }
        
        html += `</div></div>`;
    }
    
    html += '</div>';
    container.innerHTML = html;
}

/**
 * 渲染每周各日最活跃用户
 */
function renderWeekdayTopUsers(weekdayTopUsers) {
    const container = document.getElementById('weekday-top-users');
    if (!container) return;
    
    console.log('renderWeekdayTopUsers data:', weekdayTopUsers);
    
    const weekdayEmojis = ['📅', '📆', '🗓️', '📋', '🎉', '🌈', '☀️'];
    const weekdayColors = ['#ff6b6b', '#ffa94d', '#ffd43b', '#69db7c', '#38d9a9', '#74c0fc', '#9775fa'];
    const weekdayNames = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
    
    let html = '<div class="weekday-grid">';
    
    for (let i = 0; i < 7; i++) {
        // JSON序列化后整数键变成字符串，需要用字符串访问
        const userData = weekdayTopUsers[i] || weekdayTopUsers[i.toString()];
        const weekdayName = userData?.weekday_name || weekdayNames[i];
        const emoji = weekdayEmojis[i];
        const color = weekdayColors[i];
        
        if (userData) {
            html += `
                <div class="weekday-card" style="border-top: 3px solid ${color};">
                    <div class="weekday-name">${emoji} ${weekdayName}</div>
                    <div class="weekday-user" title="QQ: ${userData.qq}">${userData.name}</div>
                    <div class="weekday-count">${userData.count} 条消息</div>
                </div>`;
        } else {
            html += `
                <div class="weekday-card inactive">
                    <div class="weekday-name">${emoji} ${weekdayName}</div>
                    <div class="weekday-user">无数据</div>
                </div>`;
        }
    }
    
    html += '</div>';
    container.innerHTML = html;
}

/**
 * 渲染全年各星期几消息统计（柱状图）
 */
function renderWeekdayTotals(weekdayTotals) {
    const container = document.getElementById('weekday-totals');
    const canvas = document.getElementById('weekday-totals-chart');
    if (!canvas) return;
    
    console.log('renderWeekdayTotals data:', weekdayTotals);
    
    const weekdayNames = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
    
    // 准备数据
    const labels = [];
    const data = [];
    const colors = ['#ff6b6b', '#ffa94d', '#ffd43b', '#69db7c', '#38d9a9', '#74c0fc', '#9775fa'];
    
    for (let i = 0; i < 7; i++) {
        // JSON序列化后整数键变成字符串，需要用字符串访问
        const dayData = weekdayTotals[i] || weekdayTotals[i.toString()];
        labels.push(dayData?.weekday_name || weekdayNames[i]);
        data.push(dayData?.count || 0);
    }
    
    // 找出最高和最低
    const maxCount = Math.max(...data);
    const minCount = Math.min(...data.filter(c => c > 0));
    const maxIdx = data.indexOf(maxCount);
    const minIdx = data.indexOf(minCount);
    
    // 显示文字说明
    if (container) {
        const maxDay = labels[maxIdx];
        const minDay = labels[minIdx];
        container.innerHTML = `
            <div class="weekday-summary">
                <span class="summary-item max">🔥 最活跃: <strong>${maxDay}</strong> (${maxCount.toLocaleString()}条)</span>
                <span class="summary-item min">💤 最安静: <strong>${minDay}</strong> (${minCount.toLocaleString()}条)</span>
            </div>
        `;
    }
    
    // 销毁旧图表
    if (window.weekdayTotalsChart) {
        window.weekdayTotalsChart.destroy();
    }
    
    // 绘制柱状图
    const ctx = canvas.getContext('2d');
    window.weekdayTotalsChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: '消息数量',
                data: data,
                backgroundColor: colors,
                borderColor: colors.map(c => c),
                borderWidth: 1,
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.parsed.y.toLocaleString()} 条消息`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            if (value >= 1000) {
                                return (value / 1000).toFixed(1) + 'k';
                            }
                            return value;
                        }
                    }
                }
            }
        }
    });
}
