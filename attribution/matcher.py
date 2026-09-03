import json
import logging
import httpx
from pathlib import Path
from typing import Dict, List, Optional
from schemas.models import AttributionResult, Cluster

logger = logging.getLogger(__name__)

class ExchangeAttributionMatcher:
    """Matches wallet addresses against local labeled exchange dataset and dynamic Tronscan live explorer tags"""

    def __init__(self, data_path: Optional[Path] = None):
        if data_path is None:
            data_path = Path(__file__).resolve().parent.parent / "data" / "exchanges.json"
        self.data_path = data_path
        self.exchange_db: Dict[str, Dict] = {}
        self._load_database()

    def _load_database(self):
        """Loads labeled exchange address dataset into memory map"""
        if not self.data_path.exists():
            logger.warning(f"Exchange database file not found at {self.data_path}")
            return

        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            entities = data.get("entities", [])
            for item in entities:
                addr = item.get("address", "").strip().lower()
                if addr:
                    self.exchange_db[addr] = item
            logger.info(f"Loaded {len(self.exchange_db)} tagged exchange addresses.")
        except Exception as e:
            logger.error(f"Error loading exchange database: {e}")

    def _check_tronscan_live(self, address: str) -> Optional[AttributionResult]:
        """Queries Tronscan live explorer API (account endpoint) for real-time account tags & entity labels"""
        clean_addr = address.strip()
        url = f"https://apilist.tronscan.org/api/account?address={clean_addr}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*"
        }
        
        try:
            with httpx.Client(timeout=6.0, follow_redirects=True) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict):
                        name = str(data.get("name") or "").strip()
                        public_tag = str(data.get("publicTag") or data.get("public_tag") or "").strip()
                        address_tag = str(data.get("addressTag") or data.get("address_tag") or "").strip()
                        red_tag = str(data.get("redTag") or "").strip()

                        tag_candidate = public_tag or name or address_tag or red_tag

                        if tag_candidate and tag_candidate.lower() not in ["null", "none", ""]:
                            # Extract clean entity name
                            ex_name = tag_candidate
                            known_keywords = [
                                "Binance", "OKX", "Bybit", "KuCoin", "HTX", "Huobi", 
                                "Bitfinex", "Coinbase", "Kraken", "Gate.io", "MEXC", 
                                "Poloniex", "JustLend", "SunSwap", "Tether", "Staking"
                            ]
                            for kw in known_keywords:
                                if kw.lower() in tag_candidate.lower():
                                    ex_name = kw
                                    break

                            return AttributionResult(
                                address=address,
                                status="KNOWN",
                                exchange_name=ex_name,
                                entity_type="Exchange",
                                deposit_address=address,
                                confidence=0.95,
                                source=f"Tronscan Dynamic Live Tag ('{tag_candidate}')",
                                recommendation=f"Entity dynamically identified via Tronscan Explorer Tag as {ex_name} ('{tag_candidate}'). Issue legal freeze request to exchange compliance."
                            )
        except Exception as e:
            logger.debug(f"Tronscan live tag lookup for {address} failed: {e}")
            
        return None

    def attribute_address(self, address: str) -> AttributionResult:
        """
        Checks a single wallet address against:
        1. Local exchanges.json database
        2. Live Tronscan online tag lookup API
        Returns KNOWN match with confidence & provenance, or explicit UNATTRIBUTED.
        """
        addr_clean = address.strip().lower()

        # Step 1: Check local database first
        if addr_clean in self.exchange_db:
            entry = self.exchange_db[addr_clean]
            return AttributionResult(
                address=address,
                status="KNOWN",
                exchange_name=entry.get("entity_name"),
                entity_type=entry.get("entity_type", "Exchange"),
                deposit_address=entry.get("address"),
                confidence=entry.get("confidence", 0.95),
                source=entry.get("source", "Public Tagged Directory"),
                recommendation=f"Entity identified as {entry.get('entity_name')} ({entry.get('wallet_type')}). Issue legal freeze request to exchange compliance."
            )

        # Step 2: Dynamic Live Tronscan Online Tag Lookup
        live_res = self._check_tronscan_live(address)
        if live_res is not None:
            return live_res

        # Step 3: Default explicitly to UNATTRIBUTED if no tag exists
        return AttributionResult(
            address=address,
            status="UNATTRIBUTED",
            exchange_name=None,
            entity_type=None,
            deposit_address=None,
            confidence=0.0,
            source=None,
            recommendation="Address not found in known exchange database or Tronscan tags. Flagged for manual investigation / OSINT enrichment."
        )

    def attribute_cluster_or_addresses(self, addresses: List[str]) -> AttributionResult:
        """
        Attributes a cluster or list of addresses by searching for any known exchange wallet match.
        """
        for addr in addresses:
            res = self.attribute_address(addr)
            if res.status == "KNOWN":
                return res
        
        # If none matched
        return AttributionResult(
            address=addresses[0] if addresses else "N/A",
            status="UNATTRIBUTED",
            exchange_name=None,
            entity_type=None,
            deposit_address=None,
            confidence=0.0,
            source=None,
            recommendation="No cluster members matched known exchange addresses. Flagged for manual investigation."
        )
