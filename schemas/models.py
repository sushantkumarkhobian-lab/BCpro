from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class Transaction(BaseModel):
    """Normalized TRC20/Tron USDT Transaction Schema"""
    tx_hash: str = Field(..., description="Unique transaction hash on Tron blockchain")
    from_address: str = Field(..., description="Sender wallet address")
    to_address: str = Field(..., description="Recipient wallet address")
    amount: float = Field(..., description="Transfer amount in USDT")
    token: str = Field("USDT", description="Token symbol (default USDT)")
    timestamp: str = Field(..., description="ISO 8601 formatted timestamp")
    chain: str = Field("tron", description="Blockchain network (e.g. tron)")
    block_number: Optional[int] = Field(None, description="Tron block height")

class GraphNode(BaseModel):
    """Node in the NetworkX transaction graph representing a wallet"""
    id: str = Field(..., description="Wallet address")
    label: str = Field(..., description="Short label or full wallet address")
    hop_level: int = Field(0, description="Minimum distance/hop level from seed address")
    total_inflow: float = Field(0.0, description="Total USDT incoming volume")
    total_outflow: float = Field(0.0, description="Total USDT outgoing volume")
    is_seed: bool = Field(False, description="True if seed victim wallet")
    is_terminal: bool = Field(False, description="True if leaf node in max hop boundary")

class GraphEdge(BaseModel):
    """Directed edge in the NetworkX transaction graph representing transfer flow"""
    source: str = Field(..., description="Sender wallet address")
    target: str = Field(..., description="Recipient wallet address")
    amount: float = Field(..., description="Total USDT transferred across edge")
    tx_count: int = Field(1, description="Number of transactions between pair")
    tx_hashes: List[str] = Field(default_factory=list, description="List of transaction hashes")
    token: str = Field("USDT", description="Token symbol")

class GraphResponse(BaseModel):
    """Response containing nodes and edges for visualization & analysis"""
    seed_address: str
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    total_nodes: int
    total_edges: int

class ClusterEvidence(BaseModel):
    """Explainable evidence proving why two addresses are clustered together"""
    addr_a: str = Field(..., description="First wallet address in relationship")
    addr_b: str = Field(..., description="Second wallet address in relationship")
    heuristic_name: str = Field(..., description="Name of the deterministic rule (e.g., common_funding_source)")
    evidence_tx: str = Field(..., description="Transaction hash or reference ID serving as evidence")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score of clustering match")
    explanation: str = Field(..., description="Human-readable justification for court/forensic audit")

class Cluster(BaseModel):
    """Group of addresses inferred to be controlled by the same entity"""
    cluster_id: str = Field(..., description="Unique cluster identifier (e.g. C001)")
    addresses: List[str] = Field(..., description="List of member wallet addresses")
    primary_heuristic: str = Field(..., description="Dominant heuristic rule that formed the cluster")
    evidence_chain: List[ClusterEvidence] = Field(default_factory=list, description="All logged evidence links")

class TraceStep(BaseModel):
    """Single step along a fund tracing path"""
    hop: int = Field(..., description="Hop distance from seed wallet (0, 1, 2...)")
    address: str = Field(..., description="Wallet address at this step")
    incoming_amount: float = Field(0.0, description="Amount received at this step")
    outgoing_amount: float = Field(0.0, description="Amount sent forward from this step")
    tx_hash: Optional[str] = Field(None, description="Transaction hash leading to this hop")
    timestamp: Optional[str] = Field(None, description="Timestamp of transfer")
    flow_category: str = Field("PRIMARY", description="PRIMARY (bulk movement) or SECONDARY (peeled change/dust)")
    flow_percentage: float = Field(100.0, description="Percentage of previous hop balance carried forward")

class TracePath(BaseModel):
    """Path taken by money leading from victim seed wallet to terminal wallet"""
    path_id: str
    is_primary_path: bool
    hops_count: int
    terminal_address: str
    total_amount_transferred: float
    steps: List[TraceStep]

class AttributionResult(BaseModel):
    """Exchange entity match result for a wallet address"""
    address: str
    status: str = Field(..., description="'KNOWN' or 'UNATTRIBUTED'")
    exchange_name: Optional[str] = Field(None, description="Matched exchange name (e.g., Binance, OKX)")
    entity_type: Optional[str] = Field(None, description="Entity classification (e.g., Exchange)")
    deposit_address: Optional[str] = Field(None, description="Exchange deposit wallet if matched")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Attribution confidence score")
    source: Optional[str] = Field(None, description="Documented provenance source for attribution")
    recommendation: Optional[str] = Field(None, description="Forensic recommendation for investigator")

class TraceRequest(BaseModel):
    """Request payload for POST /trace"""
    address: str = Field(..., description="Seed suspicious/victim wallet address (e.g. T_VICTIM_SIH_DEMO_999)")
    max_hops: Optional[int] = Field(None, description="Optional override for max hop depth (1-10)")
    flow_threshold_percent: Optional[float] = Field(None, description="Optional override for peel-chain threshold")

class TraceResponse(BaseModel):
    """Unified master JSON response returned by POST /trace for AI/ML/Dashboard consumption"""
    seed_address: str
    max_hops_traversed: int
    flow_threshold_percent: float
    total_transactions_ingested: int
    primary_path: Optional[TracePath] = None
    all_paths: List[TracePath] = Field(default_factory=list)
    clusters: List[Cluster] = Field(default_factory=list)
    graph: GraphResponse
    attribution: AttributionResult
    summary: Dict[str, Any] = Field(default_factory=dict)
