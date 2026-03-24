"""
Centralized logging configuration for the REACH Agent backend.

This module provides structured logging across all agent components.
All logs are printed to console with consistent formatting.
"""

import logging
import logging.config
import sys
from typing import Optional
import json
from datetime import datetime


# ── Custom JSON Formatter ──────────────────────────────────────────────────

class StructuredFormatter(logging.Formatter):
    """
    Formats log records as structured text with clear sections.
    Easy to read while maintaining machine-readable structure.
    """
    
    LEVEL_COLORS = {
        logging.DEBUG: "\033[36m",      # Cyan
        logging.INFO: "\033[32m",       # Green
        logging.WARNING: "\033[33m",    # Yellow
        logging.ERROR: "\033[31m",      # Red
        logging.CRITICAL: "\033[35m",   # Magenta
    }
    RESET = "\033[0m"
    
    def format(self, record: logging.LogRecord) -> str:
        """Format a log record with structured output and color."""
        # Color the level name
        level_color = self.LEVEL_COLORS.get(record.levelno, "")
        level_name = f"{level_color}[{record.levelname:<8}]{self.RESET}"
        
        # Timestamp
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        # Logger name (component)
        logger_name = record.name.split(".")[-1][:15].ljust(15)
        
        # Main message
        message = record.getMessage()
        
        # Build base log line
        base = f"{timestamp} {level_name} {logger_name} │ {message}"
        
        # Add exception info if present
        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            return f"{base}\n{exc_text}"
        
        return base


# ── Logger Factory ────────────────────────────────────────────────────────

def get_logger(name: str) -> logging.Logger:
    """
    Get or create a logger for a specific module.
    
    Args:
        name: Module name (typically __name__)
    
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


# ── Initialize Logging ────────────────────────────────────────────────────

def configure_logging(level: str = "INFO") -> None:
    """
    Configure the root logger with structured formatting.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Ensure we only configure once
    if logging.getLogger().handlers:
        return
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level))
    
    # Apply structured formatter
    formatter = StructuredFormatter()
    console_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level))
    root_logger.addHandler(console_handler)
    
    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("supabase").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)


# ── Context Helpers ───────────────────────────────────────────────────────

class LogContext:
    """Helper for logging with context (user_id, conversation_id, etc.)"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.context = {}
    
    def set(self, **kwargs) -> "LogContext":
        """Set context values (e.g., user_id, conversation_id)."""
        self.context.update(kwargs)
        return self
    
    def _format_context(self) -> str:
        """Format context as a readable string."""
        if not self.context:
            return ""
        items = [f"{k}={v}" for k, v in self.context.items()]
        return f" ({', '.join(items)})"
    
    def debug(self, msg: str, **data):
        context = self._format_context()
        self.logger.debug(f"{msg}{context}", extra={"data": data})
    
    def info(self, msg: str, **data):
        context = self._format_context()
        self.logger.info(f"{msg}{context}", extra={"data": data})
    
    def warning(self, msg: str, **data):
        context = self._format_context()
        self.logger.warning(f"{msg}{context}", extra={"data": data})
    
    def error(self, msg: str, exc_info=False, **data):
        context = self._format_context()
        self.logger.error(f"{msg}{context}", exc_info=exc_info, extra={"data": data})
    
    def critical(self, msg: str, exc_info=False, **data):
        context = self._format_context()
        self.logger.critical(f"{msg}{context}", exc_info=exc_info, extra={"data": data})


# Initialize on module load
configure_logging("INFO")
