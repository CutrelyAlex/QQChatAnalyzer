from __future__ import annotations

from typing import Dict


class NetworkStats:
    """社交网络统计数据容器。"""

    def __init__(self):
        self.total_nodes = 0
        self.total_edges = 0
        self.nodes = []
        self.edges = []

        self.original_nodes_count = 0
        self.original_edges_count = 0

        self.degree_centrality = {}
        self.betweenness_centrality = {}
        self.closeness_centrality = {}

        self.most_popular_user = None
        self.most_active_pair = None
        self.interaction_matrix = {}

        self.average_clustering = 0.0
        self.network_density = 0.0
        self.average_path_length = 0.0
        self.key_connectors = []

        self.communities = []

    def to_dict(self) -> Dict:
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
            'density': round(self.network_density, 3),
            'average_path_length': round(self.average_path_length, 3),
            'avg_clustering_coefficient': round(self.average_clustering, 3),
            'communities': self.communities,
            'key_connectors': self.key_connectors,
        }
