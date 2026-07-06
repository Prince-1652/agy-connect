"""Custom exceptions for agy-connect."""

class AgyConnectException(Exception):
    """Base exception for all agy-connect errors."""
    pass

class AgyNotInstalled(AgyConnectException):
    """Raised when the agy executable cannot be found."""
    pass

class AuthenticationRequired(AgyConnectException):
    """Raised when agy is not authenticated."""
    pass

class ProcessCrash(AgyConnectException):
    """Raised when the agy process crashes unexpectedly."""
    pass

class InvalidState(AgyConnectException):
    """Raised for illegal state transitions."""
    pass

class StreamError(AgyConnectException):
    """Raised when there is an error reading the output stream."""
    pass

class CompletionError(AgyConnectException):
    """Raised when completion detection fails."""
    pass

class QueueError(AgyConnectException):
    """Raised when there is an error in the request queue."""
    pass

class ConfigurationError(AgyConnectException):
    """Raised for invalid configuration."""
    pass

class SessionNotFound(AgyConnectException):
    """Raised when a requested session does not exist."""
    pass

class HistoryError(AgyConnectException):
    """Raised when there is an error loading or saving history."""
    pass
