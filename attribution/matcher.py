import json
import logging
import re
import httpx
from pathlib import Path
from typing import Dict, List, Optional
from schemas.models import AttributionResult, Cluster

logger = logging.getLogger(__name__)

class ExchangeAttributionMatcher:
    """Matches wallet addresses against local labeled exchange dataset and dynamic Tronscan/Etherscan live explorer tags"""

    def __init__(self, data_path: Optional[Path] = None, eth_data_path: Optional[Path] = None):
        if data_path is None:
            data_path = Path(__file__).resolve().parent.parent / "data" / "exchanges.json"
        if eth_data_path is None:
            eth_data_path = Path(__file__).resolve().parent.parent / "data" / "exchanges_eth.json"
        
        self.data_path = data_path
        self.eth_data_path = eth_data_path
        self.exchange_db: Dict[str, Dict] = {}
        self._load_database()

    def _load_database(self):
        """Loads labeled exchange address dataset into memory map for both Tron and Ethereum"""
        paths = [self.data_path, self.eth_data_path]
        loaded_count = 0

        for path in paths:
            if not path or not path.exists():
                logger.warning(f"Exchange database file not found at {path}")
                continue

            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                entities = data.get("entities", [])
                for item in entities:
                    addr = item.get("address", "").strip().lower()
                    if addr:
                        self.exchange_db[addr] = item
                        loaded_count += 1
            except Exception as e:
                logger.error(f"Error loading exchange database from {path}: {e}")

        logger.info(f"Loaded {loaded_count} tagged exchange addresses across chains.")

    def _check_etherscan_live(self, address: str) -> Optional[AttributionResult]:
        """Queries Etherscan live explorer for real-time account tags, contract labels & entity names"""
        clean_addr = address.strip()
        url = f"https://etherscan.io/address/{clean_addr}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        
        try:
            with httpx.Client(timeout=6.0, follow_redirects=True) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    text = resp.text
                    match = re.search(r'og:title"\s+content="([^|"]+)\|', text)
                    if not match:
                        match = re.search(r'<title>([^|"]+)\|', text)
                    
                    if match:
                        candidate = match.group(1).strip()
                        if candidate and not candidate.lower().startswith("address:") and not candidate.lower().startswith("ethereum"):
                            entity_type = "Contract / Protocol" if any(w in candidate.lower() for w in ["contract", "router", "deposit", "vault", "staking", "bridge"]) else "Exchange"
                            return AttributionResult(
                                address=address,
                                status="KNOWN",
                                exchange_name=candidate,
                                entity_type=entity_type,
                                deposit_address=address,
                                confidence=0.95,
                                source=f"Etherscan Dynamic Live Tag ('{candidate}')",
                                recommendation=f"Entity dynamically identified via Etherscan Explorer Tag as {candidate}. Verified on Ethereum Mainnet."
                            )
        except Exception as e:
            logger.debug(f"Etherscan live tag lookup for {address} failed: {e}")
            
        return None

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
        1. Local exchanges.json & exchanges_eth.json databases
        2. Live Tronscan / Etherscan online tag lookup APIs
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

        # Step 2: Dynamic Live Explorer Tag Lookup (Etherscan for 0x, Tronscan for T)
        if addr_clean.startswith("0x"):
            live_res = self._check_etherscan_live(address)
        else:
            live_res = self._check_tronscan_live(address)

        if live_res is not None:
            return live_res

        # Step 3: Default explicitly to UNATTRIBUTED if no tag exists
        explorer_name = "Etherscan" if addr_clean.startswith("0x") else "Tronscan"
        return AttributionResult(
            address=address,
            status="UNATTRIBUTED",
            exchange_name=None,
            entity_type=None,
            deposit_address=None,
            confidence=0.0,
            source=None,
            recommendation=f"Address not found in known exchange database or {explorer_name} tags. Flagged for manual investigation / OSINT enrichment."
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
