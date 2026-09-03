import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
BASE_DIR = Path(__file__).resolve().parent
env_path = BASE_DIR / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

class Settings:
    """Central settings loader reading from environment variables / .env"""
    USE_MOCK_DATA: bool = os.getenv("USE_MOCK_DATA", "true").lower() == "true"
    TRONGRID_API_KEY: str = os.getenv("TRONGRID_API_KEY", "").strip()
    TRON_GRID_BASE_URL: str = os.getenv("TRON_GRID_BASE_URL", "https://api.trongrid.io").strip()
    TRONSCAN_BASE_URL: str = os.getenv("TRONSCAN_BASE_URL", "https://apilist.tronscanapi.com/api").strip()
    
    MAX_TRANSACTIONS_PER_WALLET: int = int(os.getenv("MAX_TRANSACTIONS_PER_WALLET", "50"))
    MAX_HOPS: int = int(os.getenv("MAX_HOPS", "4"))
    FLOW_THRESHOLD_PERCENT: float = float(os.getenv("FLOW_THRESHOLD_PERCENT", "10.0"))
    MIN_USDT_AMOUNT: float = float(os.getenv("MIN_USDT_AMOUNT", "1.0"))
    
    HOST: str = os.getenv("HOST", "0.0.0.0").strip()
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG_MODE: bool = os.getenv("DEBUG_MODE", "true").lower() == "true"

    # Smart Contract Address for TRC20 USDT on Tron Mainnet
    USDT_TRC20_CONTRACT: str = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"

settings = Settings()
