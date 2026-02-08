#!/usr/bin/env python3
"""
Non-interactive service version of Discord Self-Bot
Starts in auto-mode and runs without user input
"""

import asyncio
import time
import os
import random
import signal
import sys
from discord_client import DiscordClient
from multi_client import MultiAccountManager, Account
from dotenv import load_dotenv
import logging

# Load env early
load_dotenv()

def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}

def _env_log_level(default: str = "INFO") -> int:
    level_name = (os.getenv("LOG_LEVEL") or default).strip().upper()
    return getattr(logging, level_name, logging.INFO)

# Configure logging
logging.basicConfig(level=_env_log_level(), format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEBUG = _env_bool("DEBUG", False)

def load_random_message() -> str:
    """Load a random message from messages.txt"""
    try:
        with open('messages.txt', 'r', encoding='utf-8') as f:
            messages = [line.strip() for line in f if line.strip()]
        if messages:
            return random.choice(messages)
    except Exception as e:
        logger.error(f"Error loading messages: {e}")
    return "Default message"

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("Received shutdown signal, stopping...")
    if 'multi_manager' in globals() and multi_manager:
        multi_manager.stop_all()
    sys.exit(0)

def main():
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    logger.info("Starting Discord Self-Bot Service")
    
    # Check if multi-account mode
    use_multi_account = os.getenv('SPAM1_TOKEN') and os.getenv('SPAM2_TOKEN')
    
    if use_multi_account:
        logger.info("Initializing multi-account manager")
        multi_manager = MultiAccountManager()
        
        # Manually create accounts (like main.py does)
        from multi_client import Account
        
        spam1 = Account("SPAM1", os.getenv('SPAM1_TOKEN'), os.getenv('DEFAULT_SERVER_ID'), os.getenv('DEFAULT_CHANNEL_ID'))
        spam2 = Account("SPAM2", os.getenv('SPAM2_TOKEN'), os.getenv('DEFAULT_SERVER_ID'), os.getenv('DEFAULT_CHANNEL_ID'))
        
        # Initialize clients for each account
        if spam1.initialize_client():
            multi_manager.accounts["SPAM1"] = spam1
            logger.info(f"Added account: SPAM1")
        else:
            logger.error(f"Failed to initialize SPAM1")
            
        if spam2.initialize_client():
            multi_manager.accounts["SPAM2"] = spam2
            logger.info(f"Added account: SPAM2")
        else:
            logger.error(f"Failed to initialize SPAM2")
        
        logger.info(f"Total accounts loaded: {len(multi_manager.accounts)}")
        
        # Start rotation if enabled
        if os.getenv('ROTATION_MODE', 'false').lower() == 'true':
            logger.info("Starting rotation mode")
            multi_manager.start_rotation()
        else:
            logger.info("Starting auto-all mode")
            multi_manager.toggle_auto_all(True)
        
        # Keep running
        try:
            while True:
                time.sleep(10)
                # Check if rotation is still active
                if multi_manager.rotation_mode and not multi_manager.rotation_active:
                    logger.warning("Rotation stopped unexpectedly, restarting...")
                    multi_manager.start_rotation()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            multi_manager.stop_all()
    else:
        logger.info("Single account mode not supported in service")
        sys.exit(1)

if __name__ == "__main__":
    main()
