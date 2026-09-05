import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from api.routes import router

app = FastAPI(
    title="WalletTrace Blockchain Forensics API",
    description=(
        "Deterministic Multi-Chain Blockchain Forensics Engine for USDT (Tron TRC-20 & Ethereum ERC-20). "
        "Provides Data Ingestion, NetworkX Transaction Graph Analysis, Explainable Address Clustering, "
        "Multi-Hop Peel-Chain Fund Tracing, and Defensible Exchange Attribution."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for cross-origin dashboard & AI team integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(router)

if __name__ == "__main__":
    chain_display = "Ethereum (USDT-ERC20)" if settings.TARGET_CHAIN == "ethereum" else "Tron (USDT-TRC20)"
    mode_display = "MOCK DATA MODE" if settings.USE_MOCK_DATA else f"LIVE {settings.TARGET_CHAIN.upper()} API MODE"

    print("=========================================================")
    print(" Starting WalletTrace Blockchain Forensics Server...")
    print(f" Target Chain : {chain_display}")
    print(f" Ingestion    : {mode_display}")
    print(f" Max Hops     : {settings.MAX_HOPS}")
    print(f" Threshold    : {settings.FLOW_THRESHOLD_PERCENT}%")
    print(f" Docs (Swagger): http://{settings.HOST if settings.HOST != '0.0.0.0' else '127.0.0.1'}:{settings.PORT}/docs")
    print("=========================================================")
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG_MODE)

