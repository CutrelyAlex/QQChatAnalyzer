/**
 * QQ聊天记录分析系统 - 分析模块
 * 个人、群体、社交网络分析功能
 */

// ============ 分析功能 ============

// 子页签渲染：避免在隐藏容器里绘制 Chart.js/vis 导致尺寸异常
window.onSubtabActivated = function (scope, subtab) {
    try {
        if (scope === 'personal') {
            const stats = appState.analysisData?.personal;
            if (!stats) return;
            if (subtab === 'trend') {
                renderPersonalTrends(stats);
            } else if (subtab === 'content') {
                renderPersonalContent(stats);
            }
        } else if (scope === 'group') {
            const stats = appState.analysisData?.group;
            if (!stats) return;
            if (subtab === 'trend') {
                renderGroupTrends(stats);
            } else if (subtab === 'members') {
                renderGroupMembers(stats);
            } else if (subtab === 'content') {
                renderGroupContent(stats);
            }
        } else if (scope === 'network') {
            if (subtab === 'graph') {
                // vis-network 在隐藏容器中初始化会拿不到正确尺寸；切回来时尝试刷新
                setTimeout(() => {
                    try {
                        if (window.currentNetwork && typeof window.currentNetwork.redraw === 'function') {
                            window.currentNetwork.redraw();
                        }
                        if (window.currentNetwork && typeof window.currentNetwork.fit === 'function') {
                            window.currentNetwork.fit({ animation: false });
                        }
                    } catch (_) {}
                }, 0);
            }
        }
    } catch (e) {
        console.warn('[Subtabs] render hook failed:', e);
    }
};

async function analyzePersonal() {
    if (!appState.currentFile) {
        showStatusMessage('error', '请先加载文件');
        return;
    }
    
    // 清空热词缓存
    if (typeof clearHotWordsCache === 'function') {
        clearHotWordsCache();
    }
    
    const qqOrName = document.getElementById('qq-input').value;
    if (!qqOrName) {
        showStatusMessage('error', '请输入QQ号或昵称');
        return;
    }

    const resolved = (typeof resolveMemberQuery === 'function')
        ? resolveMemberQuery(qqOrName)
        : { id: qqOrName, member: null };

    if (!resolved?.id) {
        showStatusMessage('error', '未找到匹配的成员（请输入QQ号或昵称）');
        return;
    }
    
    // 显示进度条
    showProgress('personal', '正在分析个人数据...');
    
    try {
        updateProgress('personal', 40, '获取分析结果...');
        const response = await fetch(`${API_BASE}/personal/${encodeURIComponent(resolved.id)}?file=${appState.currentFile}`);
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

        // 默认回到“概览”（绘制图表/热词改为懒加载）
        if (typeof setActiveSubtab === 'function') {
            setActiveSubtab('personal', 'overview');
        }
        
        hideProgress('personal', true);
        const disp = (typeof formatMemberDisplay === 'function')
            ? formatMemberDisplay(resolved.member, stats.display_name)
            : { main: `${stats.display_name || '未知成员'} (${stats.uin || '-'})`, uidSmall: '' };
        showStatusMessage('success', `成功分析 ${disp.main} 的数据`);
    } catch (error) {
        console.error('个人分析失败:', error);
        hideProgress('personal', false);
        showStatusMessage('error', '分析失败');
    }
}

function displayPersonalStats(stats) {
    // """显示个人统计数据（概览先渲染；趋势/内容懒加载）"""
    const statsBox = document.getElementById('personal-stats');
    const trendsBox = document.getElementById('personal-trends');
    const contentBox = document.getElementById('personal-content');
    if (statsBox) statsBox.style.display = 'block';
    if (trendsBox) trendsBox.style.display = 'block';
    if (contentBox) contentBox.style.display = 'block';
    
    // 更新统计卡片（概览）
    const setText = (id, value, fallback = '-') => {
        const el = document.getElementById(id);
        if (!el) return;
        if (value === undefined || value === null || value === '') {
            el.textContent = fallback;
            return;
        }
        el.textContent = value;
    };

    setText('stat-display-name', stats.display_name || '-');
    setText('stat-uin', stats.uin || '-');

    setText('stat-messages', stats.total_messages ?? 0, 0);
    setText('stat-active-days', stats.active_days ?? 0, 0);

    setText('stat-first-message-date', stats.first_message_date || '-', '-');
    setText('stat-last-message-date', stats.last_message_date || '-', '-');
    setText('stat-clean-text-msgs', stats.clean_text_message_count ?? 0, 0);

    setText('stat-peak-time', getPeakTimeLabel(stats.time_distribution_12), '未知');
    setText('stat-max-streak', (stats.max_streak_days ?? 0) + '天', '0天');
    setText('stat-at-count', stats.at_count ?? 0, 0);
    setText('stat-being-at-count', stats.being_at_count ?? 0, 0);
    setText('stat-reply-count', stats.reply_count ?? 0, 0);
    setText('stat-avg-length', Math.round(stats.avg_clean_chars_per_message ?? 0) + '字', '0字');
    setText('stat-total-chars', (stats.total_clean_chars ?? 0).toLocaleString(), '0');

    // 图表/热词：改为懒加载，在切到对应子页签时再绘制（避免隐藏容器尺寸=0）

    // ElementType / 结构化事件
    const pic = Number(stats.element_pic_count ?? 0) || 0;
    const file = Number(stats.element_file_count ?? 0) || 0;
    const forward = Number(stats.element_multiforward_count ?? 0) || 0;
    const emoji = (Number(stats.element_face_count ?? 0) || 0) + (Number(stats.element_mface_count ?? 0) || 0);

    setText('stat-image-count', pic, 0);
    setText('stat-file-count', file, 0);
    setText('stat-forward-count', forward, 0);
    setText('stat-emoji-count', emoji, 0);
    setText('stat-link-count', stats.link_count ?? 0, 0);
    setText('stat-system-count', stats.system_count ?? 0, 0);
    setText('stat-recall-count', stats.recall_count ?? 0, 0);

    // 全量 ElementType 统计（概览）
    renderPersonalElementStats(stats);
}

function renderPersonalElementStats(stats) {
    const box = document.getElementById('personal-element-stats');
    if (!box) return;

    const rows = [
        { label: '文本', field: 'element_text_count' },
        { label: '语音 (PTT)', field: 'element_ptt_count' },
        { label: '视频', field: 'element_video_count' },
        { label: 'QQ 表情', field: 'element_face_count' },
        { label: '回复', field: 'element_reply_count' },
        { label: '灰色提示', field: 'element_greytip_count' },
        { label: '钱包/红包', field: 'element_wallet_count' },
        { label: 'Ark 卡片', field: 'element_ark_count' },
        { label: '商城表情', field: 'element_mface_count' },
        { label: '直播礼物', field: 'element_livegift_count' },
        { label: '长消息结构', field: 'element_structlongmsg_count' },
        { label: 'Markdown', field: 'element_markdown_count' },
        { label: 'Giphy 动图', field: 'element_giphy_count' },
        { label: '内联键盘', field: 'element_inlinekeyboard_count' },
        { label: '文内礼物', field: 'element_intextgift_count' },
        { label: '日历', field: 'element_calendar_count' },
        { label: 'YOLO 游戏结果', field: 'element_yologameresult_count' },
        { label: '音视频通话', field: 'element_avrecord_count' },
        { label: '动态', field: 'element_feed_count' },
        { label: '豆腐记录', field: 'element_tofurecord_count' },
        { label: 'ACE 气泡', field: 'element_acebubble_count' },
        { label: '活动', field: 'element_activity_count' },
        { label: '豆腐', field: 'element_tofu_count' },
        { label: '表情气泡', field: 'element_facebubble_count' },
        { label: '位置分享', field: 'element_sharelocation_count' },
        { label: '置顶任务', field: 'element_tasktopmsg_count' },
        { label: '推荐消息', field: 'element_recommendedmsg_count' },
        { label: '操作栏', field: 'element_actionbar_count' }
    ];

    const html = rows.map(r => {
        const value = Number(stats[r.field] ?? 0) || 0;
        return `
            <div class="kv-item">
                <div class="kv-k">${escapeHtml(r.label)}</div>
                <div class="kv-v">${escapeHtml(String(value))}</div>
            </div>
        `;
    }).join('');

    box.innerHTML = html;
}

function renderPersonalTrends(stats) {
    try {
        // 绘制图表（趋势页）
        if (typeof drawTimeDistributionChart === 'function') {
            drawTimeDistributionChart(stats.time_distribution_12);
        }
        if (typeof drawWeeklyChart === 'function') {
            drawWeeklyChart(stats.monthly_messages || {});
        }
        if (typeof drawWeekdayChart === 'function') {
            drawWeekdayChart(stats.weekday_messages || []);
        }
    } catch (e) {
        console.warn('renderPersonalTrends failed:', e);
    }
}

function renderPersonalContent(stats) {
    try {
        // 热词
        if (stats.top_words && stats.top_words.length > 0 && typeof renderHotWords === 'function') {
            renderHotWords('personal-hot-words', stats.top_words);
        }

        // 互动对象 Top
        const box = document.getElementById('personal-top-interactions');
        if (box) {
            const arr = Array.isArray(stats.top_interactions) ? stats.top_interactions : [];
            if (!arr.length) {
                box.innerHTML = '<div class="simple-list-item">暂无互动对象统计</div>';
            } else {
                const items = arr.slice(0, 10).map(([pid, count]) => {
                    const m = appState.memberIndex?.byId?.[String(pid)] || null;
                    const disp = (typeof formatMemberDisplay === 'function')
                        ? formatMemberDisplay(m, String(pid))
                        : { main: String(pid) };
                    const label = disp.main || String(pid);
                    return `<div class="simple-list-item">${escapeHtml(label)} × ${escapeHtml(String(count))}</div>`;
                });
                box.innerHTML = items.join('');
            }
        }
    } catch (e) {
        console.warn('renderPersonalContent failed:', e);
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
            
            // 显示统计卡片（概览先显示，其它面板懒加载）
            const groupStatsBox = document.getElementById('group-stats');
            const groupTrendsBox = document.getElementById('group-trends');
            const groupMembersBox = document.getElementById('group-members');
            const groupContentBox = document.getElementById('group-content');
            if (groupStatsBox) groupStatsBox.style.display = 'block';
            if (groupTrendsBox) groupTrendsBox.style.display = 'block';
            if (groupMembersBox) groupMembersBox.style.display = 'block';
            if (groupContentBox) groupContentBox.style.display = 'block';

            renderGroupOverview(stats);
            
            // 图表/热词/成员：在切换到对应子页签时再渲染
            
            // 显示保存按钮
            if (typeof showSaveButton === 'function') {
                showSaveButton('group');
            }

            // 默认回到“概览”
            if (typeof setActiveSubtab === 'function') {
                setActiveSubtab('group', 'overview');
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

function renderGroupOverview(stats) {
    // 更新统计数据
    const setText = (id, value) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.textContent = (value === undefined || value === null) ? '-' : value;
    };

    setText('stat-total-messages', stats.total_messages);

    // 成员数：优先用后端给的 total_members（更稳）
    const totalMembers = (stats.total_members ?? null);
    if (totalMembers !== null && totalMembers !== undefined) {
        setText('stat-members', totalMembers);
    } else {
        const fallback = (stats.core_members?.length || 0) + (stats.active_members?.length || 0) +
            (stats.normal_members?.length || 0) + (stats.lurkers?.length || 0);
        setText('stat-members', fallback);
    }

    setText('stat-daily-avg', (typeof stats.daily_average === 'number') ? stats.daily_average.toFixed(1) : stats.daily_average);

    // 最活跃时段（只显示 1 个小时）
    if (stats.peak_hour !== undefined && stats.peak_hour !== null && stats.peak_hour !== '') {
        setText('stat-peak-hour', `${stats.peak_hour}:00`);
    } else {
        const peakHours = (Array.isArray(stats.peak_hours) && stats.peak_hours.length > 0)
            ? stats.peak_hours.map(h => `${h}:00`).join(', ')
            : '无数据';
        setText('stat-peak-hour', peakHours);
    }

    // 结构化元数据统计
    setText('stat-system-messages', stats.system_messages);
    setText('stat-recalled-messages', stats.recalled_messages);
    setText('stat-mention-messages', stats.mention_messages);
    setText('stat-reply-messages', stats.reply_messages);
    setText('stat-media-messages', stats.media_messages);

    // 谁最多（带数值）
    const formatTop = (item) => {
        if (!item) return '-';
        const member = appState.memberIndex?.byQQ?.[item.qq] || null;
        if (typeof formatMemberDisplay === 'function') {
            const disp = formatMemberDisplay(member, item.name || item.qq);
            return `${disp.main} × ${item.count}`;
        }
        const name = item.name || item.qq;
        return `${name} (${item.qq}) × ${item.count}`;
    };

    setText('stat-top-recaller', formatTop(stats.top_recaller));
    setText('stat-top-image-sender', formatTop(stats.top_image_sender));
    setText('stat-top-emoji-sender', formatTop(stats.top_emoji_sender));
    setText('stat-top-forward-sender', formatTop(stats.top_forward_sender));
    setText('stat-top-file-sender', formatTop(stats.top_file_sender));
    setText('stat-top-wallet-sender', formatTop(stats.top_wallet_sender));

    // ElementType 全量统计（概览）
    renderGroupElementStats(stats);
}

function renderGroupElementStats(stats) {
    const box = document.getElementById('group-element-stats');
    if (!box) return;

    const rows = [
        { label: '文本', field: 'element_text_count' },
        { label: '图片', field: 'element_pic_count' },
        { label: '文件', field: 'element_file_count' },
        { label: '语音 (PTT)', field: 'element_ptt_count' },
        { label: '视频', field: 'element_video_count' },
        { label: 'QQ 表情', field: 'element_face_count' },
        { label: '回复', field: 'element_reply_count' },
        { label: '灰色提示', field: 'element_greytip_count' },
        { label: '钱包/红包', field: 'element_wallet_count' },
        { label: 'Ark 卡片', field: 'element_ark_count' },
        { label: '商城表情', field: 'element_mface_count' },
        { label: '直播礼物', field: 'element_livegift_count' },
        { label: '长消息结构', field: 'element_structlongmsg_count' },
        { label: 'Markdown', field: 'element_markdown_count' },
        { label: 'Giphy 动图', field: 'element_giphy_count' },
        { label: '合并转发', field: 'element_multiforward_count' },
        { label: '内联键盘', field: 'element_inlinekeyboard_count' },
        { label: '文内礼物', field: 'element_intextgift_count' },
        { label: '日历', field: 'element_calendar_count' },
        { label: 'YOLO 游戏结果', field: 'element_yologameresult_count' },
        { label: '音视频通话', field: 'element_avrecord_count' },
        { label: '动态', field: 'element_feed_count' },
        { label: '豆腐记录', field: 'element_tofurecord_count' },
        { label: 'ACE 气泡', field: 'element_acebubble_count' },
        { label: '活动', field: 'element_activity_count' },
        { label: '豆腐', field: 'element_tofu_count' },
        { label: '表情气泡', field: 'element_facebubble_count' },
        { label: '位置分享', field: 'element_sharelocation_count' },
        { label: '置顶任务', field: 'element_tasktopmsg_count' },
        { label: '推荐消息', field: 'element_recommendedmsg_count' },
        { label: '操作栏', field: 'element_actionbar_count' }
    ];

    const html = rows.map(r => {
        const value = Number(stats?.[r.field] ?? 0) || 0;
        return `
            <div class="kv-item">
                <div class="kv-k">${escapeHtml(r.label)}</div>
                <div class="kv-v">${escapeHtml(String(value))}</div>
            </div>
        `;
    }).join('');

    box.innerHTML = html;
}

function renderGroupTrends(stats) {
    try {
        if (typeof drawMonthlyTrendChart === 'function') {
            drawMonthlyTrendChart(stats.monthly_trend || {});
        }
        if (typeof drawMessageTypeChart === 'function') {
            drawMessageTypeChart(stats);
        }
        if (typeof renderWeekdayTotals === 'function' && stats.weekday_totals) {
            renderWeekdayTotals(stats.weekday_totals);
        }
    } catch (e) {
        console.warn('renderGroupTrends failed:', e);
    }
}

function renderGroupMembers(stats) {
    try {
        renderGroupTopMetrics(stats);
        if (typeof drawMemberRankingChart === 'function') {
            drawMemberRankingChart(stats.member_message_count || {});
        }
        if (typeof renderHourlyTopUsers === 'function' && stats.hourly_top_users) {
            renderHourlyTopUsers(stats.hourly_top_users);
        }
        if (typeof renderWeekdayTopUsers === 'function' && stats.weekday_top_users) {
            renderWeekdayTopUsers(stats.weekday_top_users);
        }
    } catch (e) {
        console.warn('renderGroupMembers failed:', e);
    }
}

function renderGroupTopMetrics(stats) {
    const box = document.getElementById('group-top-metrics');
    if (!box) return;

    const formatTop = (item) => {
        if (!item) return '-';
        const member = appState.memberIndex?.byQQ?.[item.qq] || null;
        if (typeof formatMemberDisplay === 'function') {
            const disp = formatMemberDisplay(member, item.name || item.qq);
            return `${disp.main} × ${item.count}`;
        }
        const name = item.name || item.qq;
        return `${name} (${item.qq}) × ${item.count}`;
    };

    const items = [
        { label: '最常撤回', value: formatTop(stats.top_recaller) },
        { label: '发图片最多', value: formatTop(stats.top_image_sender) },
        { label: '发表情最多', value: formatTop(stats.top_emoji_sender) },
        { label: '转发最多', value: formatTop(stats.top_forward_sender) },
        { label: '发文件最多', value: formatTop(stats.top_file_sender) },
        { label: '红包/钱包最多', value: formatTop(stats.top_wallet_sender) },
        { label: '系统事件最多', value: formatTop(stats.top_system_sender) },
        { label: '含@消息最多', value: formatTop(stats.top_mention_sender) },
        { label: '回复消息最多', value: formatTop(stats.top_reply_sender) },
        { label: '含媒体/附件最多', value: formatTop(stats.top_media_sender) }
    ];

    // ElementType 谁最多（按 element id 展示；中文 label 在这里映射）
    const etLabel = {
        1: '文本',
        2: '图片',
        3: '文件',
        4: '语音',
        5: '视频',
        6: 'QQ 表情',
        7: '回复引用',
        8: '灰色提示',
        9: '钱包/红包',
        10: 'Ark 卡片',
        11: '商城表情',
        12: '直播礼物',
        13: '长消息结构',
        14: 'Markdown',
        15: 'Giphy 动图',
        16: '合并转发',
        17: '内联键盘',
        18: '文内礼物',
        19: '日历',
        20: 'YOLO 游戏结果',
        21: '音视频通话记录',
        22: '动态',
        23: '豆腐记录',
        24: 'ACE 气泡',
        25: '活动',
        26: '豆腐',
        27: '表情气泡',
        28: '位置分享',
        29: '置顶任务消息',
        43: '推荐消息',
        44: '操作栏'
    };

    const topEl = stats.top_element_senders || {};
    const elRows = Object.entries(topEl)
        .map(([k, v]) => ({ id: Number(k), item: v }))
        .filter(x => x.id && x.item)
        .sort((a, b) => a.id - b.id)
        .map(x => ({ label: `Element: ${etLabel[x.id] || x.id}`, value: formatTop(x.item) }));

    const finalItems = items.concat(elRows);

    if (!finalItems.length) {
        box.innerHTML = '<div class="simple-list-item">暂无统计</div>';
        return;
    }

    box.innerHTML = finalItems.map(it => {
        return `<div class="simple-list-item"><strong>${escapeHtml(it.label)}：</strong>${escapeHtml(it.value)}</div>`;
    }).join('');
}

function renderGroupContent(stats) {
    try {
        if (stats.hot_words && stats.hot_words.length > 0 && typeof renderHotWords === 'function') {
            renderHotWords('group-hot-words', stats.hot_words);
        }
    } catch (e) {
        console.warn('renderGroupContent failed:', e);
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
        const maxNodes = (typeof currentNetworkLimits !== 'undefined' && currentNetworkLimits?.maxNodes)
            ? currentNetworkLimits.maxNodes
            : 100;
        const maxEdges = (typeof currentNetworkLimits !== 'undefined' && currentNetworkLimits?.maxEdges)
            ? currentNetworkLimits.maxEdges
            : 300;

        const response = await fetch(
            `${API_BASE}/network?file=${encodeURIComponent(appState.currentFile)}` +
            `&max_nodes=${encodeURIComponent(maxNodes)}` +
            `&max_edges=${encodeURIComponent(maxEdges)}` +
            `&limit_compute=1`
        );
        const data = await response.json();
        
        if (data.success) {
            updateProgress('network', 70, '计算中心度...');
            
            const stats = data.data;
            appState.analysisData.network = stats;
            
            // 显示统计卡片和图表容器
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
                const m = appState.memberIndex?.byId?.[popularUser.qq];
                const disp = (typeof formatMemberDisplay === 'function')
                    ? formatMemberDisplay(m || popularUser, popularUser.name)
                    : { main: (popularUser.name || popularUser.qq), uidSmall: '' };
                const popularName = disp.main;
                document.getElementById('stat-most-popular').textContent = 
                    `${popularName} (${(popularUser.centrality * 100).toFixed(1)}%)`;
            } else {
                document.getElementById('stat-most-popular').textContent = '无';
            }
            
            // 最活跃互动对
            const activePair = stats.most_active_pair;
            if (activePair) {
                const id1 = activePair.pair?.[0];
                const id2 = activePair.pair?.[1];
                const m1 = id1 ? appState.memberIndex?.byId?.[id1] : null;
                const m2 = id2 ? appState.memberIndex?.byId?.[id2] : null;
                const d1 = (typeof formatMemberDisplay === 'function') ? formatMemberDisplay(m1, activePair.name1) : { main: (activePair.name1 || id1) };
                const d2 = (typeof formatMemberDisplay === 'function') ? formatMemberDisplay(m2, activePair.name2) : { main: (activePair.name2 || id2) };
                const name1 = d1.main;
                const name2 = d2.main;
                document.getElementById('stat-active-pair').textContent = 
                    `${name1} ↔ ${name2} (${activePair.weight.toFixed(1)})`;
            } else {
                document.getElementById('stat-active-pair').textContent = '无';
            }
            
            updateProgress('network', 90, '渲染网络图 (稳定中)...');

            // 确保网络图面板处于可见状态，再初始化 vis-network（否则可能尺寸为0）
            if (typeof setActiveSubtab === 'function') {
                setActiveSubtab('network', 'graph');
            }
            
            // 根据成员索引增强节点展示：优先 Name + QQ，并在 tooltip 中补充 UID
            const enrichedNodes = (stats.nodes || []).map(n => {
                const m = appState.memberIndex?.byId?.[n.id] || null;
                const disp = (typeof formatMemberDisplay === 'function')
                    ? formatMemberDisplay(m, n.label)
                    : { main: n.label || n.id, uidSmall: '' };

                // label 建议短一些，图上展示 Name+QQ；tooltip 展示 uid
                const titleParts = [];
                if (disp.main) titleParts.push(disp.main);
                if (disp.uidSmall) titleParts.push(disp.uidSmall);
                if (n.id) titleParts.push(`id:${n.id}`);
                return {
                    ...n,
                    label: disp.main || (n.label || n.id),
                    title: titleParts.join('\n')
                };
            });

            // 渲染网络图
            renderNetworkGraph(enrichedNodes, stats.edges);
            
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

function getPeakTimeLabel(timeDistribution12) {
    // """获取高峰时段标签（12段，每段2小时）"""
    const arr = Array.isArray(timeDistribution12) ? timeDistribution12 : [];
    let maxIdx = 0;
    let maxCount = -1;

    for (let i = 0; i < 12; i++) {
        const c = Number(arr[i] ?? 0) || 0;
        if (c > maxCount) {
            maxCount = c;
            maxIdx = i;
        }
    }

    const start = maxIdx * 2;
    const end = (maxIdx + 1) * 2;
    const pad = (n) => n.toString().padStart(2, '0');
    return `${pad(start)}:00-${pad(end)}:00`;
}

// ============ 新增：时段分析渲染函数 ============

/**
 * 渲染每小时最活跃用户
 */
function renderHourlyTopUsers(hourlyTopUsers) {
    const container = getEl('hourly-top-users');
    if (!container) return;
    
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
            // 注：JSON对象键在JS中本质上是字符串；obj[hour] 会自动转为字符串键。
            const userData = hourlyTopUsers[hour];
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
    const container = getEl('weekday-top-users');
    if (!container) return;
    
    const weekdayEmojis = ['📅', '📆', '🗓️', '📋', '🎉', '🌈', '☀️'];
    const weekdayColors = ['#ff6b6b', '#ffa94d', '#ffd43b', '#69db7c', '#38d9a9', '#74c0fc', '#9775fa'];
    const weekdayNames = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
    
    let html = '<div class="weekday-grid">';
    
    for (let i = 0; i < 7; i++) {
        const userData = weekdayTopUsers[i];
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
    const container = getEl('weekday-totals');
    const canvas = getEl('weekday-totals-chart');
    if (!canvas) return;
    
    const weekdayNames = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
    
    // 准备数据
    const labels = [];
    const data = [];
    const colors = ['#ff6b6b', '#ffa94d', '#ffd43b', '#69db7c', '#38d9a9', '#74c0fc', '#9775fa'];
    
    for (let i = 0; i < 7; i++) {
        const dayData = weekdayTotals[i];
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
