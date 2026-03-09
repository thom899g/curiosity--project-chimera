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