"""
Live Tron Wallet Forensics Test Script
Tests the POST /trace endpoint against active real-world Tron mainnet USDT addresses.
"""

import sys
import json
import httpx

# Real live Tron USDT addresses
REAL_TRON_WALLETS = {
    "Binance_Hot_Wallet_1": "TPYmHEhy5n8TCEfYGqW2rPxsghSfNghpdn",
    "Tether_Treasury_Tron": "TKHuVq1oKVswCariNzhCCebdAoVkLW86M7",
    "Binance_TRC20_Hot_Wallet_2": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",  # Also USDT Token Contract
    "OKX_Hot_Wallet": "TFFBwoB8G31NqM1E3R7A3d6y4w6T3vJ1K",
}

API_URL = "http://127.0.0.1:8000/trace"

def test_live_trace(wallet_name: str, address: str, max_hops: int = 2):
    print(f"\n========================================================")
    print(f" 🔍 Tracing Real Tron Wallet: {wallet_name}")
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
            print(f" ✅ Success! Ingested {data.get('total_transactions_ingested')} live transactions.")
            
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
    print("Testing live Tron API integration with active real-world addresses...")
    # Test Binance Hot Wallet
    test_live_trace("Binance_Hot_Wallet_1", REAL_TRON_WALLETS["Binance_Hot_Wallet_1"], max_hops=2)
