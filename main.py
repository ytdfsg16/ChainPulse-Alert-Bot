import os
import json
import requests
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ALCHEMY_KEY = os.getenv("ALCHEMY_API_KEY") or os.getenv("ETHERSCAN_API_KEY")

WALLETS_FILE = "wallets.json"

def load_wallets():
    if os.path.exists(WALLETS_FILE):
        with open(WALLETS_FILE, "r") as f:
            return json.load(f)
    return ["0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"]

def save_wallets(wallets):
    with open(WALLETS_FILE, "w") as f:
        json.dump(wallets, f, indent=4)

WATCHED_WALLETS = load_wallets()

ALCHEMY_URLS = {
    "eth": f"https://eth-mainnet.g.alchemy.com/v2/{ALCHEMY_KEY}",
    "polygon": f"https://polygon-mainnet.g.alchemy.com/v2/{ALCHEMY_KEY}"
}

last_balances = {}

def get_wallet_balance(wallet_address, chain="eth"):
    url = ALCHEMY_URLS.get(chain, ALCHEMY_URLS["eth"])
    payload = {
        "id": 1,
        "jsonrpc": "2.0",
        "method": "eth_getBalance",
        "params": [wallet_address, "latest"]
    }
    headers = {"accept": "application/json", "content-type": "application/json"}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        data = response.json()
        if "result" in data:
            balance_hex = data["result"]
            balance_wei = int(balance_hex, 16)
            return round(balance_wei / 10**18, 4)
    except Exception as e:
        print(f"[!] Error fetching balance: {e}")
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("🔷 Ethereum", callback_data="check_eth"),
            InlineKeyboardButton("🟣 Polygon", callback_data="check_polygon"),
        ],
        [InlineKeyboardButton("📜 View Monitored Wallets", callback_data="list_wallets")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🐳 **Whale Tracker Pro**\n\n"
        "Real-time wallet monitoring active!\n\n"
        "⚙️ **Wallet Management:**\n"
        "• Add Wallet: `/add 0x...`\n"
        "• Remove Wallet: `/remove 0x...`\n\n"
        "Select network for instant scan:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def add_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Please provide a wallet address.\nExample:\n`/add 0xd8dA...`", parse_mode="Markdown")
        return

    address = context.args[0].strip()
    if not address.startswith("0x") or len(address) != 42:
        await update.message.reply_text("❌ Invalid wallet address format.")
        return

    if address in WATCHED_WALLETS:
        await update.message.reply_text("ℹ️ Wallet is already in watchlist.")
        return

    WATCHED_WALLETS.append(address)
    save_wallets(WATCHED_WALLETS)
    await update.message.reply_text(f"✅ **Wallet Added Successfully:**\n`{address}`", parse_mode="Markdown")

async def remove_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Please specify a wallet address to remove.\nExample:\n`/remove 0xd8dA...`", parse_mode="Markdown")
        return

    address = context.args[0].strip()
    if address not in WATCHED_WALLETS:
        await update.message.reply_text("❌ Wallet not found in watchlist.")
        return

    WATCHED_WALLETS.remove(address)
    save_wallets(WATCHED_WALLETS)
    await update.message.reply_text(f"🗑️ **Wallet Removed Successfully:**\n`{address}`", parse_mode="Markdown")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    try:
        if data in ["check_eth", "check_polygon"]:
            chain = "eth" if data == "check_eth" else "polygon"
            chain_name = "Ethereum 🔷" if chain == "eth" else "Polygon 🟣"
            symbol = "ETH" if chain == "eth" else "MATIC"
            
            await query.edit_message_text(f"⏳ Scanning {chain_name} network...")
            
            results = []
            for wallet in WATCHED_WALLETS:
                bal = get_wallet_balance(wallet, chain)
                if bal is not None:
                    results.append(f"👤 `{wallet[:6]}...{wallet[-4:]}`\n💰 Balance: `{bal} {symbol}`")
                else:
                    results.append(f"👤 `{wallet[:6]}...{wallet[-4:]}`\n⚠️ Data fetch failed")
            
            msg = f"📊 **Live Scan Results ({chain_name}):**\n\n" + "\n\n".join(results)
            keyboard = [[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

        elif data == "list_wallets":
            wallets_str = "\n".join([f"• `{w}`" for w in WATCHED_WALLETS])
            msg = f"📋 **Monitored Wallets ({len(WATCHED_WALLETS)}):**\n\n{wallets_str}"
            keyboard = [[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

        elif data == "main_menu":
            keyboard = [
                [
                    InlineKeyboardButton("🔷 Ethereum", callback_data="check_eth"),
                    InlineKeyboardButton("🟣 Polygon", callback_data="check_polygon"),
                ],
                [InlineKeyboardButton("📜 View Monitored Wallets", callback_data="list_wallets")]
            ]
            await query.edit_message_text(
                "🐳 **Whale Tracker Pro**\n\nSelect network for instant scan:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
    except Exception as e:
        print(f"[!] Processing error: {e}")

async def track_wallets_job(context: ContextTypes.DEFAULT_TYPE):
    if not CHAT_ID:
        return

    for wallet in WATCHED_WALLETS:
        try:
            current_bal = get_wallet_balance(wallet, "eth")
            if current_bal is None:
                continue

            key = f"{wallet}_eth"
            if key in last_balances:
                prev_bal = last_balances[key]
                diff = round(current_bal - prev_bal, 4)
                if diff != 0:
                    action = "📈 Buy / Deposit" if diff > 0 else "📉 Sell / Withdraw"
                    msg = (
                        f"🚨 **WHALE ALERT DETECTED!**\n\n"
                        f"👤 Wallet: `{wallet[:6]}...{wallet[-4:]}`\n"
                        f"Action: {action}\n"
                        f"Amount: `{abs(diff)} ETH`\n"
                        f"New Balance: `{current_bal} ETH`"
                    )
                    await context.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
            
            last_balances[key] = current_bal
        except Exception as e:
            print(f"[!] Background job error: {e}")

def main():
    print("[+] Whale Tracker Pro with English UI is running...")
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_wallet))
    app.add_handler(CommandHandler("remove", remove_wallet))
    app.add_handler(CallbackQueryHandler(button_click))
    
    if app.job_queue:
        app.job_queue.run_repeating(
            track_wallets_job, 
            interval=180, 
            first=10,
            job_kwargs={"misfire_grace_time": 60}
        )

    app.run_polling()

if __name__ == "__main__":
    main()
