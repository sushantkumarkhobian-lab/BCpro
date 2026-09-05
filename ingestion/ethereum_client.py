import json
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Set, Optional
import httpx

from config import settings
from schemas.models import Transaction
from ingestion.normalizer import TransactionNormalizer

logger = logging.getLogger(__name__)

class EthereumClient:
    """Client for fetching and normalizing Ethereum USDT-ERC20 transactions"""

    def __init__(self):
        self.use_mock = settings.USE_MOCK_DATA
        self.api_key = settings.ETHERSCAN_API_KEY
        self.etherscan_url = settings.ETHERSCAN_BASE_URL
        self.usdt_contract = settings.USDT_ERC20_CONTRACT
        self.max_tx_per_wallet = settings.MAX_TRANSACTIONS_PER_WALLET
        self.mock_data_path = Path(__file__).resolve().parent.parent / "data" / "mock_transactions_eth.json"
        
        self._mock_cache: Optional[List[Transaction]] = None

    def _load_mock_transactions(self) -> List[Transaction]:
        """Loads and caches pre-populated mock dataset for Ethereum"""
        if self._mock_cache is not None:
            return self._mock_cache
        
        if not self.mock_data_path.exists():
            logger.warning(f"Ethereum mock transaction file not found at {self.mock_data_path}. Returning empty list.")
            return []

        try:
            with open(self.mock_data_path, "r", encoding="utf-8") as f:
                raw_list = json.load(f)
            txs = [TransactionNormalizer.from_dict(item) for item in raw_list]
            self._mock_cache = txs
            return txs
        except Exception as e:
            logger.error(f"Error loading Ethereum mock dataset: {e}")
            return []

    async def get_wallet_transactions(self, wallet_address: str, limit: int = 50) -> List[Transaction]:
        """
        Fetches USDT-ERC20 transactions for a given wallet address.
        Supports both Mock mode and Live Etherscan API ingestion.
        """
        if self.use_mock:
            return self._get_mock_transactions_for_wallet(wallet_address)

        # Attempt live API ingestion
        try:
            live_txs = await self._fetch_live_etherscan(wallet_address, limit)
            if live_txs:
                return live_txs
            
            logger.warning(f"Etherscan returned no data for {wallet_address}. Falling back to mock dataset.")
            return self._get_mock_transactions_for_wallet(wallet_address)
        except Exception as e:
            logger.error(f"Etherscan API error for {wallet_address}: {e}. Falling back to mock data.")
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

    async def _fetch_live_etherscan(self, address: str, limit: int) -> List[Transaction]:
        """Fetches ERC20 transfers from Etherscan API with retry logic"""
        params = {
            "module": "account",
            "action": "tokentx",
            "contractaddress": self.usdt_contract,
            "address": address,
            "page": 1,
            "offset": min(limit, 100),
            "sort": "desc"
        }
        if self.api_key:
            params["apikey"] = self.api_key

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) WalletTrace/1.0"
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            for attempt in range(3):
                try:
                    resp = await client.get(self.etherscan_url, params=params, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        result = data.get("result", [])
                        if isinstance(result, list):
                            txs = []
                            for item in result:
                                tx = TransactionNormalizer.from_etherscan_erc20(item)
                                if tx and tx.amount >= settings.MIN_USDT_AMOUNT:
                                    txs.append(tx)
                            return txs
                        else:
                            logger.warning(f"Etherscan message: {data.get('message')} - {data.get('result')}")
                    elif resp.status_code == 429:
                        await asyncio.sleep(1.0 * (attempt + 1))
                    else:
                        logger.warning(f"Etherscan API returned status {resp.status_code}")
                        break
                except Exception as ex:
                    logger.warning(f"Etherscan attempt {attempt + 1} failed: {ex}")
                    await asyncio.sleep(0.5)
        return []
