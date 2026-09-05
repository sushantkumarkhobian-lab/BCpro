import networkx as nx
from typing import Dict, List, Set, Tuple, Optional
import logging

from schemas.models import Transaction, GraphNode, GraphEdge, GraphResponse
from ingestion.tron_client import TronClient
from ingestion.client_factory import get_blockchain_client
from config import settings

logger = logging.getLogger(__name__)

class TransactionGraphBuilder:
    """Builds and manages a directed NetworkX graph of wallet transactions via BFS expansion"""

    def __init__(self, client=None, tron_client: Optional[TronClient] = None):
        self.client = client or tron_client
        self.tron_client = self.client  # Backward compatibility alias
        self.graph = nx.DiGraph()
        self.node_hops: Dict[str, int] = {}
        self.all_transactions: List[Transaction] = []

    async def build_graph_for_seed(self, seed_address: str, max_hops: int = 4) -> GraphResponse:
        """
        Incrementally builds graph starting from seed address up to max_hops via BFS expansion.
        Does NOT download full blockchain—only neighborhood transactions around relevant nodes.
        """
        self.graph.clear()
        self.node_hops.clear()
        self.all_transactions.clear()

        seed_clean = seed_address.strip()
        active_client = self.client or get_blockchain_client(seed_clean)

        self.node_hops[seed_clean] = 0
        self.graph.add_node(seed_clean, hop=0, is_seed=True)

        current_frontier: Set[str] = {seed_clean}
        visited_nodes: Set[str] = set()

        for current_hop in range(max_hops):
            if not current_frontier:
                break

            next_frontier: Set[str] = set()

            for wallet in current_frontier:
                if wallet in visited_nodes:
                    continue
                visited_nodes.add(wallet)

                # Fetch transactions for current wallet node using appropriate chain client
                txs = await active_client.get_wallet_transactions(wallet, limit=settings.MAX_TRANSACTIONS_PER_WALLET)
                
                for tx in txs:
                    self.all_transactions.append(tx)
                    u, v, amount = tx.from_address, tx.to_address, tx.amount
                    
                    # Update or set hop levels for newly discovered nodes
                    if u not in self.node_hops:
                        self.node_hops[u] = current_hop + 1 if u != seed_clean else 0
                    if v not in self.node_hops:
                        self.node_hops[v] = current_hop + 1 if v != seed_clean else 0

                    # Add directed edge or update aggregated weight
                    if self.graph.has_edge(u, v):
                        edge_data = self.graph[u][v]
                        edge_data["amount"] += amount
                        edge_data["tx_count"] += 1
                        if tx.tx_hash not in edge_data["tx_hashes"]:
                            edge_data["tx_hashes"].append(tx.tx_hash)
                    else:
                        self.graph.add_edge(
                            u, v,
                            amount=amount,
                            tx_count=1,
                            tx_hashes=[tx.tx_hash],
                            token=tx.token
                        )

                    # Expand outwards if recipient/sender hasn't reached max depth
                    if u != wallet and self.node_hops[u] < max_hops and u not in visited_nodes:
                        next_frontier.add(u)
                    if v != wallet and self.node_hops[v] < max_hops and v not in visited_nodes:
                        next_frontier.add(v)

            current_frontier = next_frontier

        return self.to_graph_response(seed_clean)

    def to_graph_response(self, seed_address: str) -> GraphResponse:
        """Converts internal NetworkX graph structure into standardized GraphResponse schema"""
        nodes_list: List[GraphNode] = []
        edges_list: List[GraphEdge] = []

        # Calculate inflows and outflows per node
        inflows: Dict[str, float] = {}
        outflows: Dict[str, float] = {}

        for u, v, data in self.graph.edges(data=True):
            amt = data.get("amount", 0.0)
            outflows[u] = outflows.get(u, 0.0) + amt
            inflows[v] = inflows.get(v, 0.0) + amt

            edges_list.append(GraphEdge(
                source=u,
                target=v,
                amount=round(amt, 2),
                tx_count=data.get("tx_count", 1),
                tx_hashes=data.get("tx_hashes", []),
                token=data.get("token", "USDT")
            ))

        all_nodes = set(self.graph.nodes())
        for node in all_nodes:
            hop = self.node_hops.get(node, 99)
            is_seed = (node == seed_address)
            is_terminal = (self.graph.out_degree(node) == 0 and not is_seed)

            nodes_list.append(GraphNode(
                id=node,
                label=node[:6] + "..." + node[-4:] if len(node) > 12 else node,
                hop_level=hop,
                total_inflow=round(inflows.get(node, 0.0), 2),
                total_outflow=round(outflows.get(node, 0.0), 2),
                is_seed=is_seed,
                is_terminal=is_terminal
            ))

        return GraphResponse(
            seed_address=seed_address,
            nodes=nodes_list,
            edges=edges_list,
            total_nodes=len(nodes_list),
            total_edges=len(edges_list)
        )
