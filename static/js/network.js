/**
 * QQ聊天记录分析系统 - 社交网络图模块
 * 网络图渲染和交互功能
 */

// ============ 全局变量 ============
let originalNetworkData = { nodes: [], edges: [] }; // 存储原始数据
let currentNetworkLimits = { maxNodes: 100, maxEdges: 300 }; // 当前限制

// 布局/交互需要访问当前网络实例
window.currentNetwork = null;
window.currentNetworkData = null;

// ============ 社交网络图表函数 ============

function renderNetworkGraph(nodes, edges) {
    // """优化版网络图渲染 - 显示昵称、采用中心-圆环布局"""
    const container = document.getElementById('network-graph');
    
    if (!container) return;
    
    originalNetworkData = {
        nodes: JSON.parse(JSON.stringify(nodes)),
        edges: JSON.parse(JSON.stringify(edges))
    };

    // 当前交互模式：none | node | edge
    let focusMode = 'none';
    let focusedEdgeId = null;
    
    // ============ 配置：最大节点和边数量 ============
    const MAX_NODES = currentNetworkLimits.maxNodes;
    const MAX_EDGES = currentNetworkLimits.maxEdges;
    
    // 如果节点或边超过限制，进行过滤
    let filteredNodes = nodes;
    let filteredEdges = edges;
    
    if (nodes.length > MAX_NODES || edges.length > MAX_EDGES) {
        
        // 按边的权重排序，保留最重要的边
        const sortedEdges = [...edges].sort((a, b) => b.value - a.value);
        filteredEdges = sortedEdges.slice(0, MAX_EDGES);
        
        // 收集这些边涉及的节点
        const usedNodeIds = new Set();
        filteredEdges.forEach(edge => {
            usedNodeIds.add(edge.from);
            usedNodeIds.add(edge.to);
        });
        
        // 过滤节点，只保留有边连接的节点
        filteredNodes = nodes.filter(node => usedNodeIds.has(node.id));
        
        // 如果节点还是太多，按中心度选择最重要的节点
        if (filteredNodes.length > MAX_NODES) {
            const nodeImportance = {};
            filteredEdges.forEach(edge => {
                nodeImportance[edge.from] = (nodeImportance[edge.from] || 0) + edge.value;
                nodeImportance[edge.to] = (nodeImportance[edge.to] || 0) + edge.value;
            });
            
            filteredNodes = filteredNodes
                .sort((a, b) => (nodeImportance[b.id] || 0) - (nodeImportance[a.id] || 0))
                .slice(0, MAX_NODES);
            
            const finalNodeIds = new Set(filteredNodes.map(n => n.id));
            filteredEdges = filteredEdges.filter(edge => 
                finalNodeIds.has(edge.from) && finalNodeIds.has(edge.to)
            );
        }
        
        showStatusMessage('warning', `⚠️ 网络图已优化: ${nodes.length}→${filteredNodes.length} 节点, ${edges.length}→${filteredEdges.length} 边`);
    }
    
    // 使用过滤后的数据
    nodes = filteredNodes;
    edges = filteredEdges;
    
    // 计算节点的度（连接数）用于确定重要性
    const nodeDegrees = {};
    nodes.forEach(node => nodeDegrees[node.id] = 0);
    edges.forEach(edge => {
        if (nodeDegrees[edge.from] !== undefined) nodeDegrees[edge.from]++;
        if (nodeDegrees[edge.to] !== undefined) nodeDegrees[edge.to]++;
    });
    
    // 按度排序节点，找出核心节点（高度连接的节点）
    const sortedNodes = [...nodes].sort((a, b) => {
        const degreeA = nodeDegrees[a.id] || 0;
        const degreeB = nodeDegrees[b.id] || 0;
        return degreeB - degreeA;
    });
    
    // 核心节点（度最高的前N个，放在中心）
    const coreCount = Math.max(3, Math.min(8, Math.floor(nodes.length * 0.15)));
    const coreNodes = new Set(sortedNodes.slice(0, coreCount).map(n => n.id));
    
    // 计算布局位置
    const containerRect = container.getBoundingClientRect();
    const centerX = 0;
    const centerY = 0;
    const outerRadius = Math.min(containerRect.width, containerRect.height) * 0.35 || 350;
    const innerRadius = outerRadius * 0.25;
    
    // 外圈节点（非核心节点）
    const outerNodes = sortedNodes.filter(n => !coreNodes.has(n.id));
    // 核心节点
    const innerNodes = sortedNodes.filter(n => coreNodes.has(n.id));

    const nodePositions = {};

    if (innerNodes.length) {
        innerNodes.forEach((node, idx) => {
            const angle = (2 * Math.PI * idx) / innerNodes.length - Math.PI / 2;
            nodePositions[node.id] = {
                x: centerX + innerRadius * Math.cos(angle),
                y: centerY + innerRadius * Math.sin(angle)
            };
        });
    }

    if (outerNodes.length) {
        outerNodes.forEach((node, idx) => {
            const angle = (2 * Math.PI * idx) / outerNodes.length - Math.PI / 2;
            nodePositions[node.id] = {
                x: centerX + outerRadius * Math.cos(angle),
                y: centerY + outerRadius * Math.sin(angle)
            };
        });
    }

    // 准备节点数据 - 使用昵称而非QQ，并设置固定位置
    const visNodes = nodes.map((node) => {
        const pos = nodePositions[node.id] || { x: centerX, y: centerY };
        const degree = nodeDegrees[node.id] || 0;
        const isCore = coreNodes.has(node.id);
        
        return {
            id: node.id,
            label: node.label || node.id,
            value: Math.max(node.value * 25, 15),
            title: node.title || `${node.label || node.id} (${node.id})\n连接数: ${degree}`,
            x: pos.x,
            y: pos.y,
            // 移除 fixed 属性，允许拖动
            color: {
                background: isCore ? '#ff6b6b' : '#ff7f00',  // 核心节点红色，普通节点橙色
                border: isCore ? '#c92a2a' : '#cc6600',
                highlight: {
                    background: isCore ? '#ff8787' : '#ff9933',
                    border: isCore ? '#c92a2a' : '#cc6600'
                }
            },
            font: {
                size: isCore ? 14 : 10, 
                color: '#ffffff',
                bold: isCore ? { mod: 'bold' } : {}
            },
            borderWidth: isCore ? 3 : 2,
            size: isCore ? Math.max(25, 15 + degree * 2) : Math.max(15, 10 + degree)
        };
    });
    
    // 准备边数据 - 优化标签和样式，使用曲线避免重叠
    const visEdges = edges.map((edge, idx) => {
        const weightNorm = Math.min(edge.value / 2, 1);
        const fromCore = coreNodes.has(edge.from);
        const toCore = coreNodes.has(edge.to);
        const isCoreEdge = fromCore && toCore;  // 核心节点之间的连接
        const edgeId = edge.id || `edge-${idx}`;
        
        return {
            id: edgeId,
            from: edge.from,
            to: edge.to,
            value: edge.value,
            label: edge.value > 1.5 ? edge.value.toFixed(1) : '',
            title: edge.title || `${edge.from_name} ↔ ${edge.to_name} (强度: ${edge.value.toFixed(2)})`,
            width: isCoreEdge ? Math.max(Math.min(edge.value, 4), 1) : Math.max(Math.min(edge.value, 2), 0.3),
            color: {
                color: isCoreEdge 
                    ? `rgba(255, 107, 107, ${0.4 + weightNorm * 0.4})`  // 核心连接为红色
                    : `rgba(24, 144, 255, ${0.15 + weightNorm * 0.25})`,  // 普通连接更透明
                highlight: isCoreEdge ? 'rgba(255, 107, 107, 0.9)' : 'rgba(64, 169, 255, 0.8)'
            },
            smooth: {
                enabled: true,
                type: 'continuous',
                roundness: 0.2
            }
        };
    });

    const edgeLabelCache = {};
    const edgesByNode = {};
    const registerEdge = (nodeId, edgeId) => {
        if (!edgesByNode[nodeId]) {
            edgesByNode[nodeId] = new Set();
        }
        edgesByNode[nodeId].add(edgeId);
    };

    visEdges.forEach(edge => {
        edgeLabelCache[edge.id] = edge.label || '';
        registerEdge(edge.from, edge.id);
        registerEdge(edge.to, edge.id);
    });

    // 缓存基础样式（用于清除选择/恢复视图）
    const nodeBaseCache = {};
    const edgeBaseCache = {};

    visNodes.forEach(n => {
        nodeBaseCache[n.id] = {
            label: n.label,
            title: n.title,
            color: JSON.parse(JSON.stringify(n.color || {})),
            font: JSON.parse(JSON.stringify(n.font || {})),
            borderWidth: n.borderWidth,
            size: n.size
        };
    });

    visEdges.forEach(e => {
        edgeBaseCache[e.id] = {
            hidden: !!e.hidden,
            label: e.label || '',
            width: e.width,
            color: JSON.parse(JSON.stringify(e.color || {})),
            smooth: JSON.parse(JSON.stringify(e.smooth || {}))
        };
    });
    
    // 配置选项 - 禁用物理模拟（使用固定布局）
    const options = {
        nodes: {
            shape: 'dot',
            scaling: {
                min: 15,
                max: 50
            },
            font: {
                size: 3,
                face: 'Arial',
                multi: true
            },
            shadow: {
                enabled: true,
                color: 'rgba(255, 255, 255, 0.51)',
                size: 10,
                x: 3,
                y: 3
            }
        },
        edges: {
            width: 1,
            color: {
                color: 'rgba(24, 144, 255, 0.2)',
                highlight: 'rgba(64, 169, 255, 0.8)',
                hover: 'rgba(64, 169, 255, 0.5)'
            },
            scaling: {
                min: 0.3,
                max: 4
            },
            font: {
                size: 1,  
                color: '#888',
                strokeWidth: 0
            },
            smooth: {
                enabled: true,
                type: 'continuous'
            },
            arrows: {
                to: { enabled: false }
            },
            selectionWidth: 2
        },
        physics: {
            enabled: false  // 禁用物理模拟，使用固定布局
        },
        interaction: {
            hover: true,
            tooltipDelay: 200,
            navigationButtons: true,
            keyboard: true,
            zoomView: true,
            dragView: true,
            dragNodes: true,  // 允许拖动节点
            hideEdgesOnDrag: false,  // 不自动隐藏边，由点击事件管理
            hideEdgesOnZoom: false,
            hideNodesOnDrag: false
        },
        layout: {
            improvedLayout: false  // 使用我们的自定义布局
        }
    };
    
    // 创建网络图
    const data = {
        nodes: new vis.DataSet(visNodes),
        edges: new vis.DataSet(visEdges)
    };
    
    const network = new vis.Network(container, data, options);

    // 供布局按钮使用
    window.currentNetwork = network;
    window.currentNetworkData = data;
    
    // 初始适配视图
    network.once('afterDrawing', () => {
        if (typeof window.applyTreeLayout === 'function') {
            try {
                window.applyTreeLayout({ silent: true });
                return;
            } catch (e) {
                console.warn('Failed to apply default tree layout:', e);
            }
        }

        network.fit({
            animation: {
                duration: 500,
                easingFunction: 'easeInOutQuad'
            }
        });
    });
    
    // 追踪当前选中的节点
    let selectedNode = null;
    let isProcessing = false;  // 防止重复处理

    const focusOnNode = (nodeId, scale = 1.25) => {
        try {
            // focus 会把节点移动到视窗中心，并可设置缩放
            network.focus(nodeId, {
                scale,
                animation: {
                    duration: 350,
                    easingFunction: 'easeInOutQuad'
                }
            });
        } catch (_) {
            // ignore
        }
    };

    const focusOnNodesBoundingBox = (nodeIds, maxZoom = 1.4) => {
        try {
            const ids = (nodeIds || []).filter(Boolean);
            if (!ids.length) return;
            // fit 会把一组节点的包围盒移动到视窗中心
            network.fit({
                nodes: ids,
                animation: {
                    duration: 420,
                    easingFunction: 'easeInOutQuad'
                },
                // 避免过度放大
                maxZoom,
                // 适当留白
                padding: 60
            });
        } catch (_) {
            // ignore
        }
    };

    const BATCH_SIZE = 50;
    const processEdgeUpdates = async (updates) => {
        for (let i = 0; i < updates.length; i += BATCH_SIZE) {
            const batch = updates.slice(i, i + BATCH_SIZE);
            data.edges.update(batch);
            await new Promise(resolve => setTimeout(resolve, 5));
        }
    };

    const processNodeUpdates = async (updates) => {
        for (let i = 0; i < updates.length; i += BATCH_SIZE) {
            const batch = updates.slice(i, i + BATCH_SIZE);
            data.nodes.update(batch);
            await new Promise(resolve => setTimeout(resolve, 5));
        }
    };

    // 异步处理边的显示/隐藏
    async function updateEdgesVisibility(nodeId = null) {
        if (isProcessing) return;
        isProcessing = true;

        try {
            // 显示加载提示
            showStatusMessage('info', '⏳ 处理中...');

            // 使用 setTimeout 让UI有机会响应
            await new Promise(resolve => setTimeout(resolve, 10));

            const connected = nodeId ? (edgesByNode[nodeId] || new Set()) : null;
            const updates = visEdges.map(edge => {
                const isConnected = nodeId ? connected.has(edge.id) : true;
                return {
                    id: edge.id,
                    hidden: nodeId ? !isConnected : false,
                    label: isConnected ? edgeLabelCache[edge.id] : ''
                };
            });

            await processEdgeUpdates(updates);
        } finally {
            isProcessing = false;
        }
    }

    async function restoreAllNetworkStyles() {
        if (isProcessing) return;
        isProcessing = true;

        try {
            focusMode = 'none';
            focusedEdgeId = null;

            const nodeUpdates = visNodes.map(n => {
                const base = nodeBaseCache[n.id] || {};
                return {
                    id: n.id,
                    label: base.label,
                    title: base.title,
                    color: base.color,
                    font: base.font,
                    borderWidth: base.borderWidth,
                    size: base.size
                };
            });

            const edgeUpdates = visEdges.map(e => {
                const base = edgeBaseCache[e.id] || {};
                return {
                    id: e.id,
                    hidden: false,
                    label: edgeLabelCache[e.id] || base.label || '',
                    width: base.width,
                    color: base.color,
                    smooth: base.smooth
                };
            });

            await processNodeUpdates(nodeUpdates);
            await processEdgeUpdates(edgeUpdates);
            network.unselectAll();
        } finally {
            isProcessing = false;
        }
    }

    async function applyEdgeFocus(edgeId) {
        const edge = visEdges.find(e => e.id === edgeId);
        if (!edge) return;

        // 先恢复为“显示所有边”，避免之前点过节点导致边被隐藏
        await updateEdgesVisibility(null);

        if (isProcessing) return;
        isProcessing = true;

        try {
            focusMode = 'edge';
            focusedEdgeId = edgeId;
            selectedNode = null;

            const endpointIds = new Set([edge.from, edge.to]);
            const dimNodeColor = {
                background: 'rgba(255, 127, 0, 0.12)',
                border: 'rgba(204, 102, 0, 0.18)',
                highlight: { background: 'rgba(255, 127, 0, 0.12)', border: 'rgba(204, 102, 0, 0.18)' }
            };
            const dimFont = {
                size: 10,
                color: 'rgba(255, 255, 255, 0.25)',
                bold: {}
            };

            const nodeUpdates = visNodes.map(n => {
                const base = nodeBaseCache[n.id] || {};
                const baseLabel = base.label || n.label || n.id;
                const isEndpoint = endpointIds.has(n.id);

                // 端点节点：高亮显示“昵称 + QQ号”，其他节点：仅昵称，并整体变淡
                const endpointLabel = (baseLabel === n.id) ? `${n.id}` : `${baseLabel}\n${n.id}`;

                return {
                    id: n.id,
                    label: isEndpoint ? endpointLabel : baseLabel,
                    color: isEndpoint ? base.color : dimNodeColor,
                    font: isEndpoint ? base.font : dimFont,
                    borderWidth: isEndpoint ? Math.max(base.borderWidth || 2, 3) : 1,
                    size: isEndpoint ? Math.max(base.size || 15, 22) : Math.max(10, (base.size || 15) * 0.75)
                };
            });

            const edgeUpdates = visEdges.map(e => {
                const base = edgeBaseCache[e.id] || {};
                const isSelected = e.id === edgeId;
                return {
                    id: e.id,
                    hidden: false,
                    label: isSelected ? (edgeLabelCache[e.id] || base.label || '') : '',
                    width: isSelected ? Math.max((base.width || 1) * 2.0, 2) : Math.max((base.width || 1) * 0.4, 0.2),
                    color: isSelected
                        ? {
                            color: (base.color && base.color.highlight) ? base.color.highlight : 'rgba(64, 169, 255, 0.9)',
                            highlight: (base.color && base.color.highlight) ? base.color.highlight : 'rgba(64, 169, 255, 0.9)'
                        }
                        : {
                            color: 'rgba(24, 144, 255, 0.06)',
                            highlight: 'rgba(24, 144, 255, 0.06)'
                        }
                };
            });

            await processNodeUpdates(nodeUpdates);
            await processEdgeUpdates(edgeUpdates);

            network.selectEdges([edgeId]);
            network.selectNodes([edge.from, edge.to]);
        } finally {
            isProcessing = false;
        }
    }
    
    // 添加点击事件
    network.on('click', async function(params) {
        if (isProcessing) return;
        
        // 点击节点
        if (params.nodes.length > 0) {
            // 如果之前处于“边聚焦”，先恢复
            if (focusMode === 'edge') {
                await restoreAllNetworkStyles();
            }

            const nodeId = params.nodes[0];
            const node = visNodes.find(n => n.id === nodeId);
            if (node) {
                const degree = nodeDegrees[nodeId] || 0;
                const isCore = coreNodes.has(nodeId);
                
                // 如果已有选中节点，先恢复其所有边的显示
                if (selectedNode && selectedNode !== nodeId) {
                    await updateEdgesVisibility(null);  // 显示所有边
                    
                    // 让UI有机会更新
                    await new Promise(resolve => setTimeout(resolve, 10));
                }
                
                // 设置新的选中节点
                selectedNode = nodeId;
                focusMode = 'node';
                
                // 异步隐藏无关的边
                await updateEdgesVisibility(nodeId);
                
                // 高亮选中的节点
                network.selectNodes([nodeId]);

                // 视图居中到选中的节点（适用于所有布局）
                focusOnNode(nodeId, 1.35);
                
                // 显示最终的状态消息
                showStatusMessage('info', `${isCore ? '🌟 核心成员' : '👤 成员'}: ${node.label} (连接数: ${degree})`);
            }
        } 
        // 点击边
        else if (params.edges.length > 0) {
            const edgeId = params.edges[0];
            const edge = visEdges.find(e => e.id === edgeId);
            if (edge) {
                await applyEdgeFocus(edgeId);

                // 视图居中到两个端点的包围盒中心
                focusOnNodesBoundingBox([edge.from, edge.to], 1.35);

                const fromNode = visNodes.find(n => n.id === edge.from);
                const toNode = visNodes.find(n => n.id === edge.to);
                const fromLabel = (fromNode && (nodeBaseCache[fromNode.id]?.label || fromNode.label)) || edge.from_name || edge.from;
                const toLabel = (toNode && (nodeBaseCache[toNode.id]?.label || toNode.label)) || edge.to_name || edge.to;
                showStatusMessage('info', `🔗 ${fromLabel}(${edge.from}) ↔ ${toLabel}(${edge.to}) (强度: ${edge.value.toFixed(2)})`);
            }
        } 
        // 点击空白处
        else {
            selectedNode = null;
            await restoreAllNetworkStyles();
            showStatusMessage('success', '✅ 已清除选择');
        }
    });
    
    // 双击事件：重置视图并恢复所有边
    network.on('doubleClick', async function() {
        selectedNode = null;
        await restoreAllNetworkStyles();
        network.fit({
            animation: {
                duration: 300,
                easingFunction: 'easeInOutQuad'
            }
        });

    });
    
    // 存储网络实例供后续使用（window.currentNetwork 已在上面赋值）
    
    // 添加图例说明
    addNetworkLegend(container, coreCount, outerNodes.length);
}

// 添加网络图图例
function addNetworkLegend(container, coreCount, outerCount) {
    // 检查是否已有图例
    let legend = container.parentElement.querySelector('.network-legend');
    if (legend) {
        legend.remove();
    }
    
    legend = document.createElement('div');
    legend.className = 'network-legend';
    legend.innerHTML = `
        <div style="position: absolute; top: 10px; left: 10px; background: rgba(255,255,255,0.95); 
                    padding: 10px 15px; border-radius: 8px; font-size: 12px; 
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1); z-index: 10;">
            <div style="font-weight: bold; margin-bottom: 8px; color: #333;">📊 布局说明</div>
            <div style="display: flex; align-items: center; margin: 4px 0;">
                <span style="width: 12px; height: 12px; background: #ff6b6b; border-radius: 50%; display: inline-block; margin-right: 8px;"></span>
                <span>经常发言成员 (${coreCount}人)</span>
            </div>
            <div style="display: flex; align-items: center; margin: 4px 0;">
                <span style="width: 12px; height: 12px; background: #ff7f00; border-radius: 50%; display: inline-block; margin-right: 8px;"></span>
                <span>其余成员 (${outerCount}人) - 外圈</span>
            </div>
            <div style="color: #888; margin-top: 6px; font-size: 11px;">
                💡 双击重置视图 | 可拖动节点
            </div>
        </div>
    `;
    container.parentElement.style.position = 'relative';
    container.parentElement.appendChild(legend);
}

// ============ 网络图控制面板初始化 ============

function initNetworkControls() {
    const maxNodesSlider = document.getElementById('max-nodes-slider');
    const maxNodesValue = document.getElementById('max-nodes-value');
    const maxEdgesSlider = document.getElementById('max-edges-slider');
    const maxEdgesValue = document.getElementById('max-edges-value');
    
    if (!maxNodesSlider || !maxEdgesSlider) {
        console.warn('网络图控制元素未找到');
        return;
    }

    // 初始化：同步 slider 当前值到全局限制（否则默认仍是 100/300）
    if (maxNodesValue) maxNodesValue.textContent = maxNodesSlider.value;
    if (maxEdgesValue) maxEdgesValue.textContent = maxEdgesSlider.value;
    currentNetworkLimits.maxNodes = parseInt(maxNodesSlider.value);
    currentNetworkLimits.maxEdges = parseInt(maxEdgesSlider.value);
    
    // 更新显示值 - 控制面板现在总是显示，所以实时更新
    maxNodesSlider.addEventListener('input', function() {
        maxNodesValue.textContent = this.value;
        // 实时更新全局限制（用户输入时立即生效）
        currentNetworkLimits.maxNodes = parseInt(this.value);
    });
    
    maxEdgesSlider.addEventListener('input', function() {
        maxEdgesValue.textContent = this.value;
        // 实时更新全局限制
        currentNetworkLimits.maxEdges = parseInt(this.value);
    });
}

// ============ 网络图布局按钮 ============

function initNetworkLayoutButtons() {
    const btnCircle = document.getElementById('layout-circle-btn');
    const btnTree = document.getElementById('layout-tree-btn');
    const btnSmart = document.getElementById('layout-smart-btn');

    const btnFullscreen = document.getElementById('network-fullscreen-btn');
    const btnExportPng = document.getElementById('network-export-png-btn');
    const exportScaleSelect = document.getElementById('network-export-scale');

    const searchInput = document.getElementById('network-node-search');
    const searchBtn = document.getElementById('network-node-search-btn');

    let smartLayoutBusy = false;

    const requireNetwork = () => {
        if (!window.currentNetwork || !window.currentNetworkData) {
            showStatusMessage('error', '请先生成网络图');
            return false;
        }
        return true;
    };

    const getNetworkCanvas = () => {
        const network = window.currentNetwork;
        const c = network?.canvas?.frame?.canvas;
        if (c && c.toDataURL) return c;

        // 兜底：直接从 DOM 找 canvas
        const domCanvas = document.querySelector('#network-graph canvas');
        if (domCanvas && domCanvas.toDataURL) return domCanvas;
        return null;
    };

    const downloadDataUrl = (dataUrl, filename) => {
        const a = document.createElement('a');
        a.href = dataUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
    };

    const formatTs = () => {
        const d = new Date();
        const pad = (n) => n.toString().padStart(2, '0');
        return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
    };

    const updateFullscreenButtonText = () => {
        if (!btnFullscreen) return;
        const on = !!document.fullscreenElement;
        btnFullscreen.textContent = on ? '⛶ 退出全屏' : '⛶ 全屏';
    };

    const toggleFullscreen = async () => {
        if (!requireNetwork()) return;

        const target = document.getElementById('network-graph-container') || document.getElementById('network-graph');
        if (!target) {
            showStatusMessage('error', '网络图容器未找到');
            return;
        }

        try {
            if (!document.fullscreenElement) {
                await target.requestFullscreen();
            } else {
                await document.exitFullscreen();
            }
        } catch (e) {
            console.warn('toggleFullscreen failed:', e);
            showStatusMessage('error', '全屏失败：浏览器不支持或被阻止');
        }
    };

    const exportNetworkPng = async () => {
        if (!requireNetwork()) return;

        const network = window.currentNetwork;

        const canvas = getNetworkCanvas();
        if (!canvas) {
            showStatusMessage('error', '未找到网络图画布（请先生成网络图）');
            return;
        }

        let scale = 128;
        try {
            const v = parseFloat(exportScaleSelect?.value || '128');
            if (isFinite(v) && v > 0) scale = v;
        } catch (_) {
            // ignore
        }

        // 用户请求的倍率非常大，这里做安全保护：
        // 以“当前画布分辨率 * scale”会迅速爆内存，所以我们限制最大输出像素。
        const MAX_OUTPUT_PIXELS = 80_000_000; // ~80MP (RGBA约 320MB 内存峰值)

        // 导出前：先 fit，确保“整个画面的节点”都在视野内
        let prev = null;
        try {
            prev = {
                scale: typeof network.getScale === 'function' ? network.getScale() : null,
                position: typeof network.getViewPosition === 'function' ? network.getViewPosition() : null
            };
        } catch (_) {
            prev = null;
        }

        try {
            showStatusMessage('info', '⏳ 正在 fit 并导出 PNG（会自动包含全部节点）...');

            try {
                network.fit({
                    animation: false,
                    padding: 80,
                    maxZoom: 1.2
                });
            } catch (_) {
                // ignore
            }

            // 等待一帧，确保 redraw 完成
            await new Promise(resolve => requestAnimationFrame(() => setTimeout(resolve, 30)));

            // 再取一次画布（fit 后可能变更）
            const c = getNetworkCanvas() || canvas;

            const outW = Math.max(1, Math.floor(c.width * scale));
            const outH = Math.max(1, Math.floor(c.height * scale));
            const outPixels = outW * outH;

            if (outPixels > MAX_OUTPUT_PIXELS) {
                const approxMp = (outPixels / 1_000_000).toFixed(1);
                const maxMp = (MAX_OUTPUT_PIXELS / 1_000_000).toFixed(0);
                showStatusMessage('error', `导出倍率过大：约 ${approxMp}MP，超过安全上限 ${maxMp}MP。建议先全屏再导出，或降低倍率。`);
                return;
            }

            const out = document.createElement('canvas');
            out.width = outW;
            out.height = outH;
            const ctx = out.getContext('2d');
            if (!ctx) {
                showStatusMessage('error', '导出失败：无法获取画布上下文');
                return;
            }
            ctx.imageSmoothingEnabled = true;
            ctx.imageSmoothingQuality = 'high';
            ctx.drawImage(c, 0, 0, out.width, out.height);

            const dataUrl = out.toDataURL('image/png');
            downloadDataUrl(dataUrl, `network_graph_${formatTs()}_${scale}x.png`);
            showStatusMessage('success', `✅ 已导出 PNG（${scale}x，已包含全部节点）`);
        } catch (e) {
            console.error('exportNetworkPng failed:', e);
            showStatusMessage('error', '导出失败：' + (e?.message || e));
        } finally {
            // 导出后：恢复用户视角
            try {
                if (prev && prev.position && typeof network.moveTo === 'function') {
                    network.moveTo({
                        position: prev.position,
                        scale: prev.scale ?? undefined,
                        animation: { duration: 250, easingFunction: 'easeInOutQuad' }
                    });
                }
            } catch (_) {
                // ignore
            }
        }
    };

    const normalize = (s) => (s ?? '').toString().trim().toLowerCase();

    const findBestNodeId = (query) => {
        const q = normalize(query);
        if (!q) return null;

        const data = window.currentNetworkData;
        const nodes = data?.nodes?.get?.() || [];
        if (!nodes.length) return null;

        // 1) label 精确匹配（昵称 / Name(QQ)）
        for (const n of nodes) {
            if (normalize(n.label) === q) return n.id;
        }

        // 2) label 包含
        for (const n of nodes) {
            if (normalize(n.label).includes(q)) return n.id;
        }

        // 3) QQ 号匹配（通过全局成员索引映射 node.id -> QQ号）
        const idx = window.appState?.memberIndex;
        if (idx && idx.byId) {
            for (const n of nodes) {
                const m = idx.byId[n.id];
                const qq = (m?.qq ?? '').toString().trim();
                if (!qq) continue;
                if (normalize(qq) === q) return n.id;
            }
            for (const n of nodes) {
                const m = idx.byId[n.id];
                const qq = (m?.qq ?? '').toString().trim();
                if (!qq) continue;
                if (normalize(qq).includes(q)) return n.id;
            }
        }

        return null;
    };

    const focusAndSelectNode = (nodeId) => {
        const network = window.currentNetwork;
        const data = window.currentNetworkData;
        if (!network || !data) return;

        network.selectNodes([nodeId]);

        // 目标：在树状布局很大时也能看得清
        let targetScale = 1.35;
        try {
            const cur = network.getScale();
            if (typeof cur === 'number' && isFinite(cur)) {
                targetScale = Math.max(1.1, Math.min(1.8, cur < 0.9 ? 1.25 : cur * 1.25));
            }
        } catch (_) {
            // ignore
        }

        try {
            network.focus(nodeId, {
                scale: targetScale,
                animation: { duration: 380, easingFunction: 'easeInOutQuad' }
            });
        } catch (_) {
            // ignore
        }

        try {
            const node = data.nodes.get(nodeId);
            const label = node?.label || nodeId;
            showStatusMessage('success', `🔎 已定位: ${label} (${nodeId})`);
        } catch (_) {
            showStatusMessage('success', `🔎 已定位: ${nodeId}`);
        }
    };

    const handleSearch = () => {
        if (!requireNetwork()) return;
        const q = searchInput?.value || '';
        const nodeId = findBestNodeId(q);
        if (!nodeId) {
            showStatusMessage('warning', '未找到匹配的成员（可输入昵称或QQ号）');
            return;
        }
        focusAndSelectNode(nodeId);
    };

    const applyCircularLayout = () => {
        if (!requireNetwork()) return;
        const network = window.currentNetwork;
        const data = window.currentNetworkData;
        const container = document.getElementById('network-graph');
        const nodes = data.nodes.get();
        const edges = data.edges.get();

        if (!nodes.length) return;

        // 度数
        const deg = {};
        nodes.forEach(n => { deg[n.id] = 0; });
        edges.forEach(e => {
            if (deg[e.from] !== undefined) deg[e.from] += 1;
            if (deg[e.to] !== undefined) deg[e.to] += 1;
        });

        const sorted = [...nodes].sort((a, b) => (deg[b.id] || 0) - (deg[a.id] || 0));
        const coreCount = Math.max(3, Math.min(8, Math.floor(nodes.length * 0.15)));
        const coreIds = new Set(sorted.slice(0, coreCount).map(n => n.id));

        const rect = container ? container.getBoundingClientRect() : { width: 900, height: 600 };
        const centerX = 0;
        const centerY = 0;
        const outerRadius = Math.min(rect.width, rect.height) * 0.35 || 350;
        const innerRadius = outerRadius * 0.25;

        const inner = sorted.filter(n => coreIds.has(n.id));
        const outer = sorted.filter(n => !coreIds.has(n.id));

        const pos = {};
        if (inner.length) {
            inner.forEach((n, idx) => {
                const angle = (2 * Math.PI * idx) / inner.length - Math.PI / 2;
                pos[n.id] = { x: centerX + innerRadius * Math.cos(angle), y: centerY + innerRadius * Math.sin(angle) };
            });
        }
        if (outer.length) {
            outer.forEach((n, idx) => {
                const angle = (2 * Math.PI * idx) / outer.length - Math.PI / 2;
                pos[n.id] = { x: centerX + outerRadius * Math.cos(angle), y: centerY + outerRadius * Math.sin(angle) };
            });
        }

        data.nodes.update(nodes.map(n => ({ id: n.id, x: pos[n.id]?.x ?? 0, y: pos[n.id]?.y ?? 0 })));
        network.setOptions({
            physics: { enabled: false },
            layout: { improvedLayout: false, hierarchical: { enabled: false } },
            edges: { smooth: { enabled: true, type: 'continuous', roundness: 0.2 } }
        });
        network.fit({ animation: { duration: 500, easingFunction: 'easeInOutQuad' } });
        showStatusMessage('success', '✅ 已切换：圆形排布');
    };

    const applyTreeLayout = (opts = {}) => {
        const silent = !!opts.silent;
        if (!requireNetwork()) return;
        const network = window.currentNetwork;
        const data = window.currentNetworkData;
        const nodes = data.nodes.get();
        const edges = data.edges.get();

        if (!nodes.length) return;

        // 选择度数最高的节点为根
        const deg = {};
        nodes.forEach(n => { deg[n.id] = 0; });
        edges.forEach(e => {
            if (deg[e.from] !== undefined) deg[e.from] += 1;
            if (deg[e.to] !== undefined) deg[e.to] += 1;
        });
        const root = nodes.reduce((best, n) => ((deg[n.id] || 0) > (deg[best] || 0) ? n.id : best), nodes[0].id);

        // BFS 计算“最短距离层级”（原始层级）
        const adj = {};
        nodes.forEach(n => { adj[n.id] = []; });
        edges.forEach(e => {
            if (adj[e.from]) adj[e.from].push(e.to);
            if (adj[e.to]) adj[e.to].push(e.from);
        });

        const dist = {};
        const q = [root];
        dist[root] = 0;
        while (q.length) {
            const u = q.shift();
            const nextD = (dist[u] ?? 0) + 1;
            for (const v of (adj[u] || [])) {
                if (dist[v] === undefined) {
                    dist[v] = nextD;
                    q.push(v);
                }
            }
        }

        // 目标层容量：1-4-8-16-32-32-32...
        const capForLevel = (lvl) => {
            if (lvl <= 0) return 1;
            if (lvl === 1) return 4;
            if (lvl === 2) return 8;
            if (lvl === 3) return 16;
            return 32;
        };

        const assigned = {};
        assigned[root] = 0;
        const used = { 0: 1 };

        const maxDist = Object.values(dist).reduce((m, v) => Math.max(m, v), 0);
        const fallbackDist = maxDist + 1;

        const nodesSorted = nodes
            .filter(n => n.id !== root)
            .map(n => ({
                id: n.id,
                d: dist[n.id] ?? fallbackDist,
                deg: deg[n.id] || 0
            }))
            .sort((a, b) => (a.d - b.d) || (b.deg - a.deg) || String(a.id).localeCompare(String(b.id)));

        const pickLevel = (minLevel) => {
            let lvl = Math.max(1, minLevel);
            while (true) {
                const cap = capForLevel(lvl);
                const cur = used[lvl] || 0;
                if (cur < cap) return lvl;
                lvl += 1;
            }
        };

        for (const n of nodesSorted) {
            const lvl = pickLevel(n.d);
            assigned[n.id] = lvl;
            used[lvl] = (used[lvl] || 0) + 1;
        }

        data.nodes.update(nodes.map(n => ({ id: n.id, level: assigned[n.id] ?? fallbackDist, x: null, y: null })));
        network.setOptions({
            physics: { enabled: false },
            layout: {
                improvedLayout: true,
                hierarchical: {
                    enabled: true,
                    direction: 'UD',
                    sortMethod: 'hubsize',
                    levelSeparation: 120,
                    nodeSpacing: 140,
                    treeSpacing: 220
                }
            },
            edges: { smooth: { enabled: true, type: 'cubicBezier', roundness: 0.2 } }
        });
        network.fit({ animation: { duration: 600, easingFunction: 'easeInOutQuad' } });
        if (!silent) {
            showStatusMessage('success', '✅ 已切换：树状排布');
        }
    };

    window.applyTreeLayout = applyTreeLayout;

    const applySmartLayout = () => {
        if (!requireNetwork()) return;
        const network = window.currentNetwork;
        const data = window.currentNetworkData;

        if (smartLayoutBusy) {
            showStatusMessage('warning', '⏳ 智能排布正在计算中...');
            return;
        }
        smartLayoutBusy = true;
        if (btnSmart) btnSmart.disabled = true;

        showStatusMessage('info', '⏳ 智能排布计算中（先重置位置，再模拟几次以避免树状→智能错位）...');

        let finished = false;
        const finish = () => {
            if (finished) return;
            finished = true;
            smartLayoutBusy = false;
            if (btnSmart) btnSmart.disabled = false;

            try {
                if (typeof network.stopSimulation === 'function') network.stopSimulation();
            } catch (_) {
                // ignore
            }

            network.setOptions({ physics: { enabled: false } });
            network.fit({ animation: { duration: 600, easingFunction: 'easeInOutQuad' } });
            showStatusMessage('success', '✅ 智能排布完成');
        };

        // 从树状排布切到散乱排布时先把所有点重置到 (0,0)
        // 保证各个点可正常散开
        try {
            const nodes = data.nodes.get();
            if (nodes && nodes.length) {
                data.nodes.update(nodes.map(n => ({
                    id: n.id,
                    x: 0,
                    y: 0,
                    // 解除固定（若之前布局/拖动导致固定）
                    fixed: { x: false, y: false },
                    // 取消层级字段的影响（hierarchical 关闭后一般不影响，但保守处理）
                    level: undefined
                })));
            }
        } catch (_) {
            // ignore
        }

        network.setOptions({
            layout: { improvedLayout: true, hierarchical: { enabled: false } },
            physics: {
                enabled: true,
                solver: 'barnesHut',
                barnesHut: {
                    gravitationalConstant: -1800,
                    centralGravity: 0.12,
                    springLength: 140,
                    springConstant: 0.04,
                    damping: 0.35,
                    avoidOverlap: 0.2
                },
                stabilization: { enabled: true, iterations: 160, updateInterval: 25 }
            },
            edges: { smooth: { enabled: true, type: 'straightCross', roundness: 0.15 } }
        });

        // 强制刷新一次，确保“重置到 0,0”立即生效
        try {
            if (typeof network.redraw === 'function') network.redraw();
        } catch (_) {
            // ignore
        }

        // 事件在不同版本/状态下不一定触发，做多通道兜底
        try {
            network.once('stabilizationIterationsDone', finish);
            network.once('stabilized', finish);
        } catch (_) {
            // ignore
        }

        // 让 UI 先刷新，再触发 stabilize，降低“看起来卡住”的概率
        setTimeout(() => {
            try {
                // 分几次短 stabilize，比一次长 stabilize 更不容易让用户觉得“没反应”
                network.stabilize(60);
                setTimeout(() => {
                    try { network.stabilize(60); } catch (_) { /* ignore */ }
                }, 50);
                setTimeout(() => {
                    try { network.stabilize(60); } catch (_) { /* ignore */ }
                }, 100);
            } catch (_) {
                // ignore
            }
        }, 0);

        // 安全超时：避免永远不触发事件导致“卡住”
        setTimeout(finish, 2200);
    };

    if (btnCircle) btnCircle.addEventListener('click', applyCircularLayout);
    if (btnTree) btnTree.addEventListener('click', applyTreeLayout);
    if (btnSmart) btnSmart.addEventListener('click', applySmartLayout);

    if (btnFullscreen) {
        btnFullscreen.addEventListener('click', toggleFullscreen);
        updateFullscreenButtonText();

        // fullscreenchange 由用户按 ESC 退出时也会触发
        document.addEventListener('fullscreenchange', () => {
            updateFullscreenButtonText();
            try {
                // 全屏进/出后，容器尺寸变化，需要 redraw/fit
                const network = window.currentNetwork;
                if (network && typeof network.redraw === 'function') {
                    setTimeout(() => {
                        try { network.redraw(); } catch (_) { /* ignore */ }
                        try { network.fit({ animation: { duration: 220, easingFunction: 'easeInOutQuad' } }); } catch (_) { /* ignore */ }
                    }, 50);
                }
            } catch (_) {
                // ignore
            }
        });
    }

    if (btnExportPng) btnExportPng.addEventListener('click', () => { exportNetworkPng(); });

    if (searchBtn) searchBtn.addEventListener('click', handleSearch);
    if (searchInput) {
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                handleSearch();
            }
        });
    }
}

// 页面加载时初始化控制面板
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNetworkControls);
    document.addEventListener('DOMContentLoaded', initNetworkLayoutButtons);
} else {
    initNetworkControls();
    initNetworkLayoutButtons();
}
