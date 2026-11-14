"""Streaming logic for reading process output."""

import asyncio
from typing import AsyncGenerator
from .config import Config
from .completion import CompletionDetector
from .exceptions import StreamError
from .logger import get_logger

logger = get_logger()

class StreamHandler:
    """Reads stream chunks, checks completion, and yields tokens."""
    
    def __init__(self, config: Config, completion_detector: CompletionDetector) -> None:
        self.config = config
        self.detector = completion_detector
        
    async def process_stream(self, stdout: asyncio.StreamReader) -> AsyncGenerator[str, None]:
        """
        Reads from stdout asynchronously, yields text chunks, and stops when completion is detected.
        Never buffers the full response before yielding.
        """
        buffer = ""
        
        while True:
            try:
                # Read chunks according to config
                chunk_bytes = await stdout.read(self.config.stream_chunk_size)
            except Exception as e:
                raise StreamError(f"Failed to read from stream: {e}")
                
            if not chunk_bytes:
                # EOF reached
                if buffer:
                    is_complete, cleaned = self.detector.detect(buffer)
                    if not is_complete:
                        # Yield the remaining buffer even if no explicit completion marker was found at EOF
                        yield buffer
                break
                
            try:
                chunk_str = chunk_bytes.decode(errors='replace')
            except UnicodeDecodeError as e:
                logger.warning(f"Decoding error in stream: {e}")
                chunk_str = chunk_bytes.decode(errors='ignore')
                
            buffer += chunk_str
            
            # Check if this new buffer hits completion
            is_complete, cleaned = self.detector.detect(buffer)

            if is_complete:
                # Yield content before the marker and stop
                if cleaned:
                    yield cleaned
                return

            # Sliding-window approach: keep marker_len chars in reserve so we never
            # accidentally yield part of the completion marker.
            marker_len = len(self.detector.marker)
            if marker_len and len(buffer) > marker_len:
                safe = buffer[:-marker_len]
                buffer = buffer[-marker_len:]
                if safe:
                    yield safe
        
class SafeStreamer:
    """A streamer that yields tokens incrementally without buffering everything, while safely avoiding the marker."""
    def __init__(self, marker: str, chunk_size: int):
        self.marker = marker
        self.chunk_size = chunk_size
        self.window = ""
        
    async def stream(self, stdout: asyncio.StreamReader) -> AsyncGenerator[str, None]:
        marker_len = len(self.marker)
        if marker_len == 0:
            while True:
                data = await stdout.read(self.chunk_size)
                if not data:
                    break
                yield data.decode(errors='replace')
            return
            
        while True:
            data = await stdout.read(self.chunk_size)
            if not data:
                # EOF
                if self.window:
                    # If window is exactly marker, don't yield it
                    if self.window != self.marker:
                        # What if it's partly marker? It might just be leftover.
                        yield self.window.replace(self.marker, "")
                break
                
            text = data.decode(errors='replace')
            self.window += text
            
            # If marker is found in the window, we stop
            if self.marker in self.window:
                parts = self.window.split(self.marker)
                # Yield the part before the marker
                if parts[0]:
                    yield parts[0]
                break
                
            # If window is large enough, yield the safe part
            if len(self.window) > marker_len:
                safe_len = len(self.window) - marker_len
                yield self.window[:safe_len]
                self.window = self.window[safe_len:]
