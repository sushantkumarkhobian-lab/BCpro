from typing import List, Dict, Set, Optional
import logging

from schemas.models import Transaction, TraceStep, TracePath, GraphResponse
from config import settings

logger = logging.getLogger(__name__)

class MultiHopTracer:
    """
    Multi-hop money path tracer with Peel-Chain detection and flow ranking.
    Distinguishes primary bulk money paths from small peeled-off change transfers.
    """

    def __init__(self, flow_threshold_percent: float = settings.FLOW_THRESHOLD_PERCENT):
        self.flow_threshold_percent = flow_threshold_percent

    def trace_funds(self, seed_address: str, graph_response: GraphResponse, max_hops: int = 4) -> List[TracePath]:
        """
        Traverses NetworkX graph output outwards from seed_address to trace paths up to max_hops depth.
        Applies Peel-Chain flow ranking threshold to categorize PRIMARY vs SECONDARY movements.
        """
        # Map outgoing transactions by sender address
        outgoing_edges: Dict[str, List[Dict]] = {}
        for edge in graph_response.edges:
            src = edge.source
            if src not in outgoing_edges:
                outgoing_edges[src] = []
            outgoing_edges[src].append({
                "target": edge.target,
                "amount": edge.amount,
                "tx_hashes": edge.tx_hashes
            })

        paths: List[TracePath] = []
        path_counter = 1

        # Recursive DFS / path finder
        def _explore_path(current_address: str, current_hop: int, current_steps: List[TraceStep], visited: Set[str]):
            if current_hop >= max_hops or current_address not in outgoing_edges or not outgoing_edges[current_address]:
                # Reached terminal node or max hop boundary
                if len(current_steps) > 1:
                    is_primary = all(s.flow_category == "PRIMARY" for s in current_steps[1:])
                    paths.append(TracePath(
                        path_id=f"PATH_{path_counter:03d}",
                        is_primary_path=is_primary,
                        hops_count=len(current_steps) - 1,
                        terminal_address=current_address,
                        total_amount_transferred=current_steps[-1].incoming_amount,
                        steps=list(current_steps)
                    ))
                return

            out_transfers = outgoing_edges[current_address]
            total_outflow = sum(t["amount"] for t in out_transfers)

            # Sort transfers descending by amount for peel-chain analysis
            sorted_transfers = sorted(out_transfers, key=lambda x: x["amount"], reverse=True)

            for transfer in sorted_transfers:
                next_addr = transfer["target"]
                amt = transfer["amount"]
                tx_hash = transfer["tx_hashes"][0] if transfer["tx_hashes"] else "N/A"

                if next_addr in visited:
                    continue  # Avoid loops

                flow_pct = (amt / total_outflow * 100.0) if total_outflow > 0 else 0.0
                category = "PRIMARY" if flow_pct >= self.flow_threshold_percent else "SECONDARY"

                step = TraceStep(
                    hop=current_hop + 1,
                    address=next_addr,
                    incoming_amount=amt,
                    outgoing_amount=0.0,  # updated on next hop
                    tx_hash=tx_hash,
                    flow_category=category,
                    flow_percentage=round(flow_pct, 2)
                )

                # Update current step's outgoing amount
                current_steps[-1].outgoing_amount = amt

                visited.add(next_addr)
                _explore_path(next_addr, current_hop + 1, current_steps + [step], visited)
                visited.remove(next_addr)

        # Seed initial step
        initial_step = TraceStep(
            hop=0,
            address=seed_address,
            incoming_amount=0.0,
            outgoing_amount=0.0,
            flow_category="PRIMARY",
            flow_percentage=100.0
        )

        _explore_path(seed_address, 0, [initial_step], {seed_address})

        # Ensure primary paths come first in list
        paths.sort(key=lambda p: (not p.is_primary_path, -p.total_amount_transferred))
        return paths
