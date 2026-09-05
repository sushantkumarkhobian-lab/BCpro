from typing import Optional, Union
from config import settings
from ingestion.tron_client import TronClient
from ingestion.ethereum_client import EthereumClient

_tron_client: Optional[TronClient] = None
_ethereum_client: Optional[EthereumClient] = None

def get_tron_client() -> TronClient:
    """Returns singleton instance of TronClient"""
    global _tron_client
    if _tron_client is None:
        _tron_client = TronClient()
    return _tron_client

def get_ethereum_client() -> EthereumClient:
    """Returns singleton instance of EthereumClient"""
    global _ethereum_client
    if _ethereum_client is None:
        _ethereum_client = EthereumClient()
    return _ethereum_client

def get_blockchain_client(address_or_chain: Optional[str] = None) -> Union[TronClient, EthereumClient]:
    """
    Factory method to return appropriate Blockchain client.
    Auto-detects based on address prefix ('0x' -> Ethereum, 'T' -> Tron)
    or falls back to settings.TARGET_CHAIN configured in .env.
    """
    if address_or_chain:
        clean = address_or_chain.strip()
        if clean.lower() in ["ethereum", "eth"] or clean.startswith("0x") or clean.startswith("0X"):
            return get_ethereum_client()
        if clean.lower() == "tron" or clean.startswith("T"):
            return get_tron_client()

    # Fallback to .env configuration setting
    if settings.TARGET_CHAIN == "ethereum":
        return get_ethereum_client()
    
    return get_tron_client()
