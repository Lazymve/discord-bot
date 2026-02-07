import requests
import os
import json
import time
from dotenv import load_dotenv
from typing import Optional, Dict, Any, List
import logging

# Configure logging
load_dotenv()

def _env_log_level(default: str = "INFO") -> int:
    level_name = (os.getenv("LOG_LEVEL") or default).strip().upper()
    return getattr(logging, level_name, logging.INFO)

logging.basicConfig(level=_env_log_level(), format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DiscordClient:
    def __init__(self, token: str = None):
        load_dotenv()
        self.token = token or os.getenv('DISCORD_USER_TOKEN')
        if not self.token:
            raise ValueError("Discord user token is required")
        
        self.base_url = "https://discord.com/api/v10"
        self.headers = {
            'Authorization': f'{self.token}',
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # Cache for channel info to reduce API calls
        self._channel_cache = {}
        self._cache_expiry = 300  # 5 minutes cache
    
    def _make_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Make API request with error handling and retries"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.session.request(method, url, timeout=30, **kwargs)
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 5))
                    logger.warning(f"Rate limited. Waiting {retry_after} seconds...")
                    time.sleep(retry_after)
                    continue
                
                response.raise_for_status()
                return response.json() if response.content else {}
                
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    logger.error(f"Request failed after {max_retries} attempts: {e}")
                    raise
                logger.warning(f"Request failed (attempt {attempt + 1}): {e}")
                time.sleep(2 ** attempt)  # Exponential backoff
        
        return {}
    
    def get_user_info(self) -> Dict[str, Any]:
        """Get current user information"""
        return self._make_request('GET', f'{self.base_url}/users/@me')
    
    def get_guilds(self) -> List[Dict]:
        """Get all servers the user is in"""
        return self._make_request('GET', f'{self.base_url}/users/@me/guilds')

    def get_user_guilds(self) -> List[Dict]:
        """Get all servers the user is in (compat alias)"""
        return self.get_guilds()
    
    def get_channels(self, guild_id: str) -> List[Dict]:
        """Get all channels in a server"""
        return self._make_request('GET', f'{self.base_url}/guilds/{guild_id}/channels')
    
    def send_message(self, channel_id: str, content: str = None, embed: Optional[Dict] = None) -> Dict[str, Any]:
        """Send a message to a channel"""
        payload = {}
        
        if content:
            payload['content'] = content
        
        if embed:
            payload['embeds'] = [embed]
        
        # Ensure at least content or embeds is present
        if not payload:
            payload['content'] = "Empty message"
        
        return self._make_request('POST', f'{self.base_url}/channels/{channel_id}/messages', json=payload)
    
    def send_typing(self, channel_id: str) -> bool:
        """Send typing indicator to a channel"""
        try:
            response = self.session.post(f'{self.base_url}/channels/{channel_id}/typing', timeout=10)
            return response.status_code == 204
        except:
            return False
    
    def get_channel_messages(self, channel_id: str, limit: int = 50) -> List[Dict]:
        """Get recent messages from a channel"""
        params = {'limit': min(limit, 100)}  # Discord limit is 100
        return self._make_request('GET', f'{self.base_url}/channels/{channel_id}/messages', params=params)
    
    def get_channel_by_name(self, guild_id: str, channel_name: str) -> Optional[Dict]:
        """Get channel by name in a server"""
        channels = self.get_channels(guild_id)
        for channel in channels:
            if channel['name'].lower() == channel_name.lower().lstrip('#'):
                return channel
        return None
    
    def get_text_channels(self, guild_id: str) -> List[Dict]:
        """Get only text channels from a server"""
        channels = self.get_channels(guild_id)
        return [ch for ch in channels if ch['type'] == 0]  # Type 0 = text channel
    
    def get_channel_info(self, channel_id: str) -> Dict[str, Any]:
        """Get detailed channel information including slowmode (with caching)"""
        # Check cache first
        cache_key = f"channel_{channel_id}"
        current_time = time.time()
        
        if cache_key in self._channel_cache:
            cached_data, timestamp = self._channel_cache[cache_key]
            if current_time - timestamp < self._cache_expiry:
                return cached_data
        
        # Fetch fresh data
        channel_info = self._make_request('GET', f'{self.base_url}/channels/{channel_id}')
        
        # Cache the result
        self._channel_cache[cache_key] = (channel_info, current_time)
        
        return channel_info
    
    def get_slowmode_delay(self, channel_id: str) -> int:
        """Get slowmode delay for a channel in seconds (with caching)"""
        try:
            channel_info = self.get_channel_info(channel_id)
            return channel_info.get('rate_limit_per_user', 0)
        except:
            return 0
    
    def accept_invite(self, invite_code):
        """Accept server invite"""
        # Remove discord.gg/ if present
        if 'discord.gg/' in invite_code:
            invite_code = invite_code.split('discord.gg/')[-1]
        elif 'discord.com/invite/' in invite_code:
            invite_code = invite_code.split('discord.com/invite/')[-1]
        
        url = f"https://discord.com/api/v10/invites/{invite_code}"
        # Add required data payload for accepting invites
        data = {}
        return self._make_request('POST', url, json=data)
    
    def delete_message(self, channel_id, message_id):
        """Delete a message"""
        try:
            response = self.session.delete(f'{self.base_url}/channels/{channel_id}/messages/{message_id}', timeout=10)
            return response.status_code == 204
        except:
            return False
    
    def clear_cache(self):
        """Clear the channel info cache"""
        self._channel_cache.clear()
        logger.info("Channel cache cleared")
