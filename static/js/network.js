/**
 * QQ聊天记录分析系统 - 社交网络图模块
 * 网络图渲染和交互功能
 */

// ============ 社交网络图表函数 ============

function renderNetworkGraph(nodes, edges) {
    // """优化版网络图渲染 - 显示昵称、采用中心-圆环布局"""
    const container = document.getElementById('network-graph');
    
    if (!container) return;
    
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
    
    // 准备节点数据 - 使用昵称而非QQ，并设置固定位置
    const visNodes = nodes.map((node, idx) => {
        let x, y;
        
        if (coreNodes.has(node.id)) {
            // 核心节点：放在中心附近的小圆上
            const coreIdx = innerNodes.findIndex(n => n.id === node.id);
            const angle = (2 * Math.PI * coreIdx) / innerNodes.length - Math.PI / 2;
            x = centerX + innerRadius * Math.cos(angle);
            y = centerY + innerRadius * Math.sin(angle);
        } else {
            // 外围节点：放在大圆上
            const outerIdx = outerNodes.findIndex(n => n.id === node.id);
            const angle = (2 * Math.PI * outerIdx) / outerNodes.length - Math.PI / 2;
            x = centerX + outerRadius * Math.cos(angle);
            y = centerY + outerRadius * Math.sin(angle);
        }
        
        const degree = nodeDegrees[node.id] || 0;
        const isCore = coreNodes.has(node.id);
        
        return {
            id: node.id,
            label: node.label || node.id,
            value: Math.max(node.value * 25, 15),
            title: node.title || `${node.label || node.id} (${node.id})\n连接数: ${degree}`,
            x: x,
            y: y,
            // 移除 fixed 属性，允许拖动
            color: {
                background: isCore ? '#ff6b6b' : '#1890ff',  // 核心节点红色
                border: isCore ? '#c92a2a' : '#0050b3',
                highlight: {
                    background: isCore ? '#ff8787' : '#40a9ff',
                    border: isCore ? '#c92a2a' : '#0050b3'
                }
            },
            font: {
                size: isCore ? 14 : 12,
                color: '#000',
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
        
        return {
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
    
    // 配置选项 - 禁用物理模拟（使用固定布局）
    const options = {
        nodes: {
            shape: 'dot',
            scaling: {
                min: 15,
                max: 50
            },
            font: {
                size: 12,
                face: 'Arial',
                multi: true
            },
            shadow: {
                enabled: true,
                color: 'rgba(0, 0, 0, 0.1)',
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
                size: 10,
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
            hideNodesOnDrag: false,
            navigationButtons: true,
            keyboard: true
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
        console.log('网络图布局完成 - 中心-圆环布局');
    });
    
    // 追踪当前选中的节点
    let selectedNode = null;
    let isProcessing = false;  // 防止重复处理
    
    // 异步处理边的显示/隐藏
    async function updateEdgesVisibility(nodeId, show = false) {
        if (isProcessing) return;
        isProcessing = true;
        
        try {
            // 显示加载提示
            showStatusMessage('info', '⏳ 处理中...');
            
            // 使用 setTimeout 让UI有机会响应
            await new Promise(resolve => setTimeout(resolve, 10));
            
            if (show) {
                // 显示所有边 - 批量更新
                const edgesToUpdate = [];
                data.edges.forEach(edge => {
                    edgesToUpdate.push({
                        id: edge.id,
                        hidden: false,
                        label: edge.value > 1.5 ? edge.value.toFixed(1) : ''
                    });
                });
                
                // 分批更新，避免一次性更新太多导致卡顿
                const batchSize = 50;
                for (let i = 0; i < edgesToUpdate.length; i += batchSize) {
                    const batch = edgesToUpdate.slice(i, i + batchSize);
                    data.edges.update(batch);
                    // 让浏览器有时间处理
                    await new Promise(resolve => setTimeout(resolve, 5));
                }
            } else if (nodeId) {
                // 隐藏无关边 - 计算连接的边
                const connectedEdges = new Set();
                data.edges.forEach(edge => {
                    if (edge.from === nodeId || edge.to === nodeId) {
                        connectedEdges.add(edge.id);
                    }
                });
                
                // 准备更新列表
                const edgesToUpdate = [];
                data.edges.forEach(edge => {
                    if (!connectedEdges.has(edge.id)) {
                        edgesToUpdate.push({
                            id: edge.id,
                            hidden: true,
                            label: ''
                        });
                    }
                });
                
                // 分批更新
                const batchSize = 50;
                for (let i = 0; i < edgesToUpdate.length; i += batchSize) {
                    const batch = edgesToUpdate.slice(i, i + batchSize);
                    data.edges.update(batch);
                    await new Promise(resolve => setTimeout(resolve, 5));
                }
            }
        } finally {
            isProcessing = false;
        }
    }
    
    // 添加点击事件
    network.on('click', async function(params) {
        if (isProcessing) return;
        
        if (params.nodes.length > 0) {
            const nodeId = params.nodes[0];
            const node = visNodes.find(n => n.id === nodeId);
            if (node) {
                console.log('选中节点:', node);
                const degree = nodeDegrees[nodeId] || 0;
                const isCore = coreNodes.has(nodeId);
                
                // 如果已有选中节点，先恢复其所有边的显示
                if (selectedNode && selectedNode !== nodeId) {
                    await updateEdgesVisibility(null, true);  // 显示所有边
                    
                    // 让UI有机会更新
                    await new Promise(resolve => setTimeout(resolve, 10));
                }
                
                // 设置新的选中节点
                selectedNode = nodeId;
                
                // 异步隐藏无关的边
                await updateEdgesVisibility(nodeId, false);
                
                // 高亮选中的节点
                network.selectNodes([nodeId]);
                
                // 显示最终的状态消息
                showStatusMessage('info', `${isCore ? '🌟 核心成员' : '👤 成员'}: ${node.label} (连接数: ${degree})`);
            }
        } else {
            // 点击空白处，恢复所有边的显示
            if (selectedNode !== null) {
                selectedNode = null;
                await updateEdgesVisibility(null, true);  // 显示所有边
                network.unselectAll();
                showStatusMessage('success', '✅ 已清除选择');
            }
        }
    });
    
    // 双击事件：重置视图并恢复所有边
    network.on('doubleClick', async function() {
        if (selectedNode !== null) {
            selectedNode = null;
            await updateEdgesVisibility(null, true);  // 显示所有边
            network.unselectAll();
        }
        network.fit({
            animation: {
                duration: 300,
                easingFunction: 'easeInOutQuad'
            }
        });
        console.log('已重置网络图视图');
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
                <span>核心成员 (${coreCount}人) - 中心区域</span>
            </div>
            <div style="display: flex; align-items: center; margin: 4px 0;">
                <span style="width: 12px; height: 12px; background: #1890ff; border-radius: 50%; display: inline-block; margin-right: 8px;"></span>
                <span>普通成员 (${outerCount}人) - 外圈</span>
            </div>
            <div style="color: #888; margin-top: 6px; font-size: 11px;">
                💡 双击重置视图 | 可拖动节点
            </div>
        </div>
    `;
    container.parentElement.style.position = 'relative';
    container.parentElement.appendChild(legend);
}
