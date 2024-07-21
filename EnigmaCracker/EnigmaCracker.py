import subprocess
import sys
import os
import platform
import requests
import logging
import time
import json
from dotenv import load_dotenv
from bip_utils import (
    Bip39MnemonicGenerator,
    Bip39SeedGenerator,
    Bip44,
    Bip44Coins,
    Bip44Changes,
    Bip39WordsNum,
)

# Constants
LOG_FILE_NAME = "enigmacracker.log"
ENV_FILE_NAME = "EnigmaCracker.env"
WALLETS_FILE_NAME = "wallets_with_balance.txt"
CACHE_FILE_NAME = "cache.json"
RATE_LIMIT_DELAY = 5  # seconds between requests to avoid spamming

# Global counter for the number of wallets scanned
wallets_scanned = 0

# Get the absolute path of the directory where the script is located
directory = os.path.dirname(os.path.abspath(__file__))
# Initialize directory paths
log_file_path = os.path.join(directory, LOG_FILE_NAME)
env_file_path = os.path.join(directory, ENV_FILE_NAME)
wallets_file_path = os.path.join(directory, WALLETS_FILE_NAME)
cache_file_path = os.path.join(directory, CACHE_FILE_NAME)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file_path),  # Log to a file
        logging.StreamHandler(sys.stdout),  # Log to standard output
    ],
)

# Load environment variables from .env file
load_dotenv(env_file_path)

# Environment variable validation
required_env_vars = ["ETHERSCAN_API_KEY", "TRONGRID_API_KEY"]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise EnvironmentError(f"Missing environment variables: {', '.join(missing_vars)}")

# Cache for API responses
cache = {}

def load_cache():
    global cache
    if os.path.exists(cache_file_path):
        with open(cache_file_path, "r") as cache_file:
            cache = json.load(cache_file)

def save_cache():
    with open(cache_file_path, "w") as cache_file:
        json.dump(cache, cache_file)

# Check if we've set the environment variable indicating we're in the correct CMD
if os.environ.get("RUNNING_IN_NEW_CMD") != "TRUE":
    os.environ["RUNNING_IN_NEW_CMD"] = "TRUE"

    os_type = platform.system()
    if os_type == "Windows":
        subprocess.run(f'start cmd.exe /K python "{__file__}"', shell=True)
    elif os_type == "Linux":
        subprocess.run(f"gnome-terminal -- python3 {__file__}", shell=True)
    sys.exit()

def update_cmd_title():
    if platform.system() == "Windows":
        os.system(f"title EnigmaCracker.py - Wallets Scanned: {wallets_scanned}")

def bip():
    return Bip39MnemonicGenerator().FromWordsNumber(Bip39WordsNum.WORDS_NUM_12)

def bip44_ETH_wallet_from_seed(seed):
    seed_bytes = Bip39SeedGenerator(seed).Generate()
    bip44_mst_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.ETHEREUM)
    bip44_acc_ctx = bip44_mst_ctx.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
    return bip44_acc_ctx.PublicKey().ToAddress()

def bip44_BTC_seed_to_address(seed):
    seed_bytes = Bip39SeedGenerator(seed).Generate()
    bip44_mst_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.BITCOIN)
    bip44_acc_ctx = bip44_mst_ctx.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
    return bip44_acc_ctx.PublicKey().ToAddress()

def bip44_LTC_seed_to_address(seed):
    seed_bytes = Bip39SeedGenerator(seed).Generate()
    bip44_mst_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.LITECOIN)
    bip44_acc_ctx = bip44_mst_ctx.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
    return bip44_acc_ctx.PublicKey().ToAddress()

def bip44_TRX_seed_to_address(seed):
    seed_bytes = Bip39SeedGenerator(seed).Generate()
    bip44_mst_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.TRON)
    bip44_acc_ctx = bip44_mst_ctx.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
    return bip44_acc_ctx.PublicKey().ToAddress()

def check_ETH_balance(address, etherscan_api_key, retries=3, delay=5):
    api_url = f"https://api.etherscan.io/api?module=account&action=balance&address={address}&tag=latest&apikey={etherscan_api_key}"
    for attempt in range(retries):
        try:
            response = requests.get(api_url)
            data = response.json()
            if data["status"] == "1":
                balance = int(data["result"]) / 1e18
                return balance
            else:
                logging.error("Error getting balance: %s", data["message"])
                return 0
        except Exception as e:
            if attempt < retries - 1:
                logging.error(f"Error checking balance, retrying in {delay} seconds: {str(e)}")
                time.sleep(delay)
            else:
                logging.error("Error checking balance: %s", str(e))
                return 0

def check_BTC_balance(address, retries=3, delay=5):
    for attempt in range(retries):
        try:
            response = requests.get(f"https://blockchain.info/balance?active={address}")
            data = response.json()
            # Handle possible variations in response format
            if address in data:
                balance = data[address].get("final_balance", 0)
                return balance / 1e8
            else:
                logging.error(f"Unexpected response format for BTC address: {address}")
                return 0
        except Exception as e:
            if attempt < retries - 1:
                logging.error(f"Error checking balance, retrying in {delay} seconds: {str(e)}")
                time.sleep(delay)
            else:
                logging.error("Error checking balance: %s", str(e))
                return 0

def check_LTC_balance(address, retries=3, delay=5):
    for attempt in range(retries):
        try:
            response = requests.get(f"https://blockchain.info/rawaddr/{address}")
            data = response.json()
            # Handle possible variations in response format
            balance = data.get("final_balance", 0)
            return balance / 1e8
        except Exception as e:
            if attempt < retries - 1:
                logging.error(f"Error checking balance, retrying in {delay} seconds: {str(e)}")
                time.sleep(delay)
            else:
                logging.error("Error checking balance: %s", str(e))
                return 0

def check_TRX_balance(address, retries=3, delay=5):
    api_url = f"https://api.trongrid.io/v1/accounts/{address}"
    for attempt in range(retries):
        try:
            response = requests.get(api_url)
            data = response.json()
            if "data" in data and len(data["data"]) > 0:
                balance = data["data"][0].get("balance", 0)
                return balance / 1e6
            else:
                logging.error(f"No balance data found for TRX address: {address}")
                return 0
        except Exception as e:
            if attempt < retries - 1:
                logging.error(f"Error checking balance, retrying in {delay} seconds: {str(e)}")
                time.sleep(delay)
            else:
                logging.error("Error checking balance: %s", str(e))
                return 0

def check_USDT_balance(address, retries=3, delay=5):
    return check_ETH_balance(address, os.getenv("ETHERSCAN_API_KEY"), retries, delay)

def write_to_file(seed, BTC_address, BTC_balance, ETH_address, ETH_balance, LTC_address, LTC_balance, TRX_address, TRX_balance, USDT_balance):
    with open(wallets_file_path, "a") as f:
        log_message = (
            f"Seed: {seed}\n"
            f"BTC Address: {BTC_address}\nBalance: {BTC_balance} BTC\n\n"
            f"ETH Address: {ETH_address}\nBalance: {ETH_balance} ETH\n\n"
            f"LTC Address: {LTC_address}\nBalance: {LTC_balance} LTC\n\n"
            f"TRX Address: {TRX_address}\nBalance: {TRX_balance} TRX\n\n"
            f"USDT Address: {ETH_address}\nBalance: {USDT_balance} USDT\n\n"
        )
        f.write(log_message)
        logging.info(f"Written to file: {log_message}")

def main():
    global wallets_scanned
    load_cache()
    
    try:
        while True:
            seed = bip()
            BTC_address = bip44_BTC_seed_to_address(seed)
            BTC_balance = check_BTC_balance(BTC_address)
            ETH_address = bip44_ETH_wallet_from_seed(seed)
            ETH_balance = check_ETH_balance(ETH_address, os.getenv("ETHERSCAN_API_KEY"))
            LTC_address = bip44_LTC_seed_to_address(seed)
            LTC_balance = check_LTC_balance(LTC_address)
            TRX_address = bip44_TRX_seed_to_address(seed)
            TRX_balance = check_TRX_balance(TRX_address)
            USDT_balance = check_USDT_balance(ETH_address)

            logging.info(f"Seed: {seed}")
            logging.info(f"BTC Address: {BTC_address}, Balance: {BTC_balance} BTC")
            logging.info(f"ETH Address: {ETH_address}, Balance: {ETH_balance} ETH")
            logging.info(f"LTC Address: {LTC_address}, Balance: {LTC_balance} LTC")
            logging.info(f"TRX Address: {TRX_address}, Balance: {TRX_balance} TRX")
            logging.info(f"USDT Address: {ETH_address}, Balance: {USDT_balance} USDT")
            logging.info("")

            wallets_scanned += 1
            update_cmd_title()

            if BTC_balance > 0 or ETH_balance > 0 or LTC_balance > 0 or TRX_balance > 0 or USDT_balance > 0:
                logging.info("(!) Wallet with balance found!")
                write_to_file(seed, BTC_address, BTC_balance, ETH_address, ETH_balance, LTC_address, LTC_balance, TRX_address, TRX_balance, USDT_balance)

            save_cache()
            time.sleep(RATE_LIMIT_DELAY)

    except KeyboardInterrupt:
        logging.info("Program interrupted by user. Exiting...")

if __name__ == "__main__":
    main()
