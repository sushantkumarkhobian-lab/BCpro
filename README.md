# WalletTrace - Multi-Chain Blockchain Forensics Engine (Tron & Ethereum)

A deterministic, high-performance Multi-Chain Blockchain Forensics & Fund Tracing Engine designed for **USDT** on both the **Tron Network (TRC-20)** and **Ethereum Network (ERC-20)**.

WalletTrace ingests transaction data, constructs NetworkX flow graphs, clusters related wallet addresses using explainable account heuristics, performs multi-hop peel-chain tracing, and attributes terminal destination wallets to known cryptocurrency exchanges (Binance, OKX, Kraken, Coinbase, HTX, etc.) and smart contract protocols.

---

## 🌟 Key Features

- **Multi-Chain Support (Tron & Ethereum)**: Seamlessly switch between Tron (USDT-TRC20) and Ethereum (USDT-ERC20) via a simple change in `.env` or automatic address routing (`0x...` -> Ethereum, `T...` -> Tron).
- **Multi-Hop Peel-Chain Tracing**: Automatically traverses transaction graphs up to \(N\) hops to follow laundered funds across intermediate mule/peel wallets.
- **Explainable Address Clustering**: Groups related addresses based on Co-Spending, Common Funder, and Deposit-Sweep patterns with human-readable audit trails.
- **Defensible Exchange Attribution**: Matches terminal wallets against curated exchange deposit address databases and dynamic live block explorer tags (**TronScan** & **Etherscan**).
- **Dual Ingestion Engine**:
  - **Offline Mock Mode (`USE_MOCK_DATA=true`)**: Instant, zero-dependency reproducible demo dataset for both Tron and Ethereum.
  - **Live Mainnet Mode (`USE_MOCK_DATA=false`)**: Live query engine combining **TronGrid**, **TronScan**, and **Etherscan** public APIs with rate-limit retries.

---

## 📂 Project Structure

```text
BC/
├── .env                       # Single environment configuration file for all chains
├── main.py                    # FastAPI application entry point
├── config.py                  # Environment variable configuration loader
├── api/                       # REST API route handlers
├── ingestion/                 # Tron & Ethereum client, normalizers, & client factory
├── graph/                     # NetworkX Transaction Graph Builder
├── clustering/                # Explainable Address Clustering Engine
├── tracing/                   # Multi-hop Fund Tracing Engine
├── attribution/               # Known Exchange & Protocol Address Matcher
├── schemas/                   # Pydantic models & API DTOs
├── data/                      # Mock transaction & exchange datasets (Tron & Ethereum)
├── scripts/                   # Test scripts (test_live_tron.py & test_live_eth.py)
└── tests/                     # Automated test suites (test_forensics.py & test_eth_forensics.py)
```

---

## ⚙️ Environment Configuration (`.env`)

All engine configuration is managed in `.env`. Edit the `.env` file in the root directory:

```bash
cp .env.example .env
```

### Key `.env` Settings Explained

| Key | Default Value | Recommended Change / Description |
| :--- | :--- | :--- |
| `TARGET_CHAIN` | `tron` | **`tron`** for Tron (USDT-TRC20)<br>**`ethereum`** for Ethereum (USDT-ERC20). |
| `USE_MOCK_DATA` | `true` | **`true`** for zero-dependency offline testing.<br>**`false`** for live mainnet queries. |
| `TRONGRID_API_KEY` | `your-api-key` | *(Optional for Mock mode)*. Free API key at [Trongrid.io](https://www.trongrid.io/) for live Tron data. |
| `TRON_GRID_BASE_URL` | `https://api.trongrid.io` | TronGrid REST API endpoint. |
| `TRONSCAN_BASE_URL` | `https://apilist.tronscanapi.com/api` | TronScan REST API endpoint fallback. |
| `ETHERSCAN_API_KEY` | `your-api-key` | *(Optional for Mock mode)*. Free API key at [Etherscan.io](https://etherscan.io/myapikey) for live Ethereum data. |
| `ETHERSCAN_BASE_URL` | `https://api.etherscan.io/api` | Etherscan REST API endpoint. |
| `USDT_TRC20_CONTRACT` | `TR7NHqje...` | Smart Contract Address for TRC20 USDT on Tron. |
| `USDT_ERC20_CONTRACT` | `0xdAC17F95...` | Smart Contract Address for ERC20 USDT on Ethereum. |
| `MAX_HOPS` | `4` | Default depth limit for multi-hop graph expansion. |
| `FLOW_THRESHOLD_PERCENT` | `10.0` | Percentage of outgoing volume required to classify a **Primary Peel Flow**. |
| `MIN_USDT_AMOUNT` | `1.0` | Minimum transfer amount (USDT) to filter out dust transactions. |

---

## 🔄 How to Switch Between Tron and Ethereum

Switching chains is simple and can be done in two ways:

### Method 1: Change `TARGET_CHAIN` in `.env`

To run in **Ethereum Mode**:
```env
TARGET_CHAIN=ethereum
```

To run in **Tron Mode**:
```env
TARGET_CHAIN=tron
```

### Method 2: Automatic Address Routing (No `.env` edit needed!)
The API automatically detects the address prefix:
- Any address starting with **`0x...`** automatically routes to **Ethereum**.
- Any address starting with **`T...`** automatically routes to **Tron**.

---

## 🚀 How to Run

### 1. Prerequisites
- Python 3.9+ installed on your system.

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Start the Forensics Server
Run the application via `main.py`:

```bash
python main.py
```

**Console Output when `TARGET_CHAIN=ethereum`:**
```text
=========================================================
 Starting WalletTrace Blockchain Forensics Server...
 Target Chain : Ethereum (USDT-ERC20)
 Ingestion    : LIVE ETHEREUM API MODE (or MOCK DATA MODE)
 Max Hops     : 4
 Threshold    : 10.0%
 Docs (Swagger): http://127.0.0.1:8000/docs
=========================================================
```

**Console Output when `TARGET_CHAIN=tron`:**
```text
=========================================================
 Starting WalletTrace Blockchain Forensics Server...
 Target Chain : Tron (USDT-TRC20)
 Ingestion    : LIVE TRON API MODE (or MOCK DATA MODE)
 Max Hops     : 4
 Threshold    : 10.0%
 Docs (Swagger): http://127.0.0.1:8000/docs
=========================================================
```

Navigate to **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)** to access the interactive Swagger API documentation.

---

## 💡 Quick Start Examples

### 1. Multi-Hop Fund Trace Request (Ethereum)
```bash
curl -X POST "http://127.0.0.1:8000/trace" \
     -H "Content-Type: application/json" \
     -d '{
       "address": "0x_VICTIM_SIH_DEMO_999",
       "max_hops": 4,
       "flow_threshold_percent": 10.0
     }'
```

### 2. Multi-Hop Fund Trace Request (Tron)
```bash
curl -X POST "http://127.0.0.1:8000/trace" \
     -H "Content-Type: application/json" \
     -d '{
       "address": "T_VICTIM_SIH_DEMO_999",
       "max_hops": 4,
       "flow_threshold_percent": 10.0
     }'
```

---

## 🧪 Testing

### Run Interactive Test Scripts
- **Ethereum Test Script**: `python scripts/test_live_eth.py`
- **Tron Test Script**: `python scripts/test_live_tron.py`

### Run Full Automated Test Suite (Pytest)
```bash
python -m pytest -p no:pytest_ethereum tests/
```

For full detailed documentation, step-by-step `.env` setup, and Etherscan/TronScan instructions, see [`run.md`](file:///c:/Users/Sushant%20Kumar/OneDrive/Desktop/Projects/BC/run.md).
