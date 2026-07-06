"""Manager for handling multiple active sessions."""

import asyncio
import time
from typing import Dict, List, Optional
from .config import Config
from .session import Session
from .exceptions import SessionNotFound, ConfigurationError
from .logger import get_logger

logger = get_logger()

class SessionManager:
    """
    Manages multiple independent conversation sessions.
    Implements an LRU cache and idle cleanup.
    """
    
    def __init__(self, config: Optional[Config] = None) -> None:
        self.config = config or Config()
        self._sessions: Dict[str, Session] = {}
        self._access_times: Dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task[None]] = None
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
    async def get(self, session_id: str) -> Session:
        """Retrieve an existing session or create a new one."""
        async with self._lock:
            if session_id in self._sessions:
                self._access_times[session_id] = time.time()
                return self._sessions[session_id]
                
            if len(self._sessions) >= self.config.max_sessions:
                await self._evict_oldest()
                
            logger.info(f"Creating new session: {session_id}")
            session = Session(session_id, self.config)
            await session.initialize()
            
            self._sessions[session_id] = session
            self._access_times[session_id] = time.time()
            return session
            
    async def _evict_oldest(self) -> None:
        """Evicts the least recently used session."""
        if not self._access_times:
            return
            
        oldest_id = min(self._access_times.keys(), key=lambda k: self._access_times[k])
        logger.info(f"Evicting oldest session: {oldest_id}")
        await self.remove(oldest_id)
        
    async def remove(self, session_id: str) -> None:
        """Remove and cleanup a session."""
        if session_id in self._sessions:
            session = self._sessions[session_id]
            await session.cleanup()
            del self._sessions[session_id]
            del self._access_times[session_id]
            
    async def shutdown(self) -> None:
        """Shutdown all sessions and cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            
        async with self._lock:
            session_ids = list(self._sessions.keys())
            for sid in session_ids:
                await self.remove(sid)
                
    async def _cleanup_loop(self) -> None:
        """Background loop to clean up idle sessions."""
        while True:
            try:
                await asyncio.sleep(60) # Check every 60 seconds
                now = time.time()
                async with self._lock:
                    idle_sids = [
                        sid for sid, last_access in self._access_times.items()
                        if now - last_access > self.config.idle_timeout
                    ]
                    for sid in idle_sids:
                        logger.info(f"Cleaning up idle session: {sid}")
                        await self.remove(sid)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                
    def list_sessions(self) -> List[str]:
        """List active session IDs."""
        return list(self._sessions.keys())
