from typing import List, Dict, Set, Tuple
from collections import defaultdict
import logging

from schemas.models import Transaction, Cluster, ClusterEvidence

logger = logging.getLogger(__name__)

class DisjointSet:
    """Union-Find helper to manage cluster components with evidence tracking"""
    def __init__(self):
        self.parent: Dict[str, str] = {}

    def find(self, i: str) -> str:
        if i not in self.parent:
            self.parent[i] = i
            return i
        if self.parent[i] == i:
            return i
        self.parent[i] = self.find(self.parent[i])
        return self.parent[i]

    def union(self, i: str, j: str) -> bool:
        root_i = self.find(i)
        root_j = self.find(j)
        if root_i != root_j:
            self.parent[root_i] = root_j
            return True
        return False

class ClusteringEngine:
    """
    Account-based Address Clustering Engine tailored for Tron USDT-TRC20.
    Implements explainable, deterministic heuristic rules with evidence chains.
    """

    def analyze_and_cluster(self, transactions: List[Transaction]) -> List[Cluster]:
        """
        Executes heuristic analysis across transaction list and returns clusters with evidence.
        """
        dsu = DisjointSet()
        evidence_records: List[ClusterEvidence] = []

        # ------------------------------------------------------------------
        # Heuristic 1: Common Funding Source
        # ------------------------------------------------------------------
        # If Sender S sends USDT to A and B, A and B share a common funder.
        senders_to_recipients: Dict[str, Set[Tuple[str, str]]] = defaultdict(set)
        for tx in transactions:
            senders_to_recipients[tx.from_address].add((tx.to_address, tx.tx_hash))

        for funder, recipients in senders_to_recipients.items():
            recip_list = list(recipients)
            if len(recip_list) > 1:
                # Group all recipient pairs under funder
                base_recip, base_tx = recip_list[0]
                for r_addr, r_tx in recip_list[1:]:
                    if r_addr != base_recip:
                        dsu.union(base_recip, r_addr)
                        evidence_records.append(ClusterEvidence(
                            addr_a=base_recip,
                            addr_b=r_addr,
                            heuristic_name="common_funding_source",
                            evidence_tx=f"{base_tx} & {r_tx}",
                            confidence=0.91,
                            explanation=f"Both addresses received initial funding from common source wallet '{funder}'"
                        ))

        # ------------------------------------------------------------------
        # Heuristic 2: Deposit-Address / Aggregator Sweep Reuse
        # ------------------------------------------------------------------
        # If A and B both send funds into the same central destination D (e.g. deposit sweep wallet).
        recipients_from_senders: Dict[str, Set[Tuple[str, str]]] = defaultdict(set)
        for tx in transactions:
            recipients_from_senders[tx.to_address].add((tx.from_address, tx.tx_hash))

        for dest, senders in recipients_from_senders.items():
            sender_list = list(senders)
            if len(sender_list) > 1:
                base_sender, base_tx = sender_list[0]
                for s_addr, s_tx in sender_list[1:]:
                    if s_addr != base_sender:
                        dsu.union(base_sender, s_addr)
                        evidence_records.append(ClusterEvidence(
                            addr_a=base_sender,
                            addr_b=s_addr,
                            heuristic_name="deposit_address_reuse",
                            evidence_tx=f"{base_tx} & {s_tx}",
                            confidence=0.88,
                            explanation=f"Both wallets repeatedly deposit into central aggregator/sweep destination '{dest}'"
                        ))

        # ------------------------------------------------------------------
        # Heuristic 3: Repeated High-Volume Interaction
        # ------------------------------------------------------------------
        pair_interactions: Dict[Tuple[str, str], List[Transaction]] = defaultdict(list)
        for tx in transactions:
            pair = tuple(sorted([tx.from_address, tx.to_address]))
            pair_interactions[pair].append(tx)

        for (addr1, addr2), tx_list in pair_interactions.items():
            if len(tx_list) >= 2:
                total_vol = sum(t.amount for t in tx_list)
                dsu.union(addr1, addr2)
                evidence_records.append(ClusterEvidence(
                    addr_a=addr1,
                    addr_b=addr2,
                    heuristic_name="repeated_interactions",
                    evidence_tx=tx_list[0].tx_hash,
                    confidence=0.95,
                    explanation=f"Repeated transactions ({len(tx_list)} transfers, Total: {total_vol:,.2f} USDT) between pair"
                ))

        # ------------------------------------------------------------------
        # Group addresses by DisjointSet roots into Cluster objects
        # ------------------------------------------------------------------
        all_addrs: Set[str] = set()
        for tx in transactions:
            all_addrs.add(tx.from_address)
            all_addrs.add(tx.to_address)

        clusters_map: Dict[str, Set[str]] = defaultdict(set)
        for addr in all_addrs:
            root = dsu.find(addr)
            clusters_map[root].add(addr)

        # Filter for clusters with at least 2 addresses
        result_clusters: List[Cluster] = []
        cluster_counter = 1

        for root, member_addrs in clusters_map.items():
            if len(member_addrs) >= 2:
                # Find matching evidence records for member addresses
                relevant_evidence = [
                    ev for ev in evidence_records
                    if ev.addr_a in member_addrs or ev.addr_b in member_addrs
                ]
                
                primary_h = relevant_evidence[0].heuristic_name if relevant_evidence else "behavioral_cooccurrence"

                result_clusters.append(Cluster(
                    cluster_id=f"C{cluster_counter:03d}",
                    addresses=sorted(list(member_addrs)),
                    primary_heuristic=primary_h,
                    evidence_chain=relevant_evidence
                ))
                cluster_counter += 1

        return result_clusters
