"""
Live/Mock Ethereum Wallet Forensics Test Script
Tests the POST /trace endpoint against Ethereum USDT addresses.
"""

import sys
import json
import httpx

# Real live & mock Ethereum USDT addresses
ETH_TEST_WALLETS = {
    "Ethereum_Mock_Victim": "0x_VICTIM_SIH_DEMO_999",
    "Binance_Hot_Wallet_ERC20": "0x28C6c06298d514Db089934071355E5743bf21d60",
    "Tether_Treasury_Ethereum": "0x5754284f345afc66a98fbf0a0afe7969c3628628",
    "Kraken_Hot_Wallet": "0x0D0707963952f2a77299197a1f849334276C728E"
}

API_URL = "http://127.0.0.1:8000/trace"

def test_eth_trace(wallet_name: str, address: str, max_hops: int = 2):
    print(f"\n========================================================")
    print(f" 🔍 Tracing Ethereum Wallet: {wallet_name}")
    print(f" Address  : {address}")
    print(f" Max Hops : {max_hops}")
    print(f"========================================================")

    payload = {
        "address": address,
        "max_hops": max_hops,
        "flow_threshold_percent": 10.0
    }

    try:
        response = httpx.post(API_URL, json=payload, timeout=30.0)
        if response.status_code == 200:
            data = response.json()
            print(f" ✅ Success! Ingested {data.get('total_transactions_ingested')} Ethereum transactions.")
            
            graph = data.get("graph", {})
            print(f" 🕸️ Graph Nodes: {graph.get('total_nodes')} | Edges: {graph.get('total_edges')}")
            
            clusters = data.get("clusters", [])
            print(f" 🏷️ Clusters Discovered: {len(clusters)}")
            for c in clusters:
                print(f"    - Cluster {c['cluster_id']}: {len(c['addresses'])} addresses linked via '{c['primary_heuristic']}'")
            
            attr = data.get("attribution", {})
            print(f" 🏛️ Exchange Attribution:")
            print(f"    - Status: {attr.get('status')}")
            print(f"    - Exchange: {attr.get('exchange_name') or 'N/A'}")
            print(f"    - Confidence: {attr.get('confidence')}")
            print(f"    - Source: {attr.get('source') or 'N/A'}")
            
            primary_path = data.get("primary_path")
            if primary_path:
                print(f" 🚩 Primary Fund Path ({primary_path.get('hops_count')} Hops):")
                for step in primary_path.get("steps", []):
                    print(f"    Hop {step['hop']}: {step['address']} (Inflow: {step['incoming_amount']:,.2f} USDT | Flow: {step['flow_category']})")
            return True
        else:
            print(f" ❌ Server returned status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f" ⚠️ Could not connect to API server: {e}")
        print("    Ensure server is running via 'python main.py'")
        return False

if __name__ == "__main__":
    print("Testing Ethereum API integration...")
    # Test Mock/Live Ethereum Wallet
    target = sys.argv[1] if len(sys.argv) > 1 else "Ethereum_Mock_Victim"
    addr = ETH_TEST_WALLETS.get(target, target)
    test_eth_trace(target, addr, max_hops=4)
