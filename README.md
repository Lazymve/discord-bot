# Discord Self-Bot (Educational Example)

⚠️ **WARNING**: This code violates Discord's Terms of Service and may result in account suspension. Use Discord's official bot API instead.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create `.env` file from `.env.example`:
```bash
cp .env.example .env
```

3. Get your Discord user token:
   - Open Discord in browser
   - Press F12, go to Application/Storage tab
   - Find `token` in localStorage/cookies
   - Copy the token value

4. Edit `.env` file:
```
DISCORD_USER_TOKEN=your_token_here
DEFAULT_SERVER_ID=your_server_id_here
DEFAULT_CHANNEL_ID=your_channel_id_here
```

5. Configure messaging settings in `.env`:
   - `DELAY_BETWEEN_MESSAGES` - Base delay between messages (seconds)
   - `RANDOM_DELAY_MIN/MAX` - Random delay range
   - `TYPING_SIMULATION` - Show typing indicator before sending
   - `AUTO_SEND` - Enable automatic message sending
   - `SEND_EMBEDS` - Send messages as embeds

6. Add messages to `messages.txt` (one per line) for random selection

7. Find server/channel IDs:
   - Use `servers` command to list all servers
   - Use `channels <server_id>` to list channels in a server
   - Use `find <server_id> <channel_name>` to find specific channel

## Multi-Account Support

The bot supports multiple Discord accounts simultaneously:

### Setup

1. Configure accounts in `.env`:
```env
# Default server and channel IDs (used for all accounts in multi-account mode)
DEFAULT_SERVER_ID=your_server_id_here
DEFAULT_CHANNEL_ID=your_channel_id_here

# Multi-Account Support (comma-separated)
ACCOUNT_NAMES=Account1,Account2,Account3
ACCOUNT1_TOKEN=your_first_token_here
ACCOUNT1_ENABLED=true

ACCOUNT2_TOKEN=your_second_token_here
ACCOUNT2_ENABLED=false

ACCOUNT3_TOKEN=your_third_token_here
ACCOUNT3_ENABLED=false
```

**Optional:** Use different servers/channels per account:
```env
ACCOUNT1_SERVER_ID=custom_server1
ACCOUNT1_CHANNEL_ID=custom_channel1
ACCOUNT2_SERVER_ID=custom_server2
ACCOUNT2_CHANNEL_ID=custom_channel2
```

2. Set `ACCOUNT_NAMES` with your account names (comma-separated)
3. Configure each account's token and enabled status
4. All accounts will use the same server/channel by default
5. Run the bot - it will automatically detect multi-account mode

### Multi-Account Commands

- `accounts` - List all accounts with status
- `sendall <message>` - Send message from all enabled accounts
- `autoall` - Toggle auto-send for all accounts
- `rotation` - Start/stop rotation mode (bypass slowmode)
- `send <account_name> <message>` - Send from specific account
- `auto <account_name>` - Toggle auto-send for specific account
- `status <account_name>` - Check account status

### Rotation Mode (Slowmode Bypass)

The bot includes intelligent rotation to bypass slowmode restrictions:

**Setup in `.env`:**
```env
# Rotation Settings
ROTATION_MODE=true
ROTATION_DELAY=1  # Seconds between accounts in rotation
ROTATION_MESSAGES_PER_ACCOUNT=1  # Messages before switching
```

**How it works:**
1. **Smart rotation** - Automatically switches between accounts when one hits slowmode
2. **Message limits** - Each account sends X messages before rotating to next
3. **Slowmode detection** - Respects each account's individual slowmode
4. **Continuous messaging** - No 45-minute delays with multiple accounts

**Example with 3 accounts and 10-second slowmode:**
- Account1 sends message (10s cooldown)
- Account2 sends message (10s cooldown) 
- Account3 sends message (10s cooldown)
- Account1 ready again, cycle continues

**Benefits:**
- **Bypass slowmode** - No waiting for slowmode timeouts
- **High frequency** - Messages every few seconds instead of hours
- **Automatic** - No manual switching required
- **Respectful** - Still follows Discord's per-account limits

### Features

- **Independent control** - Each account can be enabled/disabled
- **Separate auto-send** - Individual auto-send modes per account
- **Status monitoring** - Real-time account status display
- **Graceful shutdown** - All accounts stop cleanly on exit
- **Error isolation** - One account failure doesn't affect others

### Interactive Commands

- `send <channel_id> <message>` - Send a message
- `random <channel_id>` - Send random message from messages.txt
- `auto <channel_id>` - Toggle auto-send mode
- `slowmode <channel_id>` - Check channel slowmode setting
- `servers` - List all servers
- `channels <guild_id>` - List channels in server
- `find <guild_id> <channel_name>` - Find channel by name
- `messages <channel_id>` - Get recent messages
- `quit` - Exit

### Random Messaging

The bot supports randomized messaging from `messages.txt`:
- Each line is treated as a separate message
- Messages are selected randomly
- Configurable delays and typing simulation
- **Automatic slowmode detection and respect**
- Can be used manually or in auto-mode

### Slowmode Handling

The bot automatically detects and respects channel slowmode:
- Checks channel slowmode before sending messages
- Adjusts auto-send delays to respect slowmode limits
- Shows slowmode information when sending messages
- Use `slowmode <channel_id>` command to check manually

### Programmatic Usage

```python
from discord_client import DiscordClient

client = DiscordClient()
user_info = client.get_user_info()
client.send_message("channel_id", "Hello World!")
```

## Important Notes

- This is for **educational purposes only**
- Discord actively detects and bans self-bots
- Use official Discord bot API for legitimate applications
- You're responsible for any account consequences

## Official Alternative

Use Discord's bot API: https://discord.com/developers/docs/intro

## Features

- Send messages via web requests
- Get user info and servers
- List channels and messages
- Send typing indicators
- Support for embeds
- Interactive command mode
