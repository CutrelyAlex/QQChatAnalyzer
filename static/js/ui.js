/**
 * QQ聊天记录分析系统 - UI模块
 * 进度条、图表绘制等UI组件
 */

// ============ 进度条控制 ============

/**
 * 显示分析进度条
 * @param {string} type - 类型: 'personal', 'group', 'network'
 * @param {string} text - 进度文本
 */
function showProgress(type, text = '分析中...') {
    const progressBar = document.getElementById(`${type}-progress`);
    if (!progressBar) return;
    
    progressBar.style.display = 'block';
    const textEl = progressBar.querySelector('.progress-text');
    const fillEl = progressBar.querySelector('.progress-fill');
    
    if (textEl) textEl.textContent = text;
    if (fillEl) {
        fillEl.style.width = '0%';
        // 启动动画
        setTimeout(() => fillEl.style.width = '30%', 50);
        setTimeout(() => fillEl.style.width = '60%', 300);
        setTimeout(() => fillEl.style.width = '80%', 600);
    }
}

/**
 * 更新进度条
 * @param {string} type - 类型
 * @param {number} percent - 百分比 0-100
 * @param {string} text - 进度文本
 */
function updateProgress(type, percent, text) {
    const progressBar = document.getElementById(`${type}-progress`);
    if (!progressBar) return;
    
    const textEl = progressBar.querySelector('.progress-text');
    const fillEl = progressBar.querySelector('.progress-fill');
    
    if (textEl && text) textEl.textContent = text;
    if (fillEl) fillEl.style.width = `${percent}%`;
}

/**
 * 隐藏进度条
 * @param {string} type - 类型
 * @param {boolean} success - 是否成功
 */
function hideProgress(type, success = true) {
    const progressBar = document.getElementById(`${type}-progress`);
    if (!progressBar) return;
    
    const fillEl = progressBar.querySelector('.progress-fill');
    const textEl = progressBar.querySelector('.progress-text');
    
    if (fillEl) fillEl.style.width = '100%';
    if (textEl) textEl.textContent = success ? '完成!' : '失败';
    
    // 延迟隐藏
    setTimeout(() => {
        progressBar.style.display = 'none';
        if (fillEl) fillEl.style.width = '0%';
    }, 800);
}

// ============ 图表绘制函数 ============

let charts = {
    timeDistribution: null,
    weekly: null,
    monthlyTrend: null,
    memberRanking: null,
    messageType: null
};

function drawTimeDistributionChart(timeDistribution) {
    // """绘制时段分布柱状图"""
    const ctx = document.getElementById('time-dist-chart');
    if (!ctx) return;
    
    // 销毁旧图表
    if (charts.timeDistribution) charts.timeDistribution.destroy();
    
    const arr = Array.isArray(timeDistribution) ? timeDistribution : [];
    const labels = [
        '00-02', '02-04', '04-06', '06-08', '08-10', '10-12',
        '12-14', '14-16', '16-18', '18-20', '20-22', '22-24'
    ];
    const data = labels.map((_, i) => Number(arr[i] ?? 0) || 0);

    const colors = labels.map((_, i) => {
        // 12段：用HSL做一个平滑渐变（色相从200→320）
        const hue = 200 + Math.round((120 * i) / 11);
        return `hsla(${hue}, 70%, 55%, 0.75)`;
    });
    
    charts.timeDistribution = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: '消息数',
                data: data,
                backgroundColor: colors
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: { beginAtZero: true }
            }
        }
    });
}

function drawWeeklyChart(monthlyMessages) {
    //"""绘制周发言趋势线图"""
    const ctx = document.getElementById('weekly-chart');
    if (!ctx) return;
    
    if (charts.weekly) charts.weekly.destroy();
    
    const months = Object.keys(monthlyMessages).sort();
    const data = months.map(m => monthlyMessages[m]);
    
    charts.weekly = new Chart(ctx, {
        type: 'line',
        data: {
            labels: months,
            datasets: [{
                label: '消息数',
                data: data,
                borderColor: '#667eea',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                tension: 0.4,
                fill: true,
                pointRadius: 4,
                pointBackgroundColor: '#667eea',
                pointBorderColor: '#fff',
                pointBorderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: true }
            },
            scales: {
                y: { beginAtZero: true }
            }
        }
    });
}

function drawMonthlyTrendChart(monthlyTrend) {
    // """绘制月度消息趋势线图"""
    const canvas = document.getElementById('monthly-trend-chart');
    if (!canvas) return;
    
    if (charts.monthlyTrend) charts.monthlyTrend.destroy();
    
    const months = Object.keys(monthlyTrend).sort();
    const data = months.map(m => monthlyTrend[m]);
    
    charts.monthlyTrend = new Chart(canvas, {
        type: 'line',
        data: {
            labels: months,
            datasets: [{
                label: '消息数',
                data: data,
                borderColor: '#667eea',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                tension: 0.4,
                fill: true,
                pointRadius: 4,
                pointBackgroundColor: '#667eea',
                pointBorderColor: '#fff',
                pointBorderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: true }
            },
            scales: {
                y: { beginAtZero: true }
            }
        }
    });
}

function drawMemberRankingChart(memberMessageCount) {
    // """绘制成员活跃排行前10的水平柱状图"""
    const canvas = document.getElementById('member-ranking-chart');
    if (!canvas) return;
    
    if (charts.memberRanking) charts.memberRanking.destroy();
    
    // 取前10名成员 - 统一使用 {qq: {name, count}} 格式
    const sorted = Object.entries(memberMessageCount)
        .map(([qq, info]) => ({ qq, name: info?.name || qq, count: info?.count || 0 }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 10);
    
    // 使用最新昵称作为标签
    // 优先后端提供的 name，其次用 memberIndex 里的最新昵称，最后显示 QQ
    const labels = sorted.map(item => {
        const fromStats = (item.name || '').toString().trim();
        const fromIndex = (typeof appState !== 'undefined')
            ? ((appState.memberIndex?.byQQ?.[item.qq]?.name || appState.memberIndex?.byQQ?.[item.qq]?.names?.slice(-1)?.[0] || '').toString().trim())
            : '';
        const best = fromStats && fromStats !== item.qq ? fromStats : (fromIndex && fromIndex !== item.qq ? fromIndex : '');
        return best || `QQ:${item.qq}`;
    });
    const data = sorted.map(item => item.count);
    
    charts.memberRanking = new Chart(canvas, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: '消息数',
                data: data,
                backgroundColor: 'rgba(102, 126, 234, 0.8)',
                borderRadius: 4
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: { beginAtZero: true }
            }
        }
    });
}

function drawMessageTypeChart(stats) {
    // """绘制消息类型分布饼图"""
    const canvas = document.getElementById('message-type-chart');
    if (!canvas) return;
    
    if (charts.messageType) charts.messageType.destroy();
    
    // 准备消息类型数据
    const messageTypes = [
        { label: '文本', value: stats.text_ratio || 0 },
        { label: '图片', value: stats.image_ratio || 0 },
        { label: '表情', value: stats.emoji_ratio || 0 },
        { label: '链接', value: stats.link_ratio || 0 },
        { label: '转发', value: stats.forward_ratio || 0 }
    ];
    
    // 过滤掉为0的类型
    const filtered = messageTypes.filter(t => t.value > 0);
    
    if (filtered.length === 0) {
        canvas.style.display = 'none';
        return;
    }
    
    canvas.style.display = 'block';
    
    const colors = [
        'rgba(102, 126, 234, 0.8)',  // 蓝
        'rgba(52, 211, 153, 0.8)',   // 绿
        'rgba(251, 146, 60, 0.8)',   // 橙
        'rgba(168, 85, 247, 0.8)',   // 紫
        'rgba(236, 72, 153, 0.8)'    // 粉
    ];
    
    charts.messageType = new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels: filtered.map(t => t.label),
            datasets: [{
                data: filtered.map(t => (t.value * 100).toFixed(1)),
                backgroundColor: colors.slice(0, filtered.length),
                borderColor: '#fff',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return context.label + ': ' + context.parsed + '%';
                        }
                    }
                }
            }
        }
    });
}

