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