import asyncio
from fastapi.testclient import TestClient

from main import app
from schemas.models import Transaction
from ingestion.ethereum_client import EthereumClient
from ingestion.client_factory import get_blockchain_client
from graph.builder import TransactionGraphBuilder
from clustering.engine import ClusteringEngine
from tracing.tracer import MultiHopTracer
from attribution.matcher import ExchangeAttributionMatcher

client = TestClient(app)

def test_ethereum_client_mock_data():
    """Verify EthereumClient loads and filters mock dataset correctly"""
    eth_client = EthereumClient()
    txs = eth_client._get_mock_transactions_for_wallet("0x_VICTIM_SIH_DEMO_999")
    assert len(txs) >= 2
    assert any(tx.from_address == "0x_VICTIM_SIH_DEMO_999" for tx in txs)
    assert all(tx.chain == "ethereum" for tx in txs)

def test_client_factory_auto_detection():
    """Verify client factory routes 0x to EthereumClient and T to TronClient"""
    eth_c = get_blockchain_client("0x_VICTIM_SIH_DEMO_999")
    tron_c = get_blockchain_client("T_VICTIM_SIH_DEMO_999")
    
    assert eth_c.__class__.__name__ == "EthereumClient"
    assert tron_c.__class__.__name__ == "TronClient"

def test_ethereum_graph_builder_bfs():
    """Verify NetworkX graph builder expands seed wallet for Ethereum up to max_hops"""
    async def _async_run():
        builder = TransactionGraphBuilder()
        res = await builder.build_graph_for_seed("0x_VICTIM_SIH_DEMO_999", max_hops=4)
        
        assert res.seed_address == "0x_VICTIM_SIH_DEMO_999"
        assert res.total_nodes > 1
        assert res.total_edges > 1
        
        seed_node = next(n for n in res.nodes if n.id == "0x_VICTIM_SIH_DEMO_999")
        assert seed_node.is_seed is True
        assert seed_node.hop_level == 0

    asyncio.run(_async_run())

def test_ethereum_exchange_attribution_matching():
    """Verify exchange attribution matcher identifies Ethereum Binance hot wallet"""
    matcher = ExchangeAttributionMatcher()
    
    res = matcher.attribute_address("0x28C6c06298d514Db089934071355E5743bf21d60")
    assert res.status == "KNOWN"
    assert res.exchange_name == "Binance"
    assert res.confidence >= 0.9

def test_ethereum_trace_master_endpoint():
    """Verify full POST /trace API endpoint pipeline execution for Ethereum wallet"""
    payload = {
        "address": "0x_VICTIM_SIH_DEMO_999",
        "max_hops": 4,
        "flow_threshold_percent": 10.0
    }
    response = client.post("/trace", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert data["seed_address"] == "0x_VICTIM_SIH_DEMO_999"
    assert data["max_hops_traversed"] == 4
    assert data["attribution"]["status"] == "KNOWN"
    assert data["attribution"]["exchange_name"] == "Binance"
    assert len(data["clusters"]) >= 1
    assert data["graph"]["total_nodes"] > 1
