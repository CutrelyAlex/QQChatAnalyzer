"""社交网络分析核心模块。"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from itertools import combinations
from typing import Any, Dict, List, Optional, Tuple

from .network_metrics import calculate_centrality_measures, compute_network_metrics, detect_communities
from .network_stats import NetworkStats
from .network_text import calc_pair_similarity, calculate_user_similarity, messages_related
from .txt_process import parse_timestamp


class NetworkAnalyzer:
    """智能社交网络分析器。"""

    def __init__(
        self,
        enable_parallel=True,
        max_nodes_for_viz: Optional[int] = None,
        max_edges_for_viz: Optional[int] = None,
        limit_compute: bool = False,
    ):
        self.messages = []
        self.stats = NetworkStats()
        self.qq_to_name = {}
        self.enable_parallel = enable_parallel
        self.limit_compute = limit_compute

        self.conversation_window = 30
        self.min_interactions = 1
        self.similarity_threshold = 0.1

        self.min_edge_weight = 0.2
        self.max_nodes_for_viz = max_nodes_for_viz if isinstance(max_nodes_for_viz, int) and max_nodes_for_viz > 0 else 100
        self.max_edges_for_viz = max_edges_for_viz if isinstance(max_edges_for_viz, int) and max_edges_for_viz > 0 else 300

    def load_messages(self, messages: List[Dict[str, Any]]) -> None:
        def _sort_key(message: Dict[str, Any]):
            ts = message.get('timestamp_ms')
            if isinstance(ts, int) and ts > 0:
                return (0, ts)
            return (1, str(message.get('time', '') or ''))

        self.messages = sorted(messages, key=_sort_key)

        if self.limit_compute and self.max_nodes_for_viz is not None:
            user_counts = defaultdict(int)
            for message in self.messages:
                qq = message.get('qq', '')
                if qq:
                    user_counts[qq] += 1

            limit_n = max(1, int(self.max_nodes_for_viz))
            top_users = sorted(user_counts.items(), key=lambda item: item[1], reverse=True)[:limit_n]
            allowed = {user for user, _ in top_users}
            self.messages = [message for message in self.messages if message.get('qq', '') in allowed]

        for message in self.messages:
            qq = message.get('qq', '')
            sender = message.get('sender', '')
            if message.get('is_system'):
                continue
            if qq and sender and qq not in self.qq_to_name:
                self.qq_to_name[qq] = sender

    def analyze(self) -> NetworkStats:
        if not self.messages:
            return self.stats

        self._build_interaction_graph()
        calculate_centrality_measures(self.stats, self.qq_to_name)
        detect_communities(self.stats, self.qq_to_name)
        compute_network_metrics(self.stats)
        return self.stats

    def _build_interaction_graph(self) -> None:
        conversations = self._extract_conversations()
        content_similarities = self._analyze_content_similarity()
        interaction_weights = self._calculate_interaction_weights(conversations, content_similarities)
        self._construct_network_graph(interaction_weights)

    def _extract_conversations(self) -> Dict[Tuple[str, str], int]:
        conversations = defaultdict(float)

        for index, msg1 in enumerate(self.messages):
            if msg1.get('is_system') or msg1.get('is_recalled'):
                continue
            qq1 = msg1.get('qq', '')
            time1 = self._parse_time(msg1.get('time', ''))

            if not time1 or not qq1:
                continue

            max_lookahead = min(50, len(self.messages) - index - 1)
            for next_index in range(index + 1, min(index + 1 + max_lookahead, len(self.messages))):
                msg2 = self.messages[next_index]
                if msg2.get('is_system') or msg2.get('is_recalled'):
                    continue
                qq2 = msg2.get('qq', '')
                time2 = self._parse_time(msg2.get('time', ''))

                if not time2 or not qq2 or qq1 == qq2:
                    continue

                time_diff = (time2 - time1).total_seconds() / 60
                if time_diff > self.conversation_window:
                    break

                conversation_score = self._calculate_conversation_score(msg1, msg2, time_diff)
                if conversation_score > 0:
                    pair = tuple(sorted([qq1, qq2]))
                    conversations[pair] += conversation_score

        return dict(conversations)

    def _calculate_conversation_score(self, msg1: Dict, msg2: Dict, time_diff: float) -> float:
        score = 0.0

        if time_diff <= 5:
            score += 0.6
        elif time_diff <= 15:
            score += 0.4
        elif time_diff <= 30:
            score += 0.2
        elif time_diff <= self.conversation_window:
            score += 0.1

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

        if qq2 and (qq2 in m1_mentions):
            score += 0.55
        elif qq1 and (qq1 in m2_mentions):
            score += 0.55
        elif (qq2 and f'@{qq2}' in content1) or (qq1 and f'@{qq1}' in content2):
            score += 0.35

        if msg2.get('reply_to_qq') and msg2.get('reply_to_qq') == qq1:
            score += 0.6
        elif msg1.get('reply_to_qq') and msg1.get('reply_to_qq') == qq2:
            score += 0.6

        if messages_related(content1, content2):
            score += 0.2

        if time_diff <= self.conversation_window:
            score += 0.1

        return min(score, 1.0)

    def _analyze_content_similarity(self) -> Dict[Tuple[str, str], float]:
        user_contents = defaultdict(list)
        for message in self.messages:
            if message.get('is_system') or message.get('is_recalled'):
                continue
            qq = message.get('qq', '')
            content = str(message.get('content', '') or '').strip()
            if not content:
                continue
            if qq and len(content) > 2:
                user_contents[qq].append(content)

        user_pairs = list(combinations(user_contents.keys(), 2))
        if self.enable_parallel and len(user_pairs) > 100:
            return self._analyze_similarity_parallel(user_contents, user_pairs)
        return self._analyze_similarity_sequential(user_contents, user_pairs)

    def _analyze_similarity_sequential(self, user_contents: Dict[str, List[str]], user_pairs: List[Tuple[str, str]]) -> Dict:
        similarities = {}
        for qq1, qq2 in user_pairs:
            contents1 = user_contents[qq1]
            contents2 = user_contents[qq2]

            if len(contents1) >= 2 and len(contents2) >= 2:
                similarity = calculate_user_similarity(contents1, contents2)
                if similarity > self.similarity_threshold:
                    pair = tuple(sorted([qq1, qq2]))
                    similarities[pair] = similarity

        return similarities

    def _analyze_similarity_parallel(self, user_contents: Dict[str, List[str]], user_pairs: List[Tuple[str, str]]) -> Dict:
        try:
            from functools import partial
            from multiprocessing import Pool, cpu_count

            calc_func = partial(calc_pair_similarity, user_contents=user_contents)
            num_processes = min(cpu_count() - 1, 4)
            with Pool(num_processes) as pool:
                results = pool.map(calc_func, user_pairs, chunksize=10)

            similarities = {}
            for pair, similarity in results:
                if similarity > self.similarity_threshold:
                    similarities[pair] = similarity
            return similarities
        except Exception as exc:
            print(f"Parallel processing failed: {exc}, falling back to sequential")
            return self._analyze_similarity_sequential(user_contents, user_pairs)

    def _calculate_interaction_weights(self, conversations: Dict, content_similarities: Dict) -> Dict[Tuple[str, str], float]:
        weights = defaultdict(float)

        for pair, conv_weight in conversations.items():
            weights[pair] += conv_weight * 0.7
        for pair, sim_weight in content_similarities.items():
            weights[pair] += sim_weight * 0.3

        return {pair: weight for pair, weight in weights.items() if weight >= self.min_interactions}

    def _construct_network_graph(self, interaction_weights: Dict[Tuple[str, str], float]) -> None:
        all_users = set()
        for pair in interaction_weights.keys():
            all_users.update(pair)

        self.stats.original_nodes_count = len(all_users)
        self.stats.original_edges_count = len(interaction_weights)

        filtered_weights = {
            pair: weight for pair, weight in interaction_weights.items()
            if weight >= self.min_edge_weight
        }

        filtered_users = set()
        for pair in filtered_weights.keys():
            filtered_users.update(pair)

        if len(filtered_users) > self.max_nodes_for_viz:
            node_degrees = defaultdict(int)
            for pair, _weight in filtered_weights.items():
                node_degrees[pair[0]] += 1
                node_degrees[pair[1]] += 1

            top_users = sorted(node_degrees.items(), key=lambda item: item[1], reverse=True)[:self.max_nodes_for_viz]
            top_user_set = {user for user, _ in top_users}
            filtered_weights = {
                pair: weight for pair, weight in filtered_weights.items()
                if pair[0] in top_user_set and pair[1] in top_user_set
            }
            filtered_users = top_user_set

        if len(filtered_weights) > self.max_edges_for_viz:
            sorted_edges = sorted(filtered_weights.items(), key=lambda item: item[1], reverse=True)[:self.max_edges_for_viz]
            filtered_weights = dict(sorted_edges)
            filtered_users = set()
            for pair in filtered_weights.keys():
                filtered_users.update(pair)

        self.stats.total_nodes = len(filtered_users)
        self.stats.nodes = [
            {
                'id': qq,
                'label': self.qq_to_name.get(qq, qq),
                'value': 1,
                'title': f'{self.qq_to_name.get(qq, qq)} ({qq})',
            }
            for qq in sorted(filtered_users)
        ]

        self.stats.edges = [
            {
                'from': pair[0],
                'to': pair[1],
                'from_name': self.qq_to_name.get(pair[0], pair[0]),
                'to_name': self.qq_to_name.get(pair[1], pair[1]),
                'value': weight,
                'title': f'{self.qq_to_name.get(pair[0], pair[0])} ↔ {self.qq_to_name.get(pair[1], pair[1])} (强度: {weight:.2f})',
            }
            for pair, weight in filtered_weights.items()
        ]

        self.stats.total_edges = len(self.stats.edges)
        self.stats.interaction_matrix = {f'{pair[0]}_{pair[1]}': weight for pair, weight in filtered_weights.items()}

    def _parse_time(self, time_str: str) -> Optional[datetime]:
        return parse_timestamp(time_str)
