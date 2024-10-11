import logging
import alpaca_trade_api as tradeapi
import time
import numpy as np

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("trading_bot.log"),
        logging.StreamHandler()
    ]
)

# Alpaca API configuration
API_KEY = 'PKK46FOQILEK4ALAF8IU'
API_SECRET = 'e7WOD5V3MweUClo3jhxS4Fg6xndbfqm0r6pET1cY'
BASE_URL = 'https://paper-api.alpaca.markets'

api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

# Global variables
last_price = None
current_position = 0  # Track how many shares we own of the current stock
upward_changes = 0  # Track consecutive upward price changes
last_upward_change = None  # Store last upward change magnitude
last_downward_change = None  # Store last downward change magnitude
consecutive_upward_ticks = 0  # Track consecutive upward price changes with no downward tick
stock_symbol = 'GOOGL'  # Default stock symbol to trade. Change this to switch stocks

def get_account_info():
    """Get the account buying power and balance."""
    try:
        account = api.get_account()
        buying_power = float(account.regt_buying_power)  # Regular Buying Power
        cash = float(account.cash)  # Cash balance
        logging.info(f"Account buying power: ${buying_power:.2f}")
        logging.info(f"Account cash balance: ${cash:.2f}")
        return buying_power, cash
    except tradeapi.rest.APIError as e:
        logging.error(f"Error getting account info: {e}")
        return None, None

def sell_all_stock():
    """Sell all owned stock of the current symbol."""
    try:
        positions = api.list_positions()
        for pos in positions:
            if pos.symbol == stock_symbol:
                qty_to_sell = pos.qty
                api.submit_order(
                    symbol=stock_symbol,
                    qty=qty_to_sell,
                    side='sell',
                    type='market',
                    time_in_force='gtc'
                )
                logging.info(f"Sold {qty_to_sell} shares of {stock_symbol}.")
                return
    except tradeapi.rest.APIError as e:
        logging.error(f"Error placing sell order: {e}")

def buy_stock():
    """Buy the current stock with available buying power."""
    buying_power, cash = get_account_info()  # Get real-time buying power and cash

    if buying_power is None or cash <= 0:
        logging.warning("No available buying power or cash.")
        return

    try:
        # Get the latest price of the stock
        stock_price = api.get_latest_trade(stock_symbol).price
        num_shares_to_buy = buying_power / stock_price  # Use all buying power

        # Make sure we only buy whole shares
        num_shares_to_buy = int(np.floor(num_shares_to_buy))
        logging.info(f"Buying {num_shares_to_buy} shares of {stock_symbol} at ${stock_price:.2f}")

        if num_shares_to_buy > 0:
            api.submit_order(
                symbol=stock_symbol,
                qty=num_shares_to_buy,
                side='buy',
                type='market',
                time_in_force='gtc'
            )
            logging.info(f"Bought {num_shares_to_buy} shares of {stock_symbol}.")
        else:
            logging.warning(f"Not enough buying power to buy even 1 share of {stock_symbol}.")
    except tradeapi.rest.APIError as e:
        logging.error(f"Error placing buy order: {e}")

def run_trading_strategy():
    """Main trading strategy execution."""
    global last_price, current_position, upward_changes, last_upward_change, last_downward_change, consecutive_upward_ticks

    buying_power, _ = get_account_info()

    if buying_power is None:
        return

    try:
        # Get the most recent trade for the current stock symbol
        current_trade = api.get_latest_trade(stock_symbol)
        current_price = current_trade.price
        logging.info(f"Current {stock_symbol} price: ${current_price:.2f}")

        # If the price is going up
        if last_price is None or current_price > last_price:
            if current_position == 0:  # Only buy if we don't currently own shares
                consecutive_upward_ticks += 1
                logging.info(f"Price has gone up, consecutive upward changes: {consecutive_upward_ticks}")

                # Buy after 7 consecutive upward ticks
                if consecutive_upward_ticks == 7:
                    logging.info("Seven consecutive upward price changes, buying with all buying power.")
                    buy_stock()
                    current_position = 1  # We now own the stock
                    consecutive_upward_ticks = 0  # Reset consecutive upward tick counter
                    last_upward_change = current_price - last_price  # Track the most recent upward change

                # **NEW CONDITION**: Do NOT buy if the upward change is more than twice the previous upward or downward change
                elif last_upward_change is not None and (current_price - last_price) > 2 * last_upward_change:
                    logging.info("Upward change is more than twice the size of the previous upward change, not buying.")
                elif last_downward_change is not None and (current_price - last_price) > 2 * last_downward_change:
                    logging.info("Upward change is more than twice the size of the previous downward change, not buying.")

            else:
                logging.info("Price is increasing, holding position.")
                last_upward_change = current_price - last_price  # Update the upward change

        # If the price is going down
        elif last_price is not None and current_price < last_price:
            logging.info(f"Price has decreased, resetting consecutive upward changes.")
            if current_position > 0:  # If we own shares, sell them
                logging.info("Selling all shares as price is decreasing.")
                sell_all_stock()
                current_position = 0  # We no longer own any shares
            consecutive_upward_ticks = 0  # Reset the consecutive upward ticks
            last_downward_change = last_price - current_price  # Track the most recent downward change
            last_upward_change = None  # Reset the upward change tracker

        # If the price is stable
        elif last_price is not None and current_price == last_price:
            logging.info(f"{stock_symbol} price is stable, holding position.")

        # Update last price with the current price
        last_price = current_price

        # Sleep for 0.5 seconds between each operation
        time.sleep(0.5)

    except tradeapi.rest.APIError as e:
        logging.error(f"Error in trading strategy: {e}")

def start_trading():
    """Start trading with initial position check (sell all if we own the stock)."""
    logging.info("Starting Alpaca trading bot...")

    # First, sell all current stock if any
    sell_all_stock()

    # Sleep for 0.5 seconds after sell operation
    time.sleep(0.5)

    # Start the trading strategy
    while True:
        run_trading_strategy()

if __name__ == "__main__":
    # Initial sell of all stock before starting the bot
    sell_all_stock()
    
    # Start trading
    start_trading()
