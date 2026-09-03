import json
import time
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Set, Optional
import httpx

from config import settings
from schemas.models import Transaction
from ingestion.normalizer import TransactionNormalizer

logger = logging.getLogger(__name__)

class TronClient:
    """Client for fetching and normalizing Tron USDT-TRC20 transactions"""

    def __init__(self):
        self.use_mock = settings.USE_MOCK_DATA
        self.api_key = settings.TRONGRID_API_KEY
        self.trongrid_url = settings.TRON_GRID_BASE_URL
        self.tronscan_url = settings.TRONSCAN_BASE_URL
        self.usdt_contract = settings.USDT_TRC20_CONTRACT
        self.max_tx_per_wallet = settings.MAX_TRANSACTIONS_PER_WALLET
        self.mock_data_path = Path(__file__).resolve().parent.parent / "data" / "mock_transactions.json"
        
        self._mock_cache: Optional[List[Transaction]] = None

    def _load_mock_transactions(self) -> List[Transaction]:
        """Loads and caches pre-populated mock dataset"""
        if self._mock_cache is not None:
            return self._mock_cache
        
        if not self.mock_data_path.exists():
            logger.warning(f"Mock transaction file not found at {self.mock_data_path}. Returning empty list.")
            return []

        try:
            with open(self.mock_data_path, "r", encoding="utf-8") as f:
                raw_list = json.load(f)
            txs = [TransactionNormalizer.from_dict(item) for item in raw_list]
            self._mock_cache = txs
            return txs
        except Exception as e:
            logger.error(f"Error loading mock dataset: {e}")
            return []

    async def get_wallet_transactions(self, wallet_address: str, limit: int = 50) -> List[Transaction]:
        """
        Fetches USDT-TRC20 transactions for a given wallet address.
        Supports both Mock mode and Live Tron API ingestion with rate limit handling.
        """
        if self.use_mock:
            return self._get_mock_transactions_for_wallet(wallet_address)

        # Attempt live API ingestion
        try:
            live_txs = await self._fetch_live_trongrid(wallet_address, limit)
            if not live_txs:
                logger.info(f"TronGrid returned 0 txs for {wallet_address}, trying Tronscan fallback...")
                live_txs = await self._fetch_live_tronscan(wallet_address, limit)
            
            if live_txs:
                return live_txs
            
            logger.warning(f"Live APIs returned no data for {wallet_address}. Falling back to mock dataset.")
            return self._get_mock_transactions_for_wallet(wallet_address)
        except Exception as e:
            logger.error(f"Live API error for {wallet_address}: {e}. Falling back to mock data.")
            return self._get_mock_transactions_for_wallet(wallet_address)

    def _get_mock_transactions_for_wallet(self, wallet_address: str) -> List[Transaction]:
        """Filters mock dataset for transactions involving wallet_address as sender or receiver"""
        all_mock = self._load_mock_transactions()
        wallet_address_clean = wallet_address.strip()
        
        matched = [
            tx for tx in all_mock
            if tx.from_address.lower() == wallet_address_clean.lower()
            or tx.to_address.lower() == wallet_address_clean.lower()
        ]
        
        # Deduplicate by tx_hash
        seen: Set[str] = set()
        deduped: List[Transaction] = []
        for tx in matched:
            if tx.tx_hash not in seen:
                seen.add(tx.tx_hash)
                deduped.append(tx)
                
        return deduped[:self.max_tx_per_wallet]

    async def _fetch_live_trongrid(self, address: str, limit: int) -> List[Transaction]:
        """Fetches TRC20 transfers from TronGrid REST API with headers and rate-limit retries"""
        url = f"{self.trongrid_url}/v1/accounts/{address}/transactions/trc20"
        params = {
            "limit": min(limit, 200),
            "contract_address": self.usdt_contract
        }
        headers = {}
        if self.api_key:
            headers["TRON-PRO-API-KEY"] = self.api_key

        async with httpx.AsyncClient(timeout=10.0) as client:
            for attempt in range(3):
                try:
                    resp = await client.get(url, params=params, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        raw_data = data.get("data", [])
                        txs = []
                        for item in raw_data:
                            tx = TransactionNormalizer.from_trongrid_trc20(item)
                            if tx and tx.amount >= settings.MIN_USDT_AMOUNT:
                                txs.append(tx)
                        return txs
                    elif resp.status_code == 429:  # Rate limited
                        await asyncio.sleep(1.0 * (attempt + 1))
                    else:
                        logger.warning(f"TronGrid API returned status {resp.status_code}")
                        break
                except Exception as ex:
                    logger.warning(f"TronGrid attempt {attempt + 1} failed: {ex}")
                    await asyncio.sleep(0.5)
        return []

    async def _fetch_live_tronscan(self, address: str, limit: int) -> List[Transaction]:
        """Fallback live ingestion from Tronscan API"""
        url = f"{self.tronscan_url}/token_trc20/transfers"
        params = {
            "limit": min(limit, 50),
            "start": 0,
            "contract_address": self.usdt_contract,
            "relatedAddress": address
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    token_transfers = data.get("token_transfers", [])
                    txs = []
                    for item in token_transfers:
                        tx = TransactionNormalizer.from_tronscan_trc20(item)
                        if tx and tx.amount >= settings.MIN_USDT_AMOUNT:
                            txs.append(tx)
                    return txs
            except Exception as ex:
                logger.warning(f"Tronscan fetch failed: {ex}")
        return []
