/**
 * QQ聊天记录分析系统 - 对比模块
 * 负责 /api/compare 的调用与渲染
 */

function _getOptionValues(selectEl) {
    if (!selectEl) return [];
    return Array.from(selectEl.options || [])
        .map(o => o && o.value)
        .filter(v => !!v);
}

function populateCompareFileSelects() {
    const source = document.getElementById('file-select');
    const leftSel = document.getElementById('compare-left-file');
    const rightSel = document.getElementById('compare-right-file');

    if (!source || !leftSel || !rightSel) return;

    const values = _getOptionValues(source);
    const currentLeft = leftSel.value;
    const currentRight = rightSel.value;

    const rebuild = (sel, selectedValue) => {
        const keep = selectedValue && values.includes(selectedValue) ? selectedValue : '';
        sel.innerHTML = '';
        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = '-- 选择文件 --';
        sel.appendChild(placeholder);

        Array.from(source.options || []).forEach(opt => {
            if (!opt || !opt.value) return;
            const o = document.createElement('option');
            o.value = opt.value;
            o.textContent = opt.textContent;
            sel.appendChild(o);
        });

        if (keep) {
            sel.value = keep;
        }
    };

    rebuild(leftSel, currentLeft);
    rebuild(rightSel, currentRight);

    // 默认选择：左侧尽量跟随当前已加载文件；右侧选不同的另一个
    if (!leftSel.value && appState?.currentFile && values.includes(appState.currentFile)) {
        leftSel.value = appState.currentFile;
    }

    if (!rightSel.value) {
        const pick = values.find(v => v !== leftSel.value) || '';
        rightSel.value = pick;
    }
}

function _formatDelta(delta, pct) {
    const sign = delta > 0 ? '+' : '';
    const dStr = Number.isFinite(delta) ? `${sign}${delta.toFixed(2)}` : `${delta}`;
    if (pct === null || pct === undefined) return dStr;
    if (!Number.isFinite(pct)) return dStr;
    const pSign = pct > 0 ? '+' : '';
    return `${dStr} (${pSign}${(pct * 100).toFixed(1)}%)`;
}

function _deltaClass(delta) {
    if (!Number.isFinite(delta) || delta === 0) return 'delta-zero';
    return delta > 0 ? 'delta-pos' : 'delta-neg';
}

function renderSnapshotSummary(containerId, snapshot) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const conv = snapshot?.conversation || {};
    const grp = snapshot?.group || {};
    const net = snapshot?.network || {};

    const rows = [
        ['文件', snapshot?.filename || '-'],
        ['会话类型', conv.type || '-'],
        ['标题', conv.title || '-'],
        ['参与者数', conv.participants ?? '-'],
        ['消息(原始)', conv.messageCountRaw ?? '-'],
        ['消息(去重)', conv.messageCountDeduped ?? '-'],
        ['消息总数(分析口径)', grp.total_messages ?? '-'],
        ['日均消息', (typeof grp.daily_average === 'number') ? grp.daily_average.toFixed(1) : (grp.daily_average ?? '-')],
        ['系统事件', grp.system_messages ?? '-'],
        ['撤回消息', grp.recalled_messages ?? '-'],
        ['含@提及', grp.mention_messages ?? '-'],
        ['回复消息', grp.reply_messages ?? '-'],
        ['含媒体/附件', grp.media_messages ?? '-'],
    ];

    if (net && Object.keys(net).length > 0) {
        rows.push(['网络节点数', net.total_nodes ?? '-']);
        rows.push(['网络边数', net.total_edges ?? '-']);
        rows.push(['网络密度', (typeof net.density === 'number') ? net.density.toFixed(4) : (net.density ?? '-')]);
        rows.push(['平均聚类系数', (typeof net.average_clustering === 'number') ? net.average_clustering.toFixed(4) : (net.average_clustering ?? '-')]);
    }

    container.innerHTML = rows
        .map(([label, value]) => {
            const safeLabel = escapeHtml(String(label));
            const safeValue = escapeHtml(String(value));
            return `<div class="summary-row"><div class="label">${safeLabel}</div><div class="value">${safeValue}</div></div>`;
        })
        .join('');
}

function renderDiffTable(containerId, diffFields, labelMap) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const entries = Object.entries(diffFields || {});
    if (entries.length === 0) {
        container.innerHTML = '<div style="color: var(--text-tertiary);">无差异数据</div>';
        return;
    }

    const header = `
        <table>
            <thead>
                <tr>
                    <th>指标</th>
                    <th>左侧</th>
                    <th>右侧</th>
                    <th>变化</th>
                </tr>
            </thead>
            <tbody>
    `;

    const body = entries
        .map(([key, v]) => {
            const label = (labelMap && labelMap[key]) ? labelMap[key] : key;
            const left = v?.left;
            const right = v?.right;
            const delta = (typeof v?.delta === 'number') ? v.delta : Number(v?.delta);
            const pct = v?.deltaPct;

            const deltaText = _formatDelta(delta, pct);
            const cls = _deltaClass(delta);

            return `
                <tr>
                    <td>${escapeHtml(String(label))}</td>
                    <td>${escapeHtml(String(left ?? '-'))}</td>
                    <td>${escapeHtml(String(right ?? '-'))}</td>
                    <td class="${cls}">${escapeHtml(deltaText)}</td>
                </tr>
            `;
        })
        .join('');

    const footer = `
            </tbody>
        </table>
    `;

    container.innerHTML = header + body + footer;
}

async function runCompare() {
    const leftSel = document.getElementById('compare-left-file');
    const rightSel = document.getElementById('compare-right-file');

    const left = leftSel?.value;
    const right = rightSel?.value;

    if (!left || !right) {
        showStatusMessage('error', '请选择左右两侧文件');
        return;
    }

    if (left === right) {
        showStatusMessage('error', '左右文件不能相同');
        return;
    }

    // 默认计算网络摘要；如果网络很大，可以在未来加一个开关
    const includeNetwork = true;

    setDisplay('compare-result', 'none');
    showProgress('compare', '正在对比...');

    try {
        updateProgress('compare', 20, '请求对比结果...');
        const url = `${API_BASE}/compare?left=${encodeURIComponent(left)}&right=${encodeURIComponent(right)}&include_network=${includeNetwork ? '1' : '0'}&limit_compute=1`;
        const resp = await fetch(url);
        const data = await resp.json();

        if (!data.success) {
            hideProgress('compare', false);
            showStatusMessage('error', data.error || '对比失败');
            return;
        }

        updateProgress('compare', 70, '渲染结果...');

        renderSnapshotSummary('compare-left-summary', data.left);
        renderSnapshotSummary('compare-right-summary', data.right);

        const labelMap = {
            participants: '参与者数',
            messageCountRaw: '消息(原始)',
            messageCountDeduped: '消息(去重)',
            total_messages: '消息总数(分析口径)',
            daily_average: '日均消息',
            system_messages: '系统事件',
            recalled_messages: '撤回消息',
            mention_messages: '含@提及',
            reply_messages: '回复消息',
            media_messages: '含媒体/附件',
            total_nodes: '网络节点数',
            total_edges: '网络边数',
            density: '网络密度',
            average_clustering: '平均聚类系数'
        };

        renderDiffTable('compare-diff-table', data.diff?.fields || {}, labelMap);
        renderDiffTable('compare-media-diff', data.diff?.media_breakdown || {}, null);

        setDisplay('compare-result', 'block');
        hideProgress('compare', true);

        // 如果导入时有 warning，提示一下
        const warnLeft = data?.warnings?.left || [];
        const warnRight = data?.warnings?.right || [];
        const warnCount = (warnLeft.length || 0) + (warnRight.length || 0);
        if (warnCount > 0) {
            showStatusMessage('info', `对比完成（导入提示 ${warnCount} 条，可在控制台查看）`);
            console.info('Compare warnings (left):', warnLeft);
            console.info('Compare warnings (right):', warnRight);
        } else {
            showStatusMessage('success', '对比完成');
        }

    } catch (err) {
        console.error('对比失败:', err);
        hideProgress('compare', false);
        showStatusMessage('error', '对比失败: ' + (err?.message || String(err)));
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // 点击 compare 标签时，刷新下拉列表
    document.querySelectorAll('.tab-button').forEach(btn => {
        if (btn?.dataset?.tab === 'compare') {
            btn.addEventListener('click', () => {
                populateCompareFileSelects();
            });
        }
    });

    // 监听 file-select option 变化（loadFileList 会重建 options）
    const fileSelect = document.getElementById('file-select');
    if (fileSelect && typeof MutationObserver !== 'undefined') {
        const observer = new MutationObserver(() => {
            populateCompareFileSelects();
        });
        observer.observe(fileSelect, { childList: true, subtree: true });
    }

    // 初次填充
    populateCompareFileSelects();

    const runBtn = document.getElementById('compare-run-btn');
    if (runBtn) runBtn.addEventListener('click', runCompare);
});
