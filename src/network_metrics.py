from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict


def _build_graph_structures(stats):
    adj_list = defaultdict(set)
    edge_weights = {}
    for edge in stats.edges:
        u, v = edge['from'], edge['to']
        adj_list[u].add(v)
        adj_list[v].add(u)
        edge_weights[(u, v)] = edge['value']
        edge_weights[(v, u)] = edge['value']
    return adj_list, edge_weights


def calculate_centrality_measures(stats, qq_to_name: Dict[str, str]) -> None:
    if stats.total_nodes == 0:
        return

    adj_list, edge_weights = _build_graph_structures(stats)
    nodes = [n['id'] for n in stats.nodes]
    n = len(nodes)

    degree_count = defaultdict(float)
    for node in nodes:
        for neighbor in adj_list[node]:
            degree_count[node] += edge_weights.get((node, neighbor), 1)

    max_degree = max(degree_count.values()) if degree_count else 1
    stats.degree_centrality = {
        node: count / max_degree for node, count in degree_count.items()
    }

    betweenness = {node: 0.0 for node in nodes}
    for source in nodes:
        stack = []
        predecessors = {node: [] for node in nodes}
        sigma = {node: 0 for node in nodes}
        sigma[source] = 1
        distance = {node: -1 for node in nodes}
        distance[source] = 0
        queue = deque([source])

        while queue:
            node = queue.popleft()
            stack.append(node)
            for neighbor in adj_list[node]:
                if distance[neighbor] < 0:
                    queue.append(neighbor)
                    distance[neighbor] = distance[node] + 1
                if distance[neighbor] == distance[node] + 1:
                    sigma[neighbor] += sigma[node]
                    predecessors[neighbor].append(node)

        delta = {node: 0.0 for node in nodes}
        while stack:
            node = stack.pop()
            for predecessor in predecessors[node]:
                delta[predecessor] += (sigma[predecessor] / sigma[node]) * (1 + delta[node])
            if node != source:
                betweenness[node] += delta[node]

    if n > 2:
        norm = (n - 1) * (n - 2)
        betweenness = {key: value / norm for key, value in betweenness.items()}
    stats.betweenness_centrality = betweenness

    closeness = {}
    for node in nodes:
        distances = {other: float('inf') for other in nodes}
        distances[node] = 0
        queue = deque([node])

        while queue:
            current = queue.popleft()
            for neighbor in adj_list[current]:
                if distances[neighbor] == float('inf'):
                    distances[neighbor] = distances[current] + 1
                    queue.append(neighbor)

        reachable = [value for value in distances.values() if value < float('inf') and value > 0]
        closeness[node] = (len(reachable) / sum(reachable)) if reachable else 0.0
    stats.closeness_centrality = closeness

    connector_candidates = sorted(
        (
            {
                'qq': node,
                'name': qq_to_name.get(node, node),
                'betweenness': stats.betweenness_centrality.get(node, 0),
                'degree': stats.degree_centrality.get(node, 0),
            }
            for node in nodes
        ),
        key=lambda item: (item['betweenness'], item['degree']),
        reverse=True,
    )
    stats.key_connectors = [item for item in connector_candidates if item['betweenness'] > 0][:3]

    for node in stats.nodes:
        qq = node['id']
        centrality = stats.degree_centrality.get(qq, 0)
        node['value'] = max(centrality, 0.1)

    if stats.degree_centrality:
        combined_scores = {}
        for node in nodes:
            dc = stats.degree_centrality.get(node, 0)
            bc = stats.betweenness_centrality.get(node, 0)
            cc = stats.closeness_centrality.get(node, 0)
            combined_scores[node] = 0.5 * dc + 0.3 * bc + 0.2 * cc

        most_popular = max(combined_scores.items(), key=lambda item: item[1])
        stats.most_popular_user = {
            'qq': most_popular[0],
            'name': qq_to_name.get(most_popular[0], most_popular[0]),
            'centrality': most_popular[1],
            'degree': stats.degree_centrality.get(most_popular[0], 0),
            'betweenness': stats.betweenness_centrality.get(most_popular[0], 0),
            'closeness': stats.closeness_centrality.get(most_popular[0], 0),
        }


def detect_communities(stats, qq_to_name: Dict[str, str]) -> None:
    if not stats.edges:
        return

    import random

    adj_list, edge_weights = _build_graph_structures(stats)
    nodes = [n['id'] for n in stats.nodes]
    labels = {node: index for index, node in enumerate(nodes)}

    for _ in range(100):
        changed = False
        random.shuffle(nodes)

        for node in nodes:
            if not adj_list[node]:
                continue

            label_weights = defaultdict(float)
            for neighbor in adj_list[node]:
                label_weights[labels[neighbor]] += edge_weights.get((node, neighbor), 1)

            if not label_weights:
                continue

            max_weight = max(label_weights.values())
            best_labels = [label for label, weight in label_weights.items() if weight == max_weight]
            new_label = random.choice(best_labels)
            if labels[node] != new_label:
                labels[node] = new_label
                changed = True

        if not changed:
            break

    community_members = defaultdict(list)
    for node, label in labels.items():
        community_members[label].append(node)

    stats.communities = [
        sorted(members) for members in community_members.values()
        if len(members) > 1
    ]

    if stats.edges:
        most_active = max(stats.edges, key=lambda edge: edge['value'])
        stats.most_active_pair = {
            'pair': [most_active['from'], most_active['to']],
            'name1': qq_to_name.get(most_active['from'], most_active['from']),
            'name2': qq_to_name.get(most_active['to'], most_active['to']),
            'weight': most_active['value'],
        }


def compute_network_metrics(stats) -> None:
    if stats.total_nodes <= 1:
        return

    adj_list = defaultdict(set)
    for edge in stats.edges:
        adj_list[edge['from']].add(edge['to'])
        adj_list[edge['to']].add(edge['from'])

    nodes = [n['id'] for n in stats.nodes]
    node_count = len(nodes)

    max_possible_edges = node_count * (node_count - 1) / 2
    stats.network_density = stats.total_edges / max_possible_edges if max_possible_edges > 0 else 0

    clustering_coefficients = []
    for node in nodes:
        neighbors = list(adj_list[node])
        neighbor_count = len(neighbors)
        if neighbor_count < 2:
            clustering_coefficients.append(0.0)
            continue

        edges_between_neighbors = 0
        for i in range(len(neighbors)):
            for j in range(i + 1, len(neighbors)):
                if neighbors[j] in adj_list[neighbors[i]]:
                    edges_between_neighbors += 1

        max_edges = neighbor_count * (neighbor_count - 1) / 2
        cc = edges_between_neighbors / max_edges if max_edges > 0 else 0
        clustering_coefficients.append(cc)

    stats.average_clustering = (
        sum(clustering_coefficients) / len(clustering_coefficients)
        if clustering_coefficients else 0
    )

    total_path_length = 0
    path_count = 0
    for source in nodes:
        distances = {node: float('inf') for node in nodes}
        distances[source] = 0
        queue = deque([source])

        while queue:
            node = queue.popleft()
            for neighbor in adj_list[node]:
                if distances[neighbor] == float('inf'):
                    distances[neighbor] = distances[node] + 1
                    queue.append(neighbor)

        for target in nodes:
            if target != source and distances[target] < float('inf'):
                total_path_length += distances[target]
                path_count += 1

    stats.average_path_length = total_path_length / path_count if path_count > 0 else 0
