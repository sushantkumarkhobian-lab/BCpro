import asyncio
from fastapi.testclient import TestClient

from main import app
from schemas.models import Transaction
from ingestion.tron_client import TronClient
from graph.builder import TransactionGraphBuilder
from clustering.engine import ClusteringEngine
from tracing.tracer import MultiHopTracer
from attribution.matcher import ExchangeAttributionMatcher

client = TestClient(app)

def test_health_check_endpoint():
    """Verify /health endpoint returns HTTP 200 and valid JSON"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "wallettrace-blockchain"
    assert "use_mock_data" in data

def test_ingestion_mock_data():
    """Verify TronClient loads and filters mock dataset correctly"""
    tron_client = TronClient()
    txs = tron_client._get_mock_transactions_for_wallet("T_VICTIM_SIH_DEMO_999")
    assert len(txs) >= 2
    assert any(tx.from_address == "T_VICTIM_SIH_DEMO_999" for tx in txs)

def test_graph_builder_bfs():
    """Verify NetworkX graph builder expands seed wallet outwards up to max_hops"""
    async def _async_run():
        tron_client = TronClient()
        builder = TransactionGraphBuilder(tron_client)
        res = await builder.build_graph_for_seed("T_VICTIM_SIH_DEMO_999", max_hops=4)
        
        assert res.seed_address == "T_VICTIM_SIH_DEMO_999"
        assert res.total_nodes > 1
        assert res.total_edges > 1
        
        # Check seed node properties
        seed_node = next(n for n in res.nodes if n.id == "T_VICTIM_SIH_DEMO_999")
        assert seed_node.is_seed is True
        assert seed_node.hop_level == 0

    asyncio.run(_async_run())


def test_clustering_engine_explainability():
    """Verify account-based heuristics generate explainable evidence records"""
    tron_client = TronClient()
    all_mock = tron_client._load_mock_transactions()
    
    engine = ClusteringEngine()
    clusters = engine.analyze_and_cluster(all_mock)
    
    assert len(clusters) >= 1
    c0 = clusters[0]
    assert c0.cluster_id.startswith("C")
    assert len(c0.addresses) >= 2
    assert len(c0.evidence_chain) >= 1
    
    # Check evidence structure
    ev = c0.evidence_chain[0]
    assert ev.heuristic_name in ["common_funding_source", "deposit_address_reuse", "repeated_interactions"]
    assert ev.confidence >= 0.8
    assert len(ev.explanation) > 10

def test_fund_tracing_peel_chain():
    """Verify multi-hop fund tracer correctly categorizes PRIMARY vs SECONDARY flows"""
    async def _async_run():
        tron_client = TronClient()
        builder = TransactionGraphBuilder(tron_client)
        graph_res = await builder.build_graph_for_seed("T_VICTIM_SIH_DEMO_999", max_hops=4)
        
        tracer = MultiHopTracer(flow_threshold_percent=10.0)
        paths = tracer.trace_funds("T_VICTIM_SIH_DEMO_999", graph_res, max_hops=4)
        
        assert len(paths) >= 1
        primary = next((p for p in paths if p.is_primary_path), None)
        assert primary is not None
        assert primary.terminal_address == "TBinanceUSDTDeposit666666666666"

    asyncio.run(_async_run())


def test_exchange_attribution_matching():
    """Verify exchange attribution engine identifies known Binance deposit address"""
    matcher = ExchangeAttributionMatcher()
    
    # Known Binance address test
    res = matcher.attribute_address("TBinanceUSDTDeposit666666666666")
    assert res.status == "KNOWN"
    assert res.exchange_name == "Binance"
    assert res.confidence >= 0.9
    assert "Legal" in res.source or "Tronscan" in res.source
    
    # Unknown address test
    res_unknown = matcher.attribute_address("T_UNKNOWN_WALLET_99999")
    assert res_unknown.status == "UNATTRIBUTED"
    assert res_unknown.exchange_name is None
    assert res_unknown.confidence == 0.0

def test_trace_master_endpoint():
    """Verify full POST /trace API endpoint pipeline execution"""
    payload = {
        "address": "T_VICTIM_SIH_DEMO_999",
        "max_hops": 4,
        "flow_threshold_percent": 10.0
    }
    response = client.post("/trace", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert data["seed_address"] == "T_VICTIM_SIH_DEMO_999"
    assert data["max_hops_traversed"] == 4
    assert data["attribution"]["status"] == "KNOWN"
    assert data["attribution"]["exchange_name"] == "Binance"
    assert len(data["clusters"]) >= 1
    assert data["graph"]["total_nodes"] > 1
