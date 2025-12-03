/**
 * QQ聊天记录分析系统 - 社交网络图模块
 * 网络图渲染和交互功能
 */

// ============ 社交网络图表函数 ============

function renderNetworkGraph(nodes, edges) {
    // """优化版网络图渲染 - 显示昵称、稳定物理模拟、优化边渲染"""
    const container = document.getElementById('network-graph');
    
    if (!container) return;
    
    // 准备节点数据 - 使用昵称而非QQ
    const visNodes = nodes.map(node => ({
        id: node.id,
        label: node.label || node.id,  // 使用昵称
        value: Math.max(node.value * 25, 15), // 节点大小，最小15最大50
        title: node.title || `${node.label || node.id} (${node.id})`,  // 鼠标悬停显示
        color: {
            background: '#1890ff',
            border: '#0050b3',
            highlight: {
                background: '#40a9ff',
                border: '#0050b3'
            }
        },
        font: {
            size: 13,
            color: '#000',  // 改为黑色，防止和蓝色背景重合
            bold: {
                color: '#000'
            }
        }
    }));
    
    // 准备边数据 - 优化标签和样式
    const visEdges = edges.map(edge => {
        // 根据权重调整边的宽度和颜色
        const weightNorm = Math.min(edge.value / 2, 1); // 权重归一化
        return {
            from: edge.from,
            to: edge.to,
            value: edge.value,
            label: edge.value > 1 ? edge.value.toFixed(1) : '',  // 权重大于1时显示标签
            title: edge.title || `${edge.from_name} ↔ ${edge.to_name} (强度: ${edge.value.toFixed(2)})`,
            width: Math.max(Math.min(edge.value, 3), 0.5),  // 边宽 0.5-3
            color: {
                color: `rgba(24, 144, 255, ${0.3 + weightNorm * 0.4})`,  // 根据权重调整透明度
                highlight: 'rgba(64, 169, 255, 0.8)'
            },
            smooth: {
                type: 'cubicBezier'
            }
        };
    });
    
    // 配置选项 - 稳定的物理模拟参数
    const options = {
        nodes: {
            shape: 'dot',
            scaling: {
                min: 15,
                max: 50
            },
            font: {
                size: 13,
                face: 'Arial',
                multi: true
            },
            borderWidth: 2,
            borderWidthSelected: 4,
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
                color: 'rgba(24, 144, 255, 0.3)',
                highlight: 'rgba(64, 169, 255, 0.8)',
                hover: 'rgba(64, 169, 255, 0.6)'
            },
            scaling: {
                min: 0.5,
                max: 3
            },
            font: {
                size: 11,
                color: '#666'
            },
            smooth: {
                type: 'cubicBezier',
                forceDirection: 'none'
            },
            arrows: {
                to: {
                    enabled: false
                }
            }
        },
        physics: {
            enabled: true,
            stabilization: {
                iterations: 200,  // 稳定化迭代次数
                fit: true,
                updateInterval: 25
            },
            barnesHut: {
                gravitationalConstant: -26000,  // 降低（增加排斥力）
                centralGravity: 0.15,           // 降低（减少向中心拉扯）
                springLength: 200,              // 增加（更疏散）
                springConstant: 0.01,           // 降低（减少弹性）
                damping: 0.4,                   // 增加（增加阻尼，更快稳定）
                avoidOverlap: 0.5               // 增加避免重叠
            },
            timestep: 0.5,                      // 时间步长
            adaptiveTimestep: true              // 自适应时间步长
        },
        interaction: {
            hover: true,
            tooltipDelay: 300,
            navigationButtons: true,            // 显示导航按钮
            keyboard: true,                     // 支持键盘操作
            zoomView: true,
            dragView: true
        },
        layout: {
            randomSeed: 42  // 固定随机种子，确保布局一致性
        }
    };
    
    // 创建网络图
    const data = {
        nodes: new vis.DataSet(visNodes),
        edges: new vis.DataSet(visEdges)
    };
    
    const network = new vis.Network(container, data, options);
    
    // 等待物理模拟稳定
    network.once('stabilizationIterationsDone', () => {
        // 稳定完成后，禁用物理模拟以避免抖动
        network.setOptions({
            physics: false
        });
        console.log('网络图物理模拟已稳定');
    });
    
    // 设置稳定化超时（10秒后无论如何都稳定）
    setTimeout(() => {
        network.setOptions({
            physics: false
        });
        console.log('网络图稳定化超时，已禁用物理模拟');
    }, 10000);
    
    // 添加点击事件
    network.on('click', function(params) {
        if (params.nodes.length > 0) {
            const nodeId = params.nodes[0];
            const node = visNodes.find(n => n.id === nodeId);
            if (node) {
                console.log('选中节点:', node);
                showStatusMessage('info', `已选中用户: ${node.label} (${node.id})`);
            }
        }
    });
    
    // 双击事件：重置视图
    network.on('doubleClick', function() {
        network.fit();
        console.log('已重置网络图视图');
    });
    
    // 存储网络实例供后续使用
    window.currentNetwork = network;
}
