import datetime
from typing import Dict, Any, Optional
from schemas.models import Transaction

class TransactionNormalizer:
    """Normalizes raw TronGrid / Tronscan / Mock transaction payloads into unified Transaction objects"""

    @staticmethod
    def _format_timestamp(ts: Any) -> str:
        """Converts epoch milliseconds or string timestamp to ISO 8601 string"""
        if isinstance(ts, (int, float)):
            # Tron API timestamps are usually epoch milliseconds
            if ts > 1e11:  # Milliseconds
                dt = datetime.datetime.fromtimestamp(ts / 1000.0, tz=datetime.timezone.utc)
            else:  # Seconds
                dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
            return dt.isoformat().replace("+00:00", "Z")
        elif isinstance(ts, str):
            return ts
        return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Transaction:
        """Constructs a Transaction object from a standardized dictionary"""
        return Transaction(
            tx_hash=str(data.get("tx_hash") or data.get("transaction_id") or data.get("hash") or "UNKNOWN_HASH"),
            from_address=str(data.get("from_address") or data.get("from") or data.get("transferFrom_address") or ""),
            to_address=str(data.get("to_address") or data.get("to") or data.get("transferTo_address") or ""),
            amount=float(data.get("amount") or data.get("quant") or 0.0),
            token=str(data.get("token") or data.get("symbol") or "USDT"),
            timestamp=cls._format_timestamp(data.get("timestamp") or data.get("block_timestamp")),
            chain=str(data.get("chain", "tron")),
            block_number=data.get("block_number") or data.get("block")
        )

    @classmethod
    def from_trongrid_trc20(cls, item: Dict[str, Any]) -> Optional[Transaction]:
        """Normalizes TronGrid TRC20 transfer JSON object"""
        try:
            tx_hash = item.get("transaction_id")
            from_addr = item.get("from")
            to_addr = item.get("to")
            
            # TRC20 USDT has 6 decimal places on Tron
            raw_value = float(item.get("value", 0))
            token_info = item.get("token_info", {})
            decimals = int(token_info.get("decimals", 6))
            amount = raw_value / (10 ** decimals)

            timestamp = cls._format_timestamp(item.get("block_timestamp"))
            
            if not tx_hash or not from_addr or not to_addr:
                return None

            return Transaction(
                tx_hash=tx_hash,
                from_address=from_addr,
                to_address=to_addr,
                amount=amount,
                token=token_info.get("symbol", "USDT"),
                timestamp=timestamp,
                chain="tron",
                block_number=item.get("block")
            )
        except Exception:
            return None

    @classmethod
    def from_tronscan_trc20(cls, item: Dict[str, Any]) -> Optional[Transaction]:
        """Normalizes Tronscan TRC20 transfer JSON object"""
        try:
            tx_hash = item.get("transaction_id") or item.get("hash")
            from_addr = item.get("from_address")
            to_addr = item.get("to_address")
            
            raw_value = float(item.get("quant", item.get("amount", 0)))
            decimals = int(item.get("decimals", 6))
            amount = raw_value / (10 ** decimals) if raw_value > 1e5 else raw_value

            timestamp = cls._format_timestamp(item.get("block_timestamp") or item.get("timestamp"))

            if not tx_hash or not from_addr or not to_addr:
                return None

            return Transaction(
                tx_hash=tx_hash,
                from_address=from_addr,
                to_address=to_addr,
                amount=amount,
                token=item.get("symbol", "USDT"),
                timestamp=timestamp,
                chain="tron",
                block_number=item.get("block")
            )
        except Exception:
            return None

    @classmethod
    def from_etherscan_erc20(cls, item: Dict[str, Any]) -> Optional[Transaction]:
        """Normalizes Etherscan tokentx ERC-20 transfer JSON object"""
        try:
            tx_hash = item.get("hash") or item.get("transactionHash")
            from_addr = item.get("from")
            to_addr = item.get("to")

            raw_value = float(item.get("value", 0))
            decimals = int(item.get("tokenDecimal", 6))
            amount = raw_value / (10 ** decimals)

            ts = item.get("timeStamp") or item.get("timestamp")
            if ts:
                try:
                    ts = int(ts)
                except ValueError:
                    pass
            timestamp = cls._format_timestamp(ts)

            if not tx_hash or not from_addr or not to_addr:
                return None

            return Transaction(
                tx_hash=str(tx_hash),
                from_address=str(from_addr),
                to_address=str(to_addr),
                amount=amount,
                token=str(item.get("tokenSymbol", "USDT")),
                timestamp=timestamp,
                chain="ethereum",
                block_number=int(item.get("blockNumber")) if item.get("blockNumber") else None
            )
        except Exception:
            return None

