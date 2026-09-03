from fastapi import APIRouter, HTTPException, Query, Path as APIPath
from typing import List, Optional, Dict, Any

from config import settings
from schemas.models import (
    TraceRequest, TraceResponse, GraphResponse, Cluster,
    AttributionResult, Transaction
)
from ingestion.tron_client import TronClient
from graph.builder import TransactionGraphBuilder
from clustering.engine import ClusteringEngine
from tracing.tracer import MultiHopTracer
from attribution.matcher import ExchangeAttributionMatcher

router = APIRouter()

# Instantiate singletons
tron_client = TronClient()
graph_builder = TransactionGraphBuilder(tron_client)
clustering_engine = ClusteringEngine()
attribution_matcher = ExchangeAttributionMatcher()

@router.get("/health", summary="Health Check", tags=["System"])
async def health_check():
    """Returns server operational status and active ingestion mode (Mock vs Live API)"""
    return {
        "status": "healthy",
        "service": "wallettrace-blockchain",
        "version": "1.0.0",
        "use_mock_data": settings.USE_MOCK_DATA,
        "primary_chain": "tron (USDT-TRC20)",
        "default_max_hops": settings.MAX_HOPS
    }

@router.post("/trace", response_model=TraceResponse, summary="Investigate Wallet (Full Pipeline)", tags=["Forensics"])
async def trace_wallet(req: TraceRequest):
    """
    Executes complete end-to-end forensic investigation for a seed suspicious/victim wallet address:
    1. Blockchain Data Ingestion (Tron API / Mock)
    2. NetworkX Transaction Graph Construction & BFS Expansion
    3. Account-based Explainable Address Clustering
    4. Peel-Chain Multi-Hop Fund Tracing
    5. Terminal Exchange Attribution
    """
    seed_address = req.address.strip()
    if not seed_address:
        raise HTTPException(status_code=400, detail="Seed address cannot be empty")

    max_hops = req.max_hops if req.max_hops and 1 <= req.max_hops <= 10 else settings.MAX_HOPS
    flow_threshold = req.flow_threshold_percent if req.flow_threshold_percent is not None else settings.FLOW_THRESHOLD_PERCENT

    # Step 1 & 2: Build Graph & Fetch Transactions
    graph_res = await graph_builder.build_graph_for_seed(seed_address, max_hops=max_hops)
    ingested_txs = graph_builder.all_transactions

    # Step 3: Run Clustering Engine
    clusters = clustering_engine.analyze_and_cluster(ingested_txs)

    # Step 4: Multi-Hop Fund Tracing & Peel-Chain Detection
    tracer = MultiHopTracer(flow_threshold_percent=flow_threshold)
    paths = tracer.trace_funds(seed_address, graph_res, max_hops=max_hops)

    primary_path = next((p for p in paths if p.is_primary_path), paths[0] if paths else None)

    # Step 5: Exchange Attribution for Terminal Wallet
    terminal_addr = primary_path.terminal_address if primary_path else seed_address
    
    # Also check if any cluster member has attribution
    all_trace_addrs = [node.id for node in graph_res.nodes if node.is_terminal]
    attribution = attribution_matcher.attribute_address(terminal_addr)
    if attribution.status != "KNOWN" and all_trace_addrs:
        attribution = attribution_matcher.attribute_cluster_or_addresses(all_trace_addrs)

    # Construct unified forensic response payload
    return TraceResponse(
        seed_address=seed_address,
        max_hops_traversed=max_hops,
        flow_threshold_percent=flow_threshold,
        total_transactions_ingested=len(ingested_txs),
        primary_path=primary_path,
        all_paths=paths,
        clusters=clusters,
        graph=graph_res,
        attribution=attribution,
        summary={
            "total_nodes": graph_res.total_nodes,
            "total_edges": graph_res.total_edges,
            "clusters_found": len(clusters),
            "paths_traced": len(paths),
            "attributed_exchange": attribution.exchange_name if attribution.status == "KNOWN" else "UNATTRIBUTED"
        }
    )

@router.get("/cluster/{address}", response_model=List[Cluster], summary="Get Wallet Cluster & Evidence", tags=["Clustering"])
async def get_cluster_for_address(address: str = APIPath(..., description="Wallet address to check")):
    """Returns cluster membership and explainable heuristic evidence for a wallet address"""
    txs = await tron_client.get_wallet_transactions(address)
    if not txs:
        return []
    
    clusters = clustering_engine.analyze_and_cluster(txs)
    addr_clean = address.strip().lower()
    
    matching_clusters = [
        c for c in clusters
        if any(m.lower() == addr_clean for m in c.addresses)
    ]
    return matching_clusters

@router.get("/graph/{address}", response_model=GraphResponse, summary="Get Transaction Graph Topology", tags=["Graph"])
async def get_graph_for_address(
    address: str = APIPath(..., description="Wallet address"),
    max_hops: int = Query(2, ge=1, le=5, description="Hop expansion depth")
):
    """Returns NetworkX transaction graph node/edge topology around a wallet"""
    return await graph_builder.build_graph_for_seed(address, max_hops=max_hops)

@router.get("/attribution/{address}", response_model=AttributionResult, summary="Check Exchange Attribution", tags=["Attribution"])
async def get_attribution_for_address(address: str = APIPath(..., description="Wallet address to evaluate")):
    """Checks whether a wallet address matches a known exchange deposit wallet in dataset"""
    return attribution_matcher.attribute_address(address)

@router.get("/address/{address}", summary="Get Address Details & Transactions", tags=["Ingestion"])
async def get_address_details(address: str = APIPath(..., description="Wallet address")):
    """Returns summary and raw normalized USDT transactions involving the specified wallet"""
    txs = await tron_client.get_wallet_transactions(address)
    inflow = sum(t.amount for t in txs if t.to_address.lower() == address.strip().lower())
    outflow = sum(t.amount for t in txs if t.from_address.lower() == address.strip().lower())
    
    return {
        "address": address,
        "transaction_count": len(txs),
        "total_usdt_inflow": round(inflow, 2),
        "total_usdt_outflow": round(outflow, 2),
        "transactions": txs
    }
