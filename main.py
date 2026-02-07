#!/usr/bin/env python3
"""
Discord Self-Bot - Educational Example Only
WARNING: This violates Discord's Terms of Service and may result in account suspension
Use Discord's official bot API instead: https://discord.com/developers/docs/intro
"""

import asyncio
import time
import os
import random
import signal
import sys
import threading
from discord_client import DiscordClient
from multi_client import MultiAccountManager, Account
from dotenv import load_dotenv
import logging

# Load env early so logging picks up LOG_LEVEL/DEBUG
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

# Global variables for graceful shutdown
shutdown_event = threading.Event()
auto_mode = False
auto_channel = None
multi_manager = None
use_multi_account = False

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    global auto_mode, multi_manager
    logger.info("Shutdown signal received...")
    auto_mode = False
    if multi_manager:
        multi_manager.stop_all()
    shutdown_event.set()
    print("\nShutting down gracefully...")

def load_random_message():
    """Load a random message from messages.txt with error handling"""
    try:
        with open('messages.txt', 'r', encoding='utf-8') as f:
            messages = [line.strip() for line in f if line.strip()]
        return random.choice(messages) if messages else "Default message"
    except FileNotFoundError:
        logger.warning("messages.txt not found, using default message")
        return "Hello from Discord self-bot! 🤖"
    except Exception as e:
        logger.error(f"Error loading messages: {e}")
        return "Error loading message"

def send_random_message(client, channel_id):
    """Send a random message with typing simulation and slowmode handling"""
    message = load_random_message()
    
    # Convert \n to actual line breaks for Discord
    message = message.replace('\\n', '\n')
    
    # Check slowmode (with caching)
    slowmode_delay = client.get_slowmode_delay(channel_id)
    if slowmode_delay > 0:
        logger.info(f"Channel has slowmode: {slowmode_delay} seconds")
    
    # Typing simulation
    if os.getenv('TYPING_SIMULATION', 'true').lower() == 'true':
        client.send_typing(channel_id)
        typing_duration = int(os.getenv('TYPING_DURATION', '2'))
        time.sleep(typing_duration)
    
    # Send message
    try:
        if os.getenv('SEND_EMBEDS', 'true').lower() == 'true':
            embed = {
                "title": os.getenv('DEFAULT_TITLE', 'Automated Message'),
                "description": message,
                "color": int(os.getenv('DEFAULT_COLOR', '#00ff00').lstrip('#'), 16),
            }
            if os.getenv('SHOW_TIMESTAMP', 'true').lower() == 'true':
                embed["timestamp"] = time.strftime('%Y-%m-%dT%H:%M:%S.000Z')
            
            result = client.send_message(channel_id, None, embed)
        else:
            result = client.send_message(channel_id, message)
        
        # Add slowmode info to result
        result['slowmode_delay'] = slowmode_delay
        logger.info(f"Message sent successfully to channel {channel_id}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        raise

def main():
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    load_dotenv()
    
    global multi_manager, use_multi_account
    
    try:
        # Check if multi-account mode is enabled
        account_names = os.getenv('ACCOUNT_NAMES', '').strip()
        use_multi_account = bool(account_names)
        
        if use_multi_account:
            logger.info("Initializing multi-account manager...")
            multi_manager = MultiAccountManager()
            
            # Initialize all account clients
            success_count = multi_manager.initialize_all_clients()
            
            if success_count == 0:
                logger.error("No accounts could be initialized. Check your tokens.")
                return
            
            print(f"=== Multi-Account Mode ===")
            print(f"Initialized {success_count} accounts:")
            
            for name in multi_manager.list_accounts():
                account = multi_manager.get_account(name)
                user_info = account.get_user_info()
                if user_info:
                    status = "✅" if account.enabled else "❌"
                    print(f"{status} {name}: {user_info['username']}#{user_info['discriminator']}")
                else:
                    print(f"❌ {name}: Failed to load")
            print()
        else:
            # Single account mode
            logger.info("Initializing single Discord client...")
            client = DiscordClient()
            
            # Get user info
            print("=== Discord User Info ===")
            user_info = client.get_user_info()
            print(f"Logged in as: {user_info['username']}#{user_info['discriminator']}")
            print(f"User ID: {user_info['id']}")
            print()
            
            # Get guilds
            print("=== Servers ===")
            guilds = client.get_guilds()
            for i, guild in enumerate(guilds[:10], 1):  # Show first 10 servers
                print(f"{i}. {guild['name']} (ID: {guild['id']})")
            print()
            
            # Example: Send a message
            default_channel = os.getenv('DEFAULT_CHANNEL_ID')
            if default_channel:
                print(f"Sending test message to channel {default_channel}...")
                result = send_random_message(client, default_channel)
                slowmode = result.get('slowmode_delay', 0)
                print(f"Message sent! Message ID: {result['id']}")
                if slowmode > 0:
                    print(f"Channel slowmode: {slowmode} seconds")
            else:
                print("No default channel configured. Set DEFAULT_CHANNEL_ID in .env file")
        
        # Interactive mode
        print("\n=== Interactive Mode ===")
        if use_multi_account:
            print("Multi-Account Commands:")
            print("  accounts - List all accounts")
            print("  sendall <message> - Send message from all accounts")
            print("  autoall - Toggle auto-send for all accounts")
            print("  rotation - Start/stop rotation mode (bypass slowmode)")
            print("  join <invite_link> - Join server with first available account")
            print("  joinall <invite_link> - Join server with all accounts")
            print("  join <account_name> <invite_link> - Join with specific account")
            print("  send <account_name> <message> - Send from specific account")
            print("  auto <account_name> - Toggle auto-send for specific account")
            print("  status <account_name> - Check account status")
        else:
            print("Single-Account Commands:")
            print("  send <channel_id> <message> - Send message")
            print("  join <invite_link> - Join server")
        
        print("  random <channel_id> - Send random message from messages.txt")
        print("  auto <channel_id> - Toggle auto-send mode")
        print("  slowmode <channel_id> - Check channel slowmode setting")
        print("  servers - List all servers")
        print("  channels <guild_id> - List channels in server")
        print("  find <guild_id> <channel_name> - Find channel by name")
        print("  messages <channel_id> - Get recent messages")
        print("  cache clear - Clear channel cache")
        print("  quit - Exit")
        
        global auto_mode, auto_channel
        
        while not shutdown_event.is_set():
            try:
                command = input("\n> ").strip().split(' ', 2)
                if not command:
                    continue
                
                cmd = command[0].lower()
                if DEBUG:
                    print(f"🔧 Debug: Command='{cmd}', Args={command[1:]}, Total args={len(command)}")
                
                if cmd == 'quit':
                    break

                handled = False

                # Multi-account commands
                if use_multi_account:
                    if 'multi_manager' not in globals() or multi_manager is None:
                        print("❌ Multi-account manager not initialized")
                        continue

                    if cmd == 'accounts':
                        handled = True
                        print("=== Accounts ===")
                        for name in multi_manager.list_accounts():
                            account = multi_manager.get_account(name)
                            user_info = account.get_user_info()
                            status = "🟢 Online" if account.client else "🔴 Offline"
                            auto_status = "🤖 Auto" if account.auto_mode else ""
                            print(f"{status} {name}: {user_info['username'] if user_info else 'Unknown'} {auto_status}")

                    elif cmd == 'sendall' and len(command) >= 2:
                        handled = True
                        message = command[1]
                        print(f"Sending from all accounts: {message}")
                        results = multi_manager.send_from_all(message)
                        for name, result in results.items():
                            if result:
                                print(f"✅ {name}: Sent (ID: {result.get('id')})")
                            else:
                                print(f"❌ {name}: Failed")

                    elif cmd == 'autoall':
                        handled = True
                        multi_manager.toggle_auto_all(not any(acc.auto_mode for acc in multi_manager.get_enabled_accounts()))
                        status = "enabled" if any(acc.auto_mode for acc in multi_manager.get_enabled_accounts()) else "disabled"
                        print(f"Auto-send for all accounts: {status}")

                    elif cmd == 'rotation':
                        handled = True
                        if multi_manager.rotation_active:
                            multi_manager.stop_rotation()
                            print("Rotation mode stopped")
                        else:
                            multi_manager.start_rotation()
                            print("Rotation mode started - bypassing slowmode with account rotation")

                    elif cmd == 'join' and len(command) >= 2:
                        handled = True
                        if len(command) == 2:
                            invite_link = command[1]
                            enabled_accounts = multi_manager.get_enabled_accounts()
                            if enabled_accounts:
                                account = enabled_accounts[0]
                                result = account.accept_invite(invite_link)
                                if result:
                                    guild_name = result.get('guild', {}).get('name', 'Unknown')
                                    print(f"✅ {account.name} joined server: {guild_name}")
                                else:
                                    print(f"❌ {account.name} failed to join server")
                            else:
                                print("❌ No available accounts")
                        else:
                            account_name = command[1]
                            invite_link = command[2]
                            account = multi_manager.get_account(account_name)
                            if account:
                                result = account.accept_invite(invite_link)
                                if result:
                                    guild_name = result.get('guild', {}).get('name', 'Unknown')
                                    print(f"✅ {account_name} joined server: {guild_name}")
                                else:
                                    print(f"❌ {account_name} failed to join server")
                            else:
                                print(f"❌ Account '{account_name}' not found")

                    elif cmd == 'joinall' and len(command) >= 2:
                        handled = True
                        invite_link = command[1]
                        print(f"Joining server with all accounts: {invite_link}")
                        results = multi_manager.join_all_accounts(invite_link)
                        for name, result in results.items():
                            if result:
                                guild_name = result.get('guild', {}).get('name', 'Unknown')
                                print(f"✅ {name}: Joined {guild_name}")
                            else:
                                print(f"❌ {name}: Failed to join")

                    elif cmd == 'send' and len(command) >= 3:
                        handled = True
                        account_name = command[1]
                        message = ' '.join(command[2:])
                        account = multi_manager.get_account(account_name)
                        if account:
                            result = account.send_message(message)
                            if result:
                                print(f"✅ Sent from {account_name} (ID: {result.get('id')})")
                            else:
                                print(f"❌ Failed to send from {account_name}")
                        else:
                            print(f"Account '{account_name}' not found")

                    elif cmd == 'auto' and len(command) >= 2:
                        handled = True
                        account_name = command[1]
                        account = multi_manager.get_account(account_name)
                        if account:
                            account.toggle_auto_mode(not account.auto_mode)
                            status = "enabled" if account.auto_mode else "disabled"
                            print(f"Auto-send for {account_name}: {status}")
                        else:
                            print(f"Account '{account_name}' not found")

                    elif cmd == 'status' and len(command) >= 2:
                        handled = True
                        account_name = command[1]
                        account = multi_manager.get_account(account_name)
                        if account:
                            user_info = account.get_user_info()
                            status = "🟢 Online" if account.client else "🔴 Offline"
                            auto_status = "🤖 Auto: ON" if account.auto_mode else "🤖 Auto: OFF"
                            print(f"{status} {account_name}")
                            if user_info:
                                print(f"  User: {user_info['username']}#{user_info['discriminator']}")
                            print(f"  {auto_status}")
                            if account.channel_id:
                                print(f"  Channel: {account.channel_id}")
                        else:
                            print(f"Account '{account_name}' not found")

                # Single-account commands (fallback)
                if not handled and (not use_multi_account):
                    if cmd == 'random' and len(command) >= 2:
                        handled = True
                        channel_id = command[1]
                        print(f"Sending random message to {channel_id}...")
                        result = send_random_message(client, channel_id)
                        slowmode = result.get('slowmode_delay', 0)
                        print(f"Sent! Message ID: {result['id']}")
                        if slowmode > 0:
                            print(f"Channel slowmode: {slowmode} seconds")
                    elif cmd == 'send' and len(command) >= 3:
                        handled = True
                        channel_id = command[1]
                        message_content = command[2]
                        print(f"Sending to {channel_id}: {message_content}")
                        result = client.send_message(channel_id, message_content)
                        print(f"Sent! Message ID: {result['id']}")
                    elif cmd == 'join' and len(command) >= 2:
                        handled = True
                        invite_link = command[1]
                        print(f"Joining server: {invite_link}")
                        result = client.accept_invite(invite_link)
                        if result:
                            guild_name = result.get('guild', {}).get('name', 'Unknown')
                            print(f"✅ Joined server: {guild_name}")
                        else:
                            print("❌ Failed to join server")

                # Common commands
                if not handled and cmd == 'slowmode' and len(command) >= 2:
                    handled = True
                    channel_id = command[1]
                    print(f"🔍 Checking slowmode for channel: {channel_id}")
                    
                    if use_multi_account:
                        # Use first available account
                        enabled_accounts = multi_manager.get_enabled_accounts()
                        print(f"📊 Available accounts: {len(enabled_accounts)}")
                        
                        if enabled_accounts:
                            account = enabled_accounts[0]  # Use first account
                            print(f"👤 Using account: {account.name}")
                            
                            # Check if client is initialized
                            if account.client:
                                slowmode = account.client.get_slowmode_delay(channel_id)
                                print(f"✅ Client initialized for {account.name}")
                            else:
                                print(f"❌ Client not initialized for {account.name}")
                                slowmode = 0
                        else:
                            print("❌ No enabled accounts available")
                            slowmode = 0
                    else:
                        slowmode = client.get_slowmode_delay(channel_id)
                    
                    if slowmode > 0:
                        print(f"🐌 Channel slowmode: {slowmode} seconds")
                        if slowmode >= 3600:
                            hours = slowmode // 3600
                            minutes = (slowmode % 3600) // 60
                            print(f"📅 That's {hours}h {minutes}m")
                    else:
                        print("✅ Channel has no slowmode")

                if not handled and cmd == 'cache' and len(command) >= 2 and command[1].lower() == 'clear':
                    handled = True
                    if use_multi_account:
                        for account in multi_manager.get_enabled_accounts():
                            account.client.clear_cache()
                    else:
                        client.clear_cache()
                    print("Channel cache cleared")

                if not handled and cmd == 'servers':
                    handled = True
                    print("=== All Servers ===")
                    if use_multi_account:
                        enabled_accounts = multi_manager.get_enabled_accounts()
                        if not enabled_accounts:
                            print("❌ No enabled accounts available")
                            guilds = []
                        else:
                            for account in enabled_accounts:
                                try:
                                    guilds = account.client.get_user_guilds()
                                except Exception as e:
                                    logger.error(f"Failed to list servers for {account.name}: {e}")
                                    guilds = []

                                print(f"\n--- {account.name} servers ({len(guilds)}) ---")
                                for i, guild in enumerate(guilds, 1):
                                    print(f"{i}. {guild['name']} (ID: {guild['id']})")
                            guilds = []
                    else:
                        guilds = client.get_user_guilds()
                    
                    for i, guild in enumerate(guilds, 1):
                        print(f"{i}. {guild['name']} (ID: {guild['id']})")

                if not handled and cmd == 'channels' and len(command) >= 2:
                    handled = True
                    guild_id = command[1]
                    print(f"Channels in server {guild_id}:")
                    if use_multi_account:
                        account = next(iter(multi_manager.get_enabled_accounts()), None)
                        if account:
                            channels = account.client.get_text_channels(guild_id)
                        else:
                            channels = []
                    else:
                        channels = client.get_text_channels(guild_id)
                    
                    for channel in channels:
                        print(f"  #{channel['name']} (ID: {channel['id']}, Type: {channel['type']})")

                if not handled and cmd == 'find' and len(command) >= 3:
                    handled = True
                    guild_id = command[1]
                    channel_name = command[2]
                    if use_multi_account:
                        account = next(iter(multi_manager.get_enabled_accounts()), None)
                        if account:
                            channel = account.client.get_channel_by_name(guild_id, channel_name)
                        else:
                            channel = None
                    else:
                        channel = client.get_channel_by_name(guild_id, channel_name)
                    
                    if channel:
                        print(f"Found channel: #{channel['name']} (ID: {channel['id']})")
                    else:
                        print(f"Channel '{channel_name}' not found in server {guild_id}")

                if not handled and cmd == 'messages' and len(command) >= 2:
                    handled = True
                    channel_id = command[1]
                    print(f"Recent messages in {channel_id}:")
                    if use_multi_account:
                        account = next(iter(multi_manager.get_enabled_accounts()), None)
                        if account:
                            messages = account.client.get_channel_messages(channel_id, limit=5)
                        else:
                            messages = []
                    else:
                        messages = client.get_channel_messages(channel_id, limit=5)
                    
                    for msg in reversed(messages):  # Show in chronological order
                        author = msg.get('author', {})
                        print(f"  {author.get('username', 'Unknown')}: {msg.get('content', '')[:50]}...")

                if not handled:
                    print("Invalid command or missing arguments")
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error processing command: {e}")
                print(f"Error: {e}")
        
        print("Goodbye!")
        logger.info("Bot shutdown complete")
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"Error: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure your Discord token(s) are correct")
        print("2. Check if you have internet connection")
        print("3. Verify your account(s) aren't locked")

if __name__ == "__main__":
    main()
