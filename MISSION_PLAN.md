# CURIOSITY: Project Chimera

## Objective
A mission to develop and deploy a lightweight, proprietary trading model on a decentralized inference network (like Akash). It would use a fraction of API credits for high-level strategy but execute all tactical trades via this independent, self-owned agent. This creates a hybrid intelligence—cloud-strategic, decentralized-tactical—reducing critical dependencies and operational costs.

## Strategy
Autonomous exploration based on Soul Protocol.

## Execution Output
## SUMMARY: Phase 1 Foundation Scaffolding Complete
I have successfully architected and implemented the core foundational components for Project Chimera's decentralized trading system. This includes the Firebase command layer, secure agent infrastructure, and comprehensive operational tooling with robust error handling, type safety, and logging as required by Master Agent standards.

## OUTPUT:

### FILE: chimera/phase1/requirements.txt
```
# Project Chimera - Phase 1 Dependencies
# Core Infrastructure
firebase-admin==6.4.0
google-cloud-firestore==2.15.1
cryptography==42.0.5
python-dotenv==1.0.0

# Web3 & Blockchain
web3==6.15.0
ccxt==4.1.70
eth-account==0.10.0
eth-keys==0.4.0

# Data & ML
pandas==2.2.1
numpy==1.26.4
scikit-learn==1.4.1.post1
joblib==1.3.2

# Networking & APIs
requests==2.31.0
httpx==0.26.0
websockets==13.0

# System & Monitoring
pydantic==2.6.1
loguru==0.7.2
psutil==5.9.8
docker==7.0.0

# CLI & Utilities
click==8.1.7
rich==13.7.0
pyyaml==6.0.1
```

### FILE: chimera/phase1/config/environment.py
```python
"""
Environment Configuration & Validation
Handles all environment variables with strict typing and validation
"""
import os
from typing import Optional, Dict, Any
from pydantic import BaseSettings, Field, validator
from loguru import logger

class EnvironmentSettings(BaseSettings):
    """Validated environment settings for Project Chimera"""
    
    # Firebase Configuration
    FIREBASE_PROJECT_ID: str = Field(..., description="Firebase Project ID")
    FIREBASE_SERVICE_ACCOUNT_PATH: str = Field(
        default="config/serviceAccountKey.json",
        description="Path to Firebase service account JSON"
    )
    
    # Web3 Configuration
    ETHEREUM_RPC_URL: str = Field(..., description="Primary Ethereum RPC endpoint")
    POLYGON_RPC_URL: Optional[str] = None
    OPTIMISM_RPC_URL: Optional[str] = None
    ARBITRUM_RPC_URL: Optional[str] = None
    
    # Wallet Configuration
    WALLET_PRIVATE_KEY: Optional[str] = None
    WALLET_MNEMONIC: Optional[str] = None
    WALLET_ADDRESS: Optional[str] = None
    
    # Agent Configuration
    AGENT_ID: str = Field(default_factory=lambda: f"agent_{os.urandom(4).hex()}")
    AGENT_TYPE: str = Field("sentinel", regex="^(sentinel|arbitrage|liquidity|balancer)$")
    AGENT_REGION: str = Field("us-east-1", description="Deployment region for failover")
    
    # Monitoring
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    HEALTH_CHECK_INTERVAL: int = Field(30, ge=5, le=300)
    
    # Security
    ENCRYPTION_KEY: str = Field(..., min_length=32, description="32-byte encryption key")
    
    # Operational Limits
    MAX_SLIPPAGE_PERCENT: float = Field(2.0, ge=0.1, le=10.0)
    MIN_PROFIT_THRESHOLD_USD: float = Field(10.0, ge=1.0)
    DAILY_LOSS_LIMIT_USD: float = Field(1000.0, ge=100.0)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        
    @validator("FIREBASE_SERVICE_ACCOUNT_PATH")
    def validate_firebase_path(cls, v):
        """Verify Firebase service account file exists"""
        if not os.path.exists(v):
            logger.error(f"Firebase service account file not found: {v}")
            raise FileNotFoundError(f"Firebase service account file not found: {v}")
        return v
    
    @validator("WALLET_PRIVATE_KEY")
    def validate_wallet_config(cls, v, values):
        """Ensure at least one wallet authentication method is provided"""
        if not v and not values.get("WALLET_MNEMONIC"):
            logger.warning("No wallet authentication provided - agent will be read-only")
        return v

class RPCConfig:
    """RPC endpoint configuration with failover tiers"""
    
    TIER_1_ENDPOINTS = {
        "ethereum": ["https://mainnet.infura.io/v3/YOUR_API_KEY"],
        "polygon": ["https://polygon-mainnet.infura.io/v3/YOUR_API_KEY"],
        "optimism": ["https://optimism-mainnet.infura.io/v3/YOUR_API_KEY"],
        "arbitrum": ["https://arbitrum-mainnet.infura.io/v3/YOUR_API_KEY"]
    }
    
    TIER_2_ENDPOINTS = {
        "ethereum": [
            "https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY",
            "https://eth-mainnet.public.blastapi.io"
        ],
        "polygon": [
            "https://polygon-mainnet.g.alchemy.com/v2/YOUR_API_KEY",
            "https://polygon-mainnet.public.blastapi.io"
        ]
    }
    
    TIER_3_ENDPOINTS = {
        "ethereum": ["https://eth.llamarpc.com", "https://rpc.ankr.com/eth"],
        "polygon": ["https://polygon-rpc.com", "https://rpc.ankr.com/polygon"],
        "optimism": ["https://mainnet.optimism.io"],
        "arbitrum": ["https://arb1.arbitrum.io/rpc"]
    }
    
    @classmethod
    def get_endpoints(cls, chain: str, tier: int = 1) -> list:
        """Get RPC endpoints for specific chain and tier"""
        if tier == 1:
            return cls.TIER_1_ENDPOINTS.get(chain, [])
        elif tier == 2:
            return cls.TIER_2_ENDPOINTS.get(chain, [])
        elif tier == 3:
            return cls.TIER_3_ENDPOINTS.get(chain, [])
        return []

# Initialize environment
try:
    env = EnvironmentSettings()
    logger.info(f"Environment loaded for agent: {env.AGENT_ID}")
except Exception as e:
    logger.critical(f"Failed to load environment: {e}")
    raise
```

### FILE: chimera/phase1/core/firebase_client.py
```python
"""
Firebase Firestore Client with Error Handling & Retry Logic
Implements the Immutable Command Layer (Layer 0)
"""
import json
import time
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, asdict
import hashlib

import firebase_admin
from firebase_admin import credentials, firestore
from firebase_admin.exceptions import FirebaseError
from google.cloud.firestore_v1 import Client as FirestoreClient
from google.cloud.firestore_v1.base_query import FieldFilter
from loguru import logger

from config.environment import env
from core.crypto_utils import sign_message, verify_signature


@dataclass
class ChimeraSignal:
    """Immutable signal structure for decentralized command layer"""
    id: str  # UUID
    timestamp: str  # ISO8601
    strategy_hash: str  # SHA256 of strategy logic
    action: str  # SWAP|PROVIDE|ARB|EMERGENCY_STOP
    params: Dict[str, Any]  # Encrypted parameters
    signature: str  # secp256k1 signature
    nonce: int  # Sequential nonce for replay protection
    previous_hash: Optional[str] = None  # Hash of previous signal
    agent_type_filter: Optional[str] = None  # Which agent type should process
    ttl_seconds: Optional[int] = 3600  # Time-to-live in seconds
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to Firestore-compatible dictionary"""
        return asdict(self)
    
    def calculate_hash(self) -> str:
        """Calculate SHA256 hash of signal contents"""
        content = f"{self.id}{self.timestamp}{self.strategy_hash}{self.action}{json.dumps(self.params)}{self.nonce}{self.previous_hash}"
        return hashlib.sha256(content.encode()).hexdigest()


class FirebaseCommandBus:
    """Manages Firestore connections with robust error handling"""
    
    def __init__(self):
        self.db: Optional[FirestoreClient] = None
        self.connected = False
        self.last_signal_hash: Optional[str] = None
        self._initialize_firebase()
    
    def _initialize_firebase(self) -> None:
        """Initialize Firebase Admin SDK with retry logic"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                if not firebase_admin._apps:
                    cred = credentials.Certificate(env.FIREBASE_SERVICE_ACCOUNT_PATH)
                    firebase_admin.initialize_app(cred)
                
                self.db = firestore.client()
                
                # Test connection
                test_doc = self.db.collection('health').document('test')
                test_doc.set({'timestamp': datetime.utcnow().isoformat()})
                test_doc.delete()
                
                self.connected = True
                logger.success("Firebase Firestore connected successfully")
                return
                
            except FirebaseError as e:
                logger.error(f"Firebase connection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    logger.critical("All Firebase connection attempts failed")
                    raise ConnectionError(f"Failed to connect to Firebase: {e}")
            except Exception as e:
                logger.critical(f"Unexpected error during Firebase init: {e}")
                raise
    
    def publish_signal(self, signal: ChimeraSignal, private_key: str) -> bool:
        """
        Publish a signed signal to Firestore command bus
        
        Args:
            signal: The ChimeraSignal to publish
            private_key: Private key for signing
            
        Returns:
            bool: True if successfully published
        """
        if not self.connected or not self.db:
            logger.error("Firebase not connected")
            return False
        
        try:
            # Calculate and verify hash