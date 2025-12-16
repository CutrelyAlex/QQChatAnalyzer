"""社交网络分析模块 - 智能分析群聊中的互动关系。

使用多维度算法：时间窗口对话分析 + 内容相似性 + @提及 + 连续回复。

TODO: 高分辨率图片保存、全屏化网络图。
"""

from collections import defaultdict
from datetime import datetime
from itertools import combinations
from typing import Any, Dict, List, Optional, Tuple

import re

from .utils import parse_timestamp


class NetworkStats:
    """社交网络统计数据容器"""

    def __init__(self):
        # 网络基本信息
        self.total_nodes = 0
        self.total_edges = 0
        self.nodes = []  # [{'id': qq, 'label': name, 'value': centrality}, ...]
        self.edges = []  # [{'from': qq1, 'to': qq2, 'value': weight, 'from_name': name, 'to_name': name}, ...]
        
        # 优化相关
        self.original_nodes_count = 0  # 过滤前的节点数
        self.original_edges_count = 0  # 过滤前的边数

        # 中心度指标
        self.degree_centrality = {}      # 度中心度
        self.betweenness_centrality = {} # 介数中心度
        self.closeness_centrality = {}   # 接近中心度

        # 互动统计
        self.most_popular_user = None
        self.most_active_pair = None
        self.interaction_matrix = {}  # {qq1: {qq2: weight}}

        # 网络特征
        self.average_clustering = 0.0
        self.network_density = 0.0
        self.average_path_length = 0.0

        # 社区检测
        self.communities = []  # 社区分组

    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            'total_nodes': self.total_nodes,
            'total_edges': self.total_edges,
            'nodes': self.nodes,
            'edges': self.edges,
            'degree_centrality': self.degree_centrality,
            'betweenness_centrality': self.betweenness_centrality,
            'closeness_centrality': self.closeness_centrality,
            'most_popular_user': self.most_popular_user,
            'most_active_pair': self.most_active_pair,
            'interaction_matrix': self.interaction_matrix,
            'average_clustering': round(self.average_clustering, 3),
            'network_density': round(self.network_density, 3),
            'average_path_length': round(self.average_path_length, 3),
            'communities': self.communities
        }


class NetworkAnalyzer:
    """智能社交网络分析器"""

    def __init__(
        self,
        enable_parallel=True,
        max_nodes_for_viz: Optional[int] = None,
        max_edges_for_viz: Optional[int] = None,
        limit_compute: bool = False,
    ):
        self.messages = []
        self.stats = NetworkStats()
        self.qq_to_name = {}  # QQ -> 昵称映射
        self.enable_parallel = enable_parallel  # 启用并行处理

        # 当启用时：在分析前按“最活跃用户Top-N”裁剪消息，减少计算量。
        # 注意：这会改变网络计算的输入范围
        self.limit_compute = limit_compute

        # 算法参数 - 调整为更宽松的设置
        self.conversation_window = 30  # 分钟：对话窗口大小（增加到30分钟）
        self.min_interactions = 1      # 最小互动次数（降低到1）
        self.similarity_threshold = 0.1  # 内容相似度阈值（降低阈值）
        
        # 优化参数
        self.min_edge_weight = 0.2  # 最小边权重（过滤弱关系）
        self.max_nodes_for_viz = max_nodes_for_viz if isinstance(max_nodes_for_viz, int) and max_nodes_for_viz > 0 else 100
        self.max_edges_for_viz = max_edges_for_viz if isinstance(max_edges_for_viz, int) and max_edges_for_viz > 0 else 300

    def load_messages(self, messages: List[Dict[str, Any]]) -> None:
        """
        加载消息列表

        Args:
            messages: 消息列表，每条消息包含: qq, time, content, sender等字段
        """
        # 优先按结构化 timestamp_ms 排序；缺失时回退到 time 字符串
        def _sort_key(m: Dict[str, Any]):
            ts = m.get('timestamp_ms')
            if isinstance(ts, int) and ts > 0:
                return (0, ts)
            # 旧数据/文本导入：time 字符串通常是 YYYY-MM-DD HH:MM:SS
            return (1, str(m.get('time', '') or ''))

        self.messages = sorted(messages, key=_sort_key)

        # 可选：限制计算范围（Top-N 活跃用户）
        if self.limit_compute and self.max_nodes_for_viz is not None:
            user_counts = defaultdict(int)
            for msg in self.messages:
                qq = msg.get('qq', '')
                if qq:
                    user_counts[qq] += 1

            # 允许 N=1（只看一个节点），但通常网络至少需要 2 个节点才有边
            limit_n = max(1, int(self.max_nodes_for_viz))
            top_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:limit_n]
            allowed = set(u for u, _ in top_users)
            self.messages = [m for m in self.messages if m.get('qq', '') in allowed]
        
        # 构建 QQ -> 昵称映射
        for msg in self.messages:
            qq = msg.get('qq', '')
            sender = msg.get('sender', '')
            if msg.get('is_system'):
                continue
            if qq and sender and qq not in self.qq_to_name:
                self.qq_to_name[qq] = sender

    def analyze(self) -> NetworkStats:
        """
        执行完整的社交网络分析

        Returns:
            NetworkStats对象
        """
        if not self.messages:
            return self.stats

        # 按顺序执行各项分析
        self._build_interaction_graph()
        self._calculate_centrality_measures()
        self._detect_communities()
        self._compute_network_metrics()

        return self.stats

    def _build_interaction_graph(self) -> None:
        """T032: 构建智能互动关系图"""

        # 1. 基于时间窗口的对话分析
        conversations = self._extract_conversations()

        # 2. 基于内容的相似性分析
        content_similarities = self._analyze_content_similarity()

        # 3. 综合互动权重计算
        interaction_weights = self._calculate_interaction_weights(conversations, content_similarities)

        # 4. 构建网络图
        self._construct_network_graph(interaction_weights)

    def _extract_conversations(self) -> Dict[Tuple[str, str], int]:
        """
        从时间序列中提取对话关系

        Returns:
            {(qq1, qq2): interaction_count}
        """
        conversations = defaultdict(float)

        # 按时间排序的消息（已排序）
        for i, msg1 in enumerate(self.messages):
            # 系统/撤回事件不参与互动边
            if msg1.get('is_system') or msg1.get('is_recalled'):
                continue
            qq1 = msg1.get('qq', '')
            time1 = self._parse_time(msg1.get('time', ''))

            if not time1 or not qq1:
                continue

            # 在时间窗口内查找可能的对话伙伴
            max_lookahead = min(50, len(self.messages) - i - 1)  # 最多向前看50条
            
            for j in range(i + 1, min(i + 1 + max_lookahead, len(self.messages))):
                msg2 = self.messages[j]
                if msg2.get('is_system') or msg2.get('is_recalled'):
                    continue
                qq2 = msg2.get('qq', '')
                time2 = self._parse_time(msg2.get('time', ''))

                if not time2 or not qq2 or qq1 == qq2:
                    continue

                # 检查是否在对话窗口内
                time_diff = (time2 - time1).total_seconds() / 60  # 分钟

                if time_diff > self.conversation_window:
                    break  # 超出窗口，停止搜索

                # 计算对话可能性
                conversation_score = self._calculate_conversation_score(msg1, msg2, time_diff)

                if conversation_score > 0:
                    # 对称添加边
                    pair = tuple(sorted([qq1, qq2]))
                    conversations[pair] += conversation_score

        return dict(conversations)

    def _calculate_conversation_score(self, msg1: Dict, msg2: Dict, time_diff: float) -> float:
        """
        计算两条消息是否构成对话的分数

        Args:
            msg1: 第一条消息
            msg2: 第二条消息
            time_diff: 时间差（分钟）

        Returns:
            对话分数 (0-1)
        """
        score = 0.0

        # 1. 时间 proximity 分数 - 更宽松的评分
        if time_diff <= 5:
            score += 0.6  # 5分钟内回复，很可能是对话
        elif time_diff <= 15:
            score += 0.4  # 15分钟内，可能在讨论
        elif time_diff <= 30:
            score += 0.2  # 30分钟内，可能性较低
        elif time_diff <= self.conversation_window:
            score += 0.1  # 在窗口内但时间较长

        # 2. @提及加分
        content1 = msg1.get('content', '')
        content2 = msg2.get('content', '')
        qq1 = msg1.get('qq', '')
        qq2 = msg2.get('qq', '')

        m1_mentions = msg1.get('mentions')
        m2_mentions = msg2.get('mentions')
        if not isinstance(m1_mentions, list):
            m1_mentions = []
        if not isinstance(m2_mentions, list):
            m2_mentions = []

        # mentions 列表里可能是 participantId 或 name，这里只对“精确 id”做加分
        if qq2 and (qq2 in m1_mentions):
            score += 0.55
        elif qq1 and (qq1 in m2_mentions):
            score += 0.55
        elif (qq2 and f'@{qq2}' in content1) or (qq1 and f'@{qq1}' in content2):
            score += 0.35  # 旧格式兜底

        # 2.5 reply 加分（若能解析到回复对象）
        if msg2.get('reply_to_qq') and msg2.get('reply_to_qq') == qq1:
            score += 0.6
        elif msg1.get('reply_to_qq') and msg1.get('reply_to_qq') == qq2:
            score += 0.6

        # 3. 内容相关性（简单检查）
        if self._messages_related(content1, content2):
            score += 0.2

        # 4. 基础互动分数 - 只要在时间窗口内就有基础分数
        if time_diff <= self.conversation_window:
            score += 0.1

        return min(score, 1.0)  # 最大分数为1

    def _messages_related(self, content1: str, content2: str) -> bool:
        """简单检查两条消息是否相关"""
        if not content1 or not content2:
            return False

        # 移除标点符号和表情
        clean1 = re.sub(r'[^\w\s]', '', content1)
        clean2 = re.sub(r'[^\w\s]', '', content2)

        # 计算词重叠度
        words1 = set(clean1.split())
        words2 = set(clean2.split())

        if not words1 or not words2:
            return False

        overlap = len(words1 & words2)
        union = len(words1 | words2)

        return overlap / union > 0.2  # 20%词重叠

    def _analyze_content_similarity(self) -> Dict[Tuple[str, str], float]:
        """
        分析用户间的长期内容相似性 - 支持并行计算

        Returns:
            {(qq1, qq2): similarity_score}
        """
        # 收集每个用户的消息内容
        user_contents = defaultdict(list)

        for msg in self.messages:
            if msg.get('is_system') or msg.get('is_recalled'):
                continue
            qq = msg.get('qq', '')
            content = msg.get('content', '').strip()
            # 非文本消息不参与“内容相似性”
            mt = str(msg.get('message_type') or 'text')
            if mt not in ('text', 'reply') and not content:
                continue
            if qq and content and len(content) > 2:  # 过滤太短的消息
                user_contents[qq].append(content)

        # 获取用户对
        user_pairs = list(combinations(user_contents.keys(), 2))
        
        # 如果启用并行处理且用户对较多
        if self.enable_parallel and len(user_pairs) > 100:
            return self._analyze_similarity_parallel(user_contents, user_pairs)
        else:
            return self._analyze_similarity_sequential(user_contents, user_pairs)

    def _analyze_similarity_sequential(self, user_contents: Dict, user_pairs: List) -> Dict:
        """顺序计算相似性"""
        similarities = {}
        for qq1, qq2 in user_pairs:
            contents1 = user_contents[qq1]
            contents2 = user_contents[qq2]

            if len(contents1) >= 2 and len(contents2) >= 2:
                similarity = self._calculate_user_similarity_simple(contents1, contents2)
                if similarity > self.similarity_threshold:
                    pair = tuple(sorted([qq1, qq2]))
                    similarities[pair] = similarity

        return similarities

    def _analyze_similarity_parallel(self, user_contents: Dict, user_pairs: List) -> Dict:
        """并行计算相似性"""
        try:
            from multiprocessing import Pool, cpu_count
            from functools import partial
            
            # 准备参数
            calc_func = partial(self._calc_pair_similarity, user_contents=user_contents)
            
            # 使用进程池
            num_processes = min(cpu_count() - 1, 4)  # 最多4个进程
            with Pool(num_processes) as pool:
                results = pool.map(calc_func, user_pairs, chunksize=10)
            
            # 合并结果
            similarities = {}
            for pair, similarity in results:
                if similarity > self.similarity_threshold:
                    similarities[pair] = similarity
            
            return similarities
        except Exception as e:
            # 并行失败，回退到顺序计算
            print(f"Parallel processing failed: {e}, falling back to sequential")
            return self._analyze_similarity_sequential(user_contents, user_pairs)

    @staticmethod
    def _calc_pair_similarity(pair, user_contents):
        """计算单个用户对的相似性（用于并行处理）"""
        qq1, qq2 = pair
        contents1 = user_contents.get(qq1, [])
        contents2 = user_contents.get(qq2, [])
        
        if len(contents1) < 2 or len(contents2) < 2:
            return pair, 0.0
        
        # 这里需要重新实现相似度计算（不能用self）
        words1 = set()
        words2 = set()
        
        for content in contents1:
            words1.update(NetworkAnalyzer._tokenize_static(content))
        
        for content in contents2:
            words2.update(NetworkAnalyzer._tokenize_static(content))
        
        if not words1 or not words2:
            return pair, 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        similarity = intersection / union if union > 0 else 0.0
        
        return pair, similarity

    @staticmethod
    def _tokenize_static(text: str) -> List[str]:
        """静态分词方法（用于并行处理）"""
        text = re.sub(r'[^\w\s]', '', text)
        return [word for word in text.split() if len(word) > 1]

    def _calculate_user_similarity_simple(self, contents1: List[str], contents2: List[str]) -> float:
        """计算两个用户的消息内容相似性"""
        # 收集所有词
        words1 = set()
        words2 = set()

        for content in contents1:
            words1.update(self._tokenize(content))

        for content in contents2:
            words2.update(self._tokenize(content))

        if not words1 or not words2:
            return 0.0

        # 计算Jaccard相似度
        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def _tokenize(self, text: str) -> List[str]:
        """简单分词"""
        # 移除标点和表情
        text = re.sub(r'[^\w\s]', '', text)
        return [word for word in text.split() if len(word) > 1]

    def _calculate_interaction_weights(self, conversations: Dict, content_similarities: Dict) -> Dict[Tuple[str, str], float]:
        """
        综合计算互动权重

        Args:
            conversations: 对话互动权重
            content_similarities: 内容相似性权重

        Returns:
            综合权重
        """
        weights = defaultdict(float)

        # 合并权重
        for pair, conv_weight in conversations.items():
            weights[pair] += conv_weight * 0.7  # 对话权重70%

        for pair, sim_weight in content_similarities.items():
            weights[pair] += sim_weight * 0.3  # 相似性权重30%

        # 过滤低权重关系
        return {pair: weight for pair, weight in weights.items() if weight >= self.min_interactions}

    def _construct_network_graph(self, interaction_weights: Dict[Tuple[str, str], float]) -> None:
        """构建最终的网络图"""

        # 获取所有节点
        all_users = set()
        for pair in interaction_weights.keys():
            all_users.update(pair)

        # 记录原始数量
        self.stats.original_nodes_count = len(all_users)
        self.stats.original_edges_count = len(interaction_weights)
        
        # 第一步：过滤边权重（移除过弱的关系）
        filtered_weights = {
            pair: weight for pair, weight in interaction_weights.items()
            if weight >= self.min_edge_weight
        }
        
        # 第二步：过滤节点（只保留过滤后边中的节点）
        filtered_users = set()
        for pair in filtered_weights.keys():
            filtered_users.update(pair)
        
        # 第三步：如果节点过多，进行进一步过滤（保留度数最高的节点）
        if len(filtered_users) > self.max_nodes_for_viz:
            # 计算每个节点的度数
            node_degrees = defaultdict(int)
            for pair, weight in filtered_weights.items():
                node_degrees[pair[0]] += 1
                node_degrees[pair[1]] += 1
            
            # 保留度数最高的节点
            top_users = sorted(node_degrees.items(), key=lambda x: x[1], reverse=True)[:self.max_nodes_for_viz]
            top_user_set = set(u for u, _ in top_users)
            
            # 过滤边（只保留top用户间的边）
            filtered_weights = {
                pair: weight for pair, weight in filtered_weights.items()
                if pair[0] in top_user_set and pair[1] in top_user_set
            }
            filtered_users = top_user_set
        
        # 第四步：如果边过多，按权重过滤
        if len(filtered_weights) > self.max_edges_for_viz:
            # 保留权重最高的边
            sorted_edges = sorted(filtered_weights.items(), key=lambda x: x[1], reverse=True)[:self.max_edges_for_viz]
            filtered_weights = dict(sorted_edges)
            
            # 重新计算节点（可能某些节点会被移除）
            filtered_users = set()
            for pair in filtered_weights.keys():
                filtered_users.update(pair)
        
        # 构建节点列表（包含昵称）
        self.stats.total_nodes = len(filtered_users)
        self.stats.nodes = [
            {
                'id': qq,
                'label': self.qq_to_name.get(qq, qq),  # 使用昵称
                'value': 1,  # 后续用中心度更新
                'title': f'{self.qq_to_name.get(qq, qq)} ({qq})'  # 鼠标悬停显示全名和QQ
            }
            for qq in sorted(filtered_users)
        ]

        # 构建边列表（包含名称）
        self.stats.edges = [
            {
                'from': pair[0],
                'to': pair[1],
                'from_name': self.qq_to_name.get(pair[0], pair[0]),
                'to_name': self.qq_to_name.get(pair[1], pair[1]),
                'value': weight,
                'title': f'{self.qq_to_name.get(pair[0], pair[0])} ↔ {self.qq_to_name.get(pair[1], pair[1])} (强度: {weight:.2f})'
            }
            for pair, weight in filtered_weights.items()
        ]

        self.stats.total_edges = len(self.stats.edges)
        self.stats.interaction_matrix = {pair[0] + '_' + pair[1]: weight for pair, weight in filtered_weights.items()}

    def _calculate_centrality_measures(self) -> None:
        """T033: 计算中心度指标"""

        if self.stats.total_nodes == 0:
            return

        # 构建邻接表和边权重
        adj_list = defaultdict(set)
        edge_weights = {}
        for edge in self.stats.edges:
            u, v = edge['from'], edge['to']
            adj_list[u].add(v)
            adj_list[v].add(u)
            edge_weights[(u, v)] = edge['value']
            edge_weights[(v, u)] = edge['value']

        nodes = [n['id'] for n in self.stats.nodes]
        n = len(nodes)

        # 1. 度中心度 (Degree Centrality)
        degree_count = defaultdict(float)
        for node in nodes:
            # 加权度数
            for neighbor in adj_list[node]:
                degree_count[node] += edge_weights.get((node, neighbor), 1)
        
        max_degree = max(degree_count.values()) if degree_count else 1
        self.stats.degree_centrality = {
            node: count / max_degree for node, count in degree_count.items()
        }

        # 2. 介数中心度 (Betweenness Centrality) - Brandes算法
        betweenness = {node: 0.0 for node in nodes}
        
        for s in nodes:
            # BFS 从 s 开始
            S = []  # 栈，按照访问顺序
            P = {v: [] for v in nodes}  # 前驱节点
            sigma = {v: 0 for v in nodes}  # 最短路径数
            sigma[s] = 1
            d = {v: -1 for v in nodes}  # 距离
            d[s] = 0
            Q = [s]  # 队列
            
            while Q:
                v = Q.pop(0)
                S.append(v)
                for w in adj_list[v]:
                    # w 首次被发现
                    if d[w] < 0:
                        Q.append(w)
                        d[w] = d[v] + 1
                    # 最短路径到 w 经过 v
                    if d[w] == d[v] + 1:
                        sigma[w] += sigma[v]
                        P[w].append(v)
            
            # 累积
            delta = {v: 0.0 for v in nodes}
            while S:
                w = S.pop()
                for v in P[w]:
                    delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w])
                if w != s:
                    betweenness[w] += delta[w]
        
        # 归一化
        if n > 2:
            norm = (n - 1) * (n - 2)
            betweenness = {k: v / norm for k, v in betweenness.items()}
        
        self.stats.betweenness_centrality = betweenness

        # 3. 接近中心度 (Closeness Centrality)
        closeness = {}
        for node in nodes:
            # BFS 计算最短路径
            distances = {v: float('inf') for v in nodes}
            distances[node] = 0
            Q = [node]
            
            while Q:
                v = Q.pop(0)
                for w in adj_list[v]:
                    if distances[w] == float('inf'):
                        distances[w] = distances[v] + 1
                        Q.append(w)
            
            # 计算可达节点的总距离
            reachable = [d for d in distances.values() if d < float('inf') and d > 0]
            if reachable:
                closeness[node] = len(reachable) / sum(reachable)
            else:
                closeness[node] = 0.0
        
        self.stats.closeness_centrality = closeness

        # 更新节点大小（使用度中心度）
        for node in self.stats.nodes:
            qq = node['id']
            centrality = self.stats.degree_centrality.get(qq, 0)
            node['value'] = max(centrality, 0.1)  # 最小值0.1确保可见

        # 找出最受欢迎的用户（使用综合中心度）
        if self.stats.degree_centrality:
            # 综合评分 = 0.5*度中心度 + 0.3*介数中心度 + 0.2*接近中心度
            combined_scores = {}
            for node in nodes:
                dc = self.stats.degree_centrality.get(node, 0)
                bc = self.stats.betweenness_centrality.get(node, 0)
                cc = self.stats.closeness_centrality.get(node, 0)
                combined_scores[node] = 0.5 * dc + 0.3 * bc + 0.2 * cc
            
            most_popular = max(combined_scores.items(), key=lambda x: x[1])
            self.stats.most_popular_user = {
                'qq': most_popular[0],
                'name': self.qq_to_name.get(most_popular[0], most_popular[0]),
                'centrality': most_popular[1],
                'degree': self.stats.degree_centrality.get(most_popular[0], 0),
                'betweenness': self.stats.betweenness_centrality.get(most_popular[0], 0),
                'closeness': self.stats.closeness_centrality.get(most_popular[0], 0)
            }

    def _detect_communities(self) -> None:
        """T034-T035: 社区检测 - 使用标签传播算法"""

        if not self.stats.edges:
            return

        # 构建邻接表和边权重
        adj_list = defaultdict(set)
        edge_weights = {}
        for edge in self.stats.edges:
            u, v = edge['from'], edge['to']
            adj_list[u].add(v)
            adj_list[v].add(u)
            edge_weights[(u, v)] = edge['value']
            edge_weights[(v, u)] = edge['value']

        nodes = [n['id'] for n in self.stats.nodes]
        
        # 标签传播算法 (Label Propagation)
        # 初始化：每个节点有自己的标签
        labels = {node: i for i, node in enumerate(nodes)}
        
        import random
        max_iterations = 100
        
        for iteration in range(max_iterations):
            changed = False
            random.shuffle(nodes)  # 随机顺序
            
            for node in nodes:
                if not adj_list[node]:
                    continue
                
                # 统计邻居标签的加权频率
                label_weights = defaultdict(float)
                for neighbor in adj_list[node]:
                    weight = edge_weights.get((node, neighbor), 1)
                    label_weights[labels[neighbor]] += weight
                
                if label_weights:
                    # 选择权重最大的标签
                    max_weight = max(label_weights.values())
                    best_labels = [l for l, w in label_weights.items() if w == max_weight]
                    new_label = random.choice(best_labels)
                    
                    if labels[node] != new_label:
                        labels[node] = new_label
                        changed = True
            
            if not changed:
                break
        
        # 收集社区
        community_members = defaultdict(list)
        for node, label in labels.items():
            community_members[label].append(node)
        
        # 只保留多于1人的社区
        self.stats.communities = [
            sorted(members) for members in community_members.values()
            if len(members) > 1
        ]

        # 找出最活跃的互动对
        if self.stats.edges:
            most_active = max(self.stats.edges, key=lambda x: x['value'])
            self.stats.most_active_pair = {
                'pair': [most_active['from'], most_active['to']],
                'name1': self.qq_to_name.get(most_active['from'], most_active['from']),
                'name2': self.qq_to_name.get(most_active['to'], most_active['to']),
                'weight': most_active['value']
            }

    def _compute_network_metrics(self) -> None:
        """计算网络整体指标"""

        if self.stats.total_nodes <= 1:
            return

        # 构建邻接表
        adj_list = defaultdict(set)
        for edge in self.stats.edges:
            adj_list[edge['from']].add(edge['to'])
            adj_list[edge['to']].add(edge['from'])

        nodes = [n['id'] for n in self.stats.nodes]
        n = len(nodes)

        # 1. 网络密度 (Network Density)
        max_possible_edges = n * (n - 1) / 2
        self.stats.network_density = self.stats.total_edges / max_possible_edges if max_possible_edges > 0 else 0

        # 2. 平均聚类系数 (Average Clustering Coefficient)
        clustering_coefficients = []
        for node in nodes:
            neighbors = list(adj_list[node])
            k = len(neighbors)
            if k < 2:
                clustering_coefficients.append(0.0)
                continue
            
            # 计算邻居之间的边数
            edges_between_neighbors = 0
            for i in range(len(neighbors)):
                for j in range(i + 1, len(neighbors)):
                    if neighbors[j] in adj_list[neighbors[i]]:
                        edges_between_neighbors += 1
            
            # 聚类系数 = 邻居之间的实际边数 / 邻居之间可能的最大边数
            max_edges = k * (k - 1) / 2
            cc = edges_between_neighbors / max_edges if max_edges > 0 else 0
            clustering_coefficients.append(cc)
        
        self.stats.average_clustering = sum(clustering_coefficients) / len(clustering_coefficients) if clustering_coefficients else 0

        # 3. 平均路径长度 (Average Path Length) - BFS计算所有最短路径
        total_path_length = 0
        path_count = 0
        
        for source in nodes:
            distances = {v: float('inf') for v in nodes}
            distances[source] = 0
            Q = [source]
            
            while Q:
                v = Q.pop(0)
                for w in adj_list[v]:
                    if distances[w] == float('inf'):
                        distances[w] = distances[v] + 1
                        Q.append(w)
            
            for target in nodes:
                if target != source and distances[target] < float('inf'):
                    total_path_length += distances[target]
                    path_count += 1
        
        self.stats.average_path_length = total_path_length / path_count if path_count > 0 else 0

    def _parse_time(self, time_str: str) -> Optional[datetime]:
        """解析时间字符串"""
        return parse_timestamp(time_str)