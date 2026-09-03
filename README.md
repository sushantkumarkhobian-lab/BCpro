# WalletTrace - Blockchain Forensics Engine (Tron USDT-TRC20)

A deterministic, high-performance Blockchain Forensics & Fund Tracing Engine designed for **USDT (TRC-20)** on the **Tron Network**. 

WalletTrace ingests transaction data, constructs NetworkX flow graphs, clusters related wallet addresses using explainable heuristics, performs multi-hop peel-chain tracing, and attributes terminal destination wallets to known cryptocurrency exchanges (Binance, Huobi, OKX, Kraken, etc.).

---

## 🌟 Key Features

- **Multi-Hop Peel-Chain Tracing**: Automatically traverses transaction graphs up to \(N\) hops to follow laundered funds across intermediate mule/peel wallets.
- **Explainable Address Clustering**: Groups related addresses based on Co-Spending, Common Funder, and Deposit-Sweep patterns with human-readable audit trails.
- **Defensible Exchange Attribution**: Matches terminal wallets against curated exchange deposit address signatures.
- **Dual Ingestion Engine**:
  - **Offline Mock Mode (`USE_MOCK_DATA=true`)**: Instant, zero-dependency reproducible demo dataset.
  - **Live Tron Mainnet Mode (`USE_MOCK_DATA=false`)**: Live query engine combining **TronGrid** and **TronScan** public APIs with rate-limit retries.

---

## 📂 Project Structure

```text
BC/
├── .env                       # Environment configuration file
├── main.py                    # FastAPI application entry point
├── config.py                  # Environment variable configuration loader
├── api/                       # REST API route handlers
├── ingestion/                 # TronGrid / TronScan API integration & Normalizer
├── graph/                     # NetworkX Transaction Graph Builder
├── clustering/                # Explainable Address Clustering Engine
├── tracing/                   # Multi-hop Fund Tracing Engine
├── attribution/               # Known Exchange Address Matcher
├── schemas/                   # Pydantic models & API DTOs
├── data/                      # Mock transaction & exchange datasets
└── tests/                     # Automated test suites

```

---

## ⚙️ Environment Configuration (`.env`)

To reproduce results or adapt the engine to your needs, copy `.env.example` to `.env` or edit the existing `.env` file in the root directory:

```bash
cp .env.example .env
```

### Key `.env` Settings Explained

| Key | Default Value | Recommended Change / Notes |
| :--- | :--- | :--- |
| `USE_MOCK_DATA` | `false` | **`true`** for zero-dependency offline testing with instant mock data.<br>**`false`** for live Tron mainnet queries. |
| `TRONGRID_API_KEY` | `your-api-key` | *(Optional for Mock mode)*. Get a free API key at [Trongrid.io](https://www.trongrid.io/) to prevent rate limiting in live mode. |
| `TRON_GRID_BASE_URL` | `https://api.trongrid.io` | TronGrid REST API endpoint. |
| `TRONSCAN_BASE_URL` | `https://apilist.tronscanapi.com/api` | TronScan REST API endpoint fallback. |
| `MAX_TRANSACTIONS_PER_WALLET` | `50` | Maximum transactions fetched per wallet per query depth. |
| `MAX_HOPS` | `4` | Default depth limit for multi-hop graph expansion. |
| `FLOW_THRESHOLD_PERCENT` | `10.0` | Percentage of outgoing wallet volume required to classify a path as a **Primary Peel Flow** (range: 1.0 to 100.0). |
| `MIN_USDT_AMOUNT` | `1.0` | Minimum transfer amount (USDT) to filter out spam or dust transactions. |
| `HOST` | `0.0.0.0` | Bind IP for the FastAPI server. |
| `PORT` | `8000` | Port for the FastAPI server. |
| `DEBUG_MODE` | `true` | Enables auto-reload on code modifications. |

> [!TIP]
> **To test immediately without any API keys or network requests:**
> Set `USE_MOCK_DATA=true` in your `.env` file.

---

## 🚀 How to Run

### 1. Prerequisites
- Python 3.9+ installed on your system.

### 2. Install Dependencies
Install all required packages from `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 3. Start the Forensics Server
Run the FastAPI application via `main.py`:

```bash
python main.py
```
*Alternatively, run using Uvicorn:*
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Once started, the server will output:
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

Open your browser and navigate to **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)** to access the interactive Swagger API documentation.

---

## 💡 Quick Start Example

### 1. Health Check Endpoint
Verify that the service is running:

```bash
curl -X GET "http://127.0.0.1:8000/health"
```

**Response:**
```json
{
  "status": "healthy",
  "service": "wallettrace-blockchain",
  "version": "1.0.0",
  "use_mock_data": true,
  "primary_chain": "tron (USDT-TRC20)",
  "default_max_hops": 4
}
```

---

### 2. Multi-Hop Fund Trace Request (cURL)

Trace funds starting from a seed wallet address:

```bash
curl -X POST "http://127.0.0.1:8000/trace" \
     -H "Content-Type: application/json" \
     -d '{
       "address": "T_VICTIM_SIH_DEMO_999",
       "max_hops": 3,
       "flow_threshold_percent": 10.0
     }'
```

*(Note: If testing in live mode `USE_MOCK_DATA=false`, replace `"T_VICTIM_SIH_DEMO_999"` with a live Tron wallet address such as `TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t`)*

---

### 3. Example Request using Python (`requests` library)

```python
import requests

url = "http://127.0.0.1:8000/trace"
payload = {
    "address": "T_VICTIM_SIH_DEMO_999",
    "max_hops": 4,
    "flow_threshold_percent": 10.0
}

response = requests.post(url, json=payload)
data = response.json()

print(f"Seed Address      : {data['seed_address']}")
print(f"Transactions      : {data['total_transactions_ingested']}")
print(f"Clusters Found    : {data['summary']['clusters_found']}")
print(f"Target Exchange   : {data['summary']['attributed_exchange']}")

# Print Primary Peel-Chain Path
primary_path = data.get("primary_path")
if primary_path:
    print("\n--- Primary Fund Flow Path ---")
    print(f"Path Hops         : {' -> '.join(primary_path['path_addresses'])}")
    print(f"Total Amount      : ${primary_path['total_flow_amount']:,.2f} USDT")
    print(f"Terminal Wallet   : {primary_path['terminal_address']}")
```

---

## 🧪 Running Unit Tests

To run the automated forensic test suite:

```bash
pytest tests/
```

---
