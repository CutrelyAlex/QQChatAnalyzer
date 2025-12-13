/**
 * QQ聊天记录分析系统 - 社交网络图模块
 * 网络图渲染和交互功能
 */

// ============ 全局变量 ============
let originalNetworkData = { nodes: [], edges: [] }; // 存储原始数据
let currentNetworkLimits = { maxNodes: 100, maxEdges: 300 }; // 当前限制

// ============ 社交网络图表函数 ============

function renderNetworkGraph(nodes, edges) {
    // """优化版网络图渲染 - 显示昵称、采用中心-圆环布局"""
    const container = document.getElementById('network-graph');
    
    if (!container) return;
    
    // 存储原始数据供后续调整使用
    if (originalNetworkData.nodes.length === 0) {
        originalNetworkData = { 
            nodes: JSON.parse(JSON.stringify(nodes)), 
            edges: JSON.parse(JSON.stringify(edges)) 
        };
    }
    
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
    
    // 初始适配视图
    network.once('afterDrawing', () => {
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

    const BATCH_SIZE = 50;
    const processEdgeUpdates = async (updates) => {
        for (let i = 0; i < updates.length; i += BATCH_SIZE) {
            const batch = updates.slice(i, i + BATCH_SIZE);
            data.edges.update(batch);
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
    
    // 添加点击事件
    network.on('click', async function(params) {
        if (isProcessing) return;
        
        // 点击节点
        if (params.nodes.length > 0) {
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
                
                // 异步隐藏无关的边
                await updateEdgesVisibility(nodeId);
                
                // 高亮选中的节点
                network.selectNodes([nodeId]);
                
                // 显示最终的状态消息
                showStatusMessage('info', `${isCore ? '🌟 核心成员' : '👤 成员'}: ${node.label} (连接数: ${degree})`);
            }
        } 
        // 点击边
        else if (params.edges.length > 0) {
            const edgeId = params.edges[0];
            const edge = visEdges.find(e => e.id === edgeId);
            if (edge) {
                // 高亮这条边连接的两个节点
                const fromNode = visNodes.find(n => n.id === edge.from);
                const toNode = visNodes.find(n => n.id === edge.to);
                
                if (fromNode && toNode) {
                    network.selectNodes([edge.from, edge.to]);
                    
                    const fromLabel = fromNode.label || edge.from;
                    const toLabel = toNode.label || edge.to;
                    showStatusMessage('info', `🔗 ${fromLabel} ↔ ${toLabel} (强度: ${edge.value.toFixed(2)})`);
                }
            }
        } 
        // 点击空白处
        else {
            // 恢复所有边的显示
            if (selectedNode !== null) {
                selectedNode = null;
                await updateEdgesVisibility(null);  // 显示所有边
                network.unselectAll();
                showStatusMessage('success', '✅ 已清除选择');
            }
        }
    });
    
    // 双击事件：重置视图并恢复所有边
    network.on('doubleClick', async function() {
        if (selectedNode !== null) {
            selectedNode = null;
            await updateEdgesVisibility(null);  // 显示所有边
            network.unselectAll();
        }
        network.fit({
            animation: {
                duration: 300,
                easingFunction: 'easeInOutQuad'
            }
        });

    });
    
    // 存储网络实例供后续使用
    window.currentNetwork = network;
    
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

// 页面加载时初始化控制面板
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNetworkControls);
} else {
    initNetworkControls();
}
