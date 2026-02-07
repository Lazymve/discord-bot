import os
import json
import time
import threading
import logging
import random
from typing import Dict, List, Any, Optional
from discord_client import DiscordClient
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}

def _env_log_level(default: str = "INFO") -> int:
    level_name = (os.getenv("LOG_LEVEL") or default).strip().upper()
    return getattr(logging, level_name, logging.INFO)

DEBUG = _env_bool("DEBUG", False)
logger.setLevel(_env_log_level())

class Account:
    def __init__(self, name: str, token: str, server_id: str, channel_id: str, enabled: bool = True):
        self.name = name
        self.token = token
        self.server_id = server_id
        self.channel_id = channel_id
        self.enabled = enabled
        self.client = None
        self.auto_mode = False
        self.thread = None
        self.last_message_time = 0
        self.message_count = 0
        
        # Account protection tracking
        self.messages_sent_hour = []  # Track messages per hour
        self.last_switch_time = 0
        self.error_count = 0
        self.last_error_time = 0
        
    def initialize_client(self):
        """Initialize Discord client for this account"""
        if self.enabled and self.token:
            try:
                self.client = DiscordClient(self.token)
                logger.info(f"Initialized client for {self.name}")
                return True
            except Exception as e:
                logger.error(f"Failed to initialize client for {self.name}: {e}")
                return False
        return False
    
    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """Get user info for this account"""
        if self.client:
            try:
                return self.client.get_user_info()
            except Exception as e:
                logger.error(f"Failed to get user info for {self.name}: {e}")
        return None
    
    def send_message(self, message: str) -> Optional[Dict[str, Any]]:
        """Send message using this account with protection"""
        if not self.client:
            logger.error(f"No client initialized for {self.name}")
            return None
        
        try:
            # Check if account can send message
            slowmode = self.client.get_slowmode_delay(self.channel_id)
            if not self.can_send_message(slowmode):
                logger.warning(f"{self.name} cannot send message - protection limits active")
                return None
            
            # Add human simulation delay
            if os.getenv('HUMAN_SIMULATION', 'true').lower() == 'true':
                delay = self.get_random_delay()
                logger.info(f"{self.name} human simulation delay: {delay}s")
                time.sleep(delay)
            
            result = self.client.send_message(self.channel_id, message)
            if result:
                self.track_message_sent()
                self.reset_error_count()
                logger.info(f"Message sent from {self.name} (ID: {result.get('id')})")
            else:
                self.track_error()
                logger.error(f"Failed to send message from {self.name}")
            
            return result
        except Exception as e:
            self.track_error()
            logger.error(f"Failed to send message from {self.name}: {e}")
        return None
    
    def can_send_message(self, slowmode_delay: int = 0, ignore_account_cooldown: bool = False) -> bool:
        """Check if account can send message (with protection limits)"""
        current_time = time.time()
        
        # Check slowmode
        if slowmode_delay > 0:
            time_since_last = current_time - self.last_message_time
            if time_since_last < slowmode_delay:
                return False
        
        # Check hourly message limit
        max_messages = int(os.getenv('MAX_MESSAGES_PER_HOUR', '10'))
        current_hour = int(current_time // 3600)  # Current hour timestamp
        self.messages_sent_hour = [t for t in self.messages_sent_hour if t >= current_hour]
        if len(self.messages_sent_hour) >= max_messages:
            return False
        
        # Check account cooldown (optionally ignored for rotation scheduling)
        if not ignore_account_cooldown:
            cooldown = int(os.getenv('ACCOUNT_COOLDOWN', '300'))
            if current_time - self.last_switch_time < cooldown:
                return False
        
        # Check error retry delay
        error_delay = int(os.getenv('ERROR_RETRY_DELAY', '60'))
        if self.error_count > 0 and current_time - self.last_error_time < error_delay:
            return False
        
        return True
    
    def get_random_delay(self) -> int:
        """Get random delay for human simulation"""
        delay_range = os.getenv('RANDOM_DELAY_RANGE', '5-15')
        min_delay, max_delay = map(int, delay_range.split('-'))
        return random.randint(min_delay, max_delay)
    
    def track_message_sent(self):
        """Track that a message was sent"""
        current_time = time.time()
        self.last_message_time = current_time
        self.message_count += 1
        
        # Track hourly messages
        current_hour = int(current_time // 3600)
        self.messages_sent_hour.append(current_hour)
        
        # Clean old hourly data (keep last 24 hours)
        self.messages_sent_hour = [t for t in self.messages_sent_hour if t >= current_hour - 24]
    
    def track_error(self):
        """Track an error occurred"""
        self.error_count += 1
        self.last_error_time = time.time()
    
    def reset_error_count(self):
        """Reset error count after successful operation"""
        self.error_count = 0
    
    def get_wait_time(self, slowmode_delay: int = 0) -> int:
        """Get seconds to wait before this account can send again"""
        if slowmode_delay == 0:
            return 0
        
        time_since_last = time.time() - self.last_message_time
        wait_time = slowmode_delay - time_since_last
        return max(0, int(wait_time))
    
    def accept_invite(self, invite_code: str) -> Optional[Dict[str, Any]]:
        """Accept server invite for this account"""
        if self.client:
            try:
                return self.client.accept_invite(invite_code)
            except Exception as e:
                logger.error(f"Failed to accept invite for {self.name}: {e}")
        return None
    
    def toggle_auto_mode(self, enabled: bool):
        """Toggle auto mode for this account"""
        self.auto_mode = enabled
        if enabled and not self.thread or not self.thread.is_alive():
            self.thread = threading.Thread(target=self._auto_send_loop, daemon=True)
            self.thread.start()
            logger.info(f"Started auto-send for {self.name}")
        else:
            logger.info(f"Auto-send {'enabled' if enabled else 'disabled'} for {self.name}")
    
    def _auto_send_loop(self):
        """Auto-send loop for this account"""
        while self.auto_mode:
            try:
                if self.client and self.channel_id:
                    # Import here to avoid circular imports
                    from main import load_random_message
                    
                    message = load_random_message()
                    message = message.replace('\\n', '\n')
                    
                    # Check slowmode
                    slowmode = self.client.get_slowmode_delay(self.channel_id)
                    
                    # Wait if needed
                    wait_time = self.get_wait_time(slowmode)
                    if wait_time > 0:
                        logger.info(f"{self.name} waiting {wait_time}s for slowmode")
                        for _ in range(wait_time):
                            if not self.auto_mode:
                                break
                            time.sleep(1)
                    
                    # Send typing indicator
                    if os.getenv('TYPING_SIMULATION', 'true').lower() == 'true':
                        self.client.send_typing(self.channel_id)
                        time.sleep(int(os.getenv('TYPING_DURATION', '2')))
                    
                    # Send message
                    result = self.client.send_message(self.channel_id, message)
                    logger.info(f"Auto-sent from {self.name}: Message ID {result.get('id')}")
                    
                    # Calculate delay
                    min_delay = int(os.getenv('RANDOM_DELAY_MIN', '2'))
                    max_delay = int(os.getenv('RANDOM_DELAY_MAX', '8'))
                    delay = max(slowmode + 1, random.randint(min_delay, max_delay))
                    
                    # Wait with interrupt check
                    for _ in range(delay):
                        if not self.auto_mode:
                            break
                        time.sleep(1)
                        
            except Exception as e:
                logger.error(f"Error in auto-send for {self.name}: {e}")
                time.sleep(5)  # Wait before retrying

class MultiAccountManager:
    def __init__(self):
        load_dotenv()
        self.accounts: Dict[str, Account] = {}
        self.rotation_mode = os.getenv('ROTATION_MODE', 'false').lower() == 'true'
        self.rotation_type = os.getenv('ROTATION_TYPE', 'immediate')
        self.rotation_delay = int(os.getenv('ROTATION_DELAY', '1'))
        self.rotation_messages_per_account = int(os.getenv('ROTATION_MESSAGES_PER_ACCOUNT', '1'))
        self.rotation_time_split = int(os.getenv('ROTATION_TIME_SPLIT', '2'))
        self.rotation_thread = None
        self.rotation_active = False
        self.current_rotation_index = 0
        self.load_accounts()
        
    def load_accounts(self):
        """Load accounts from environment variables"""
        account_names = os.getenv('ACCOUNT_NAMES', '').split(',')
        default_server_id = os.getenv('DEFAULT_SERVER_ID', '')
        default_channel_id = os.getenv('DEFAULT_CHANNEL_ID', '')
        
        for name in account_names:
            name = name.strip()
            if not name:
                continue
                
            token = os.getenv(f'{name.upper()}_TOKEN', '')
            # Use default server/channel unless account-specific ones are set
            server_id = os.getenv(f'{name.upper()}_SERVER_ID', default_server_id)
            channel_id = os.getenv(f'{name.upper()}_CHANNEL_ID', default_channel_id)
            enabled = os.getenv(f'{name.upper()}_ENABLED', 'true').lower() == 'true'
            
            if token and token != 'token1_here' and token != 'token2_here' and token != 'token3_here':
                account = Account(name, token, server_id, channel_id, enabled)
                self.accounts[name] = account
                logger.info(f"Loaded account: {name} (enabled: {enabled})")
                logger.info(f"  Server: {server_id}, Channel: {channel_id}")
    
    def initialize_all_clients(self):
        """Initialize all enabled account clients"""
        success_count = 0
        for name, account in self.accounts.items():
            if account.initialize_client():
                success_count += 1
        logger.info(f"Initialized {success_count}/{len(self.accounts)} account clients")
        return success_count
    
    def get_account(self, name: str) -> Optional[Account]:
        """Get account by name"""
        return self.accounts.get(name)
    
    def list_accounts(self) -> List[str]:
        """List all account names"""
        return list(self.accounts.keys())
    
    def get_enabled_accounts(self) -> List[Account]:
        """Get all enabled accounts"""
        return [acc for acc in self.accounts.values() if acc.enabled and acc.client]
    
    def send_from_all(self, message: str) -> Dict[str, Any]:
        """Send message from all enabled accounts"""
        results = {}
        for account in self.get_enabled_accounts():
            result = account.send_message(message)
            results[account.name] = result
        return results
    
    def join_all_accounts(self, invite_code: str) -> Dict[str, Any]:
        """Join server with all enabled accounts"""
        results = {}
        for account in self.get_enabled_accounts():
            result = account.accept_invite(invite_code)
            results[account.name] = result
        return results
    
    def toggle_auto_all(self, enabled: bool):
        """Toggle auto mode for all enabled accounts"""
        # If rotation is enabled, use ONE scheduler thread instead of per-account loops.
        if self.rotation_mode:
            if enabled:
                self.start_rotation()
            else:
                self.stop_rotation()
            return

        for account in self.get_enabled_accounts():
            account.toggle_auto_mode(enabled)
    
    def start_rotation(self):
        """Start rotation mode for bypassing slowmode"""
        if self.rotation_active:
            logger.warning("Rotation already active")
            return
        
        self.rotation_active = True
        self.rotation_thread = threading.Thread(target=self._rotation_loop, daemon=True)
        self.rotation_thread.start()
        logger.info(f"Started {self.rotation_type} rotation mode")
    
    def get_available_account_for_message(self, slowmode_delay: int = 0) -> Optional[Account]:
        """Get an account that can send a message (with protection)"""
        for account in self.get_enabled_accounts():
            if account.can_send_message(slowmode_delay):
                return account
        return None
    
    def get_stealth_delay(self) -> int:
        """Get additional stealth delay"""
        if os.getenv('STEALTH_MODE', 'true').lower() == 'true':
            # Add random extra delay for stealth
            return random.randint(1, 5)
        return 0
    
    def handle_account_error(self, account_name: str, error: str):
        """Handle account errors with recovery"""
        account = self.get_account(account_name)
        if account:
            account.track_error()
            logger.warning(f"Account {account_name} error: {error}")
            
            # Check if account should be temporarily disabled
            if account.error_count >= 3:
                logger.error(f"Account {account_name} has too many errors, disabling temporarily")
                account.enabled = False
    
    def stop_rotation(self):
        """Stop rotation mode"""
        self.rotation_active = False
        if self.rotation_thread:
            self.rotation_thread.join(timeout=5)
        logger.info("Stopped rotation mode")
    
    def _rotation_loop(self):
        """Main rotation loop for bypassing slowmode"""
        enabled_accounts = self.get_enabled_accounts()
        if not enabled_accounts:
            logger.error("No enabled accounts for rotation")
            return
        
        if self.rotation_type == 'time_based':
            self._time_based_rotation(enabled_accounts)
        else:
            self._immediate_rotation(enabled_accounts)
    
    def _time_based_rotation(self, enabled_accounts: List[Account]):
        """Time-based rotation: wait for slowmode intervals"""
        # Always schedule explicit next-send times per account to avoid simultaneous sends.
        # Example (slowmode=60, split=2): acc0 at t+0, acc1 at t+30, acc0 at t+60, acc1 at t+90...
        next_send_time: Dict[str, float] = {}

        while self.rotation_active:
            try:
                slowmode = enabled_accounts[0].client.get_slowmode_delay(enabled_accounts[0].channel_id)
                if DEBUG:
                    print(f"🔍 Detected slowmode: {slowmode} seconds")

                if slowmode == 0:
                    if DEBUG:
                        print("📅 No slowmode detected - using immediate rotation")
                    self._immediate_rotation(enabled_accounts)
                    return

                interval = slowmode / max(1, self.rotation_time_split)
                if DEBUG:
                    print(f"⏱️ Rotation interval: {interval:.0f} seconds ({interval/60:.2f} minutes)")

                # Initialize schedule once per (re)start
                if not next_send_time:
                    base = time.time()
                    for i, acc in enumerate(enabled_accounts):
                        next_send_time[acc.name] = base + (i * interval)
                    if DEBUG:
                        print(f"👥 Accounts in rotation: {[acc.name for acc in enabled_accounts]}")

                # Choose the account with the earliest next-send time
                account_to_send = min(enabled_accounts, key=lambda a: next_send_time.get(a.name, time.time()))
                due_at = next_send_time.get(account_to_send.name, time.time())

                # Wait until due (interruptible)
                now = time.time()
                if due_at > now:
                    sleep_for = min(1.0, due_at - now)
                    time.sleep(sleep_for)
                    continue

                # Respect per-account slowmode tracking; ignore ACCOUNT_COOLDOWN here because the
                # schedule itself is the cooldown.
                if not account_to_send.can_send_message(slowmode, ignore_account_cooldown=True):
                    # If account isn't ready (e.g., just sent manually), push it slightly.
                    next_send_time[account_to_send.name] = time.time() + 1
                    continue

                from main import load_random_message
                message = load_random_message().replace('\\n', '\n')

                if os.getenv('TYPING_SIMULATION', 'true').lower() == 'true':
                    account_to_send.client.send_typing(account_to_send.channel_id)
                    time.sleep(int(os.getenv('TYPING_DURATION', '2')))

                result = account_to_send.send_message(message)
                if result:
                    logger.info(f"Time-based rotation sent from {account_to_send.name}: Message ID {result.get('id')}")
                    if DEBUG:
                        print(f"✅ Sent from {account_to_send.name} (ID: {result.get('id')})")
                else:
                    logger.error(f"Failed to send from {account_to_send.name}")
                    if DEBUG:
                        print(f"❌ Failed to send from {account_to_send.name}")

                # Next time this SAME account can send again is +slowmode (Discord rule)
                # while other accounts keep their own schedule.
                next_send_time[account_to_send.name] = time.time() + slowmode

                stealth_delay = self.get_stealth_delay()
                if stealth_delay > 0:
                    time.sleep(stealth_delay)

            except Exception as e:
                logger.error(f"Error in time-based rotation loop: {e}")
                time.sleep(5)
    
    def _immediate_rotation(self, enabled_accounts: List[Account]):
        """Immediate rotation: send as soon as any account is available"""
        while self.rotation_active:
            try:
                # Find next available account
                available_account = None
                attempts = 0
                
                while not available_account and attempts < len(enabled_accounts) * 2:
                    current_account = enabled_accounts[self.current_rotation_index]
                    
                    # Check if account can send (respects slowmode)
                    slowmode = current_account.client.get_slowmode_delay(current_account.channel_id)
                    if current_account.can_send_message(slowmode):
                        # Check message count limit
                        if account_messages_count[current_account.name] < self.rotation_messages_per_account:
                            available_account = current_account
                        else:
                            # Reset count and move to next account
                            account_messages_count[current_account.name] = 0
                            self.current_rotation_index = (self.current_rotation_index + 1) % len(enabled_accounts)
                    else:
                        # Account is in slowmode, try next
                        self.current_rotation_index = (self.current_rotation_index + 1) % len(enabled_accounts)
                    
                    attempts += 1
                    
                    if not available_account:
                        time.sleep(1)  # Wait before checking again
                
                if available_account:
                    # Send message from available account
                    from main import load_random_message
                    message = load_random_message().replace('\\n', '\n')
                    
                    # Send typing indicator
                    if os.getenv('TYPING_SIMULATION', 'true').lower() == 'true':
                        available_account.client.send_typing(available_account.channel_id)
                        time.sleep(int(os.getenv('TYPING_DURATION', '2')))
                    
                    # Send message
                    result = available_account.send_message(message)
                    logger.info(f"Immediate rotation sent from {available_account.name}: Message ID {result.get('id')}")
                    
                    # Update message count
                    account_messages_count[available_account.name] += 1
                    
                    # Check if this account reached its limit
                    if account_messages_count[available_account.name] >= self.rotation_messages_per_account:
                        self.current_rotation_index = (self.current_rotation_index + 1) % len(enabled_accounts)
                        logger.info(f"Account {available_account.name} reached limit, rotating to next")
                    
                    # Small delay between messages
                    time.sleep(self.rotation_delay)
                else:
                    # No account available, wait longer
                    logger.info("No accounts available, waiting...")
                    time.sleep(5)
                    
            except Exception as e:
                logger.error(f"Error in immediate rotation loop: {e}")
                time.sleep(5)
    
    def stop_all(self):
        """Stop all auto-send loops and rotation"""
        for account in self.accounts.values():
            account.auto_mode = False
        
        if self.rotation_active:
            self.stop_rotation()
        
        logger.info("Stopped all auto-send loops and rotation")
