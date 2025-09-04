import pandas as pd
import numpy as np
import os
from datetime import date

def generate_suspicious_trade_log():
    """
    Generates a large, mock daily trade log that includes a wide variety of
    intentionally suspicious trading patterns for robust testing.
    """
    print("Generating a large and complex trade log with multiple suspicious patterns...")
    
    # --- Configuration ---
    NUM_NORMAL_TRADES = 5000  # Increased for realism
    CLIENT_IDS = [f"CL{1001 + i}" for i in range(50)] # More clients
    STOCKS = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "BAJFINANCE"]
    PENNY_STOCKS = ["SUZLON", "YESBANK", "IDEA", "GTLINFRA"]
    
    # --- Path Setup ---
    DATA_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'data')
    os.makedirs(DATA_DIR, exist_ok=True)

    # --- Generate a large base of normal trades ---
    trades = []
    for i in range(NUM_NORMAL_TRADES):
        trades.append({
            "trade_id": f"TRD{10001 + i}",
            "client_id": np.random.choice(CLIENT_IDS),
            "stock_symbol": np.random.choice(STOCKS),
            "trade_type": np.random.choice(["BUY", "SELL"]),
            "quantity": np.random.randint(10, 500),
            "price_per_share": round(np.random.uniform(500, 3000), 2)
        })

    # === Plant a Variety of Suspicious Trades ===
    print("Planting suspicious trade patterns into the dataset...")

    # Flag 1: Large Trade Value (> 5 Lakhs)
    trades.append({
        "trade_id": "TRD9001", "client_id": "CL1007", "stock_symbol": "INFY",
        "trade_type": "SELL", "quantity": 300, "price_per_share": 1800.00
    }) # Value = 5,40,000

    # Flag 2: High Volume in a Penny Stock (> 100,000 shares, price < Rs 10)
    trades.append({
        "trade_id": "TRD9002", "client_id": "CL1015", "stock_symbol": "SUZLON",
        "trade_type": "BUY", "quantity": 150000, "price_per_share": 8.75
    })

    # Flag 3: High Frequency Trading (> 50 trades in one stock by one client)
    for i in range(55):
        trades.append({
            "trade_id": f"TRD8001 + {i}", "client_id": "CL1002", "stock_symbol": "YESBANK",
            "trade_type": "BUY", "quantity": 1000, "price_per_share": 15.50
        })

    # Flag 4: Wash Trading (A client trading with themselves to create volume)
    # Simulating by having a client place multiple buy and sell orders for the same illiquid stock.
    wash_client = "CL1025"
    wash_stock = "GTLINFRA"
    for i in range(15):
        trades.append({"trade_id": f"WASH_B_{i}", "client_id": wash_client, "stock_symbol": wash_stock, "trade_type": "BUY", "quantity": 5000, "price_per_share": 1.25})
        trades.append({"trade_id": f"WASH_S_{i}", "client_id": wash_client, "stock_symbol": wash_stock, "trade_type": "SELL", "quantity": 5000, "price_per_share": 1.25})

    # Flag 5: Circular Trading (A small group of clients trading amongst themselves)
    # A trades to B, B trades to C, C trades back to A.
    circular_clients = ["CL1031", "CL1032", "CL1033"]
    circular_stock = "RCOM"
    trades.append({"trade_id": "CIRC_1", "client_id": circular_clients[0], "stock_symbol": circular_stock, "trade_type": "SELL", "quantity": 10000, "price_per_share": 2.10})
    trades.append({"trade_id": "CIRC_2", "client_id": circular_clients[1], "stock_symbol": circular_stock, "trade_type": "SELL", "quantity": 10000, "price_per_share": 2.10})
    trades.append({"trade_id": "CIRC_3", "client_id": circular_clients[2], "stock_symbol": circular_stock, "trade_type": "SELL", "quantity": 10000, "price_per_share": 2.10})

    # Flag 6: Trade Reversal / Loss Booking (Booking a loss for potential tax harvesting or other reasons)
    loss_client_A = "CL1041"
    loss_client_B = "CL1042" # This part is implied, not explicit in the log
    loss_stock = "BAJAJFINSV"
    # Client A buys high...
    trades.append({"trade_id": "LOSS_B", "client_id": loss_client_A, "stock_symbol": loss_stock, "trade_type": "BUY", "quantity": 100, "price_per_share": 1600.00})
    # ...and sells low on the same day.
    trades.append({"trade_id": "LOSS_S", "client_id": loss_client_A, "stock_symbol": loss_stock, "trade_type": "SELL", "quantity": 100, "price_per_share": 1500.00})
    
    # --- Finalize and Save the Dataset ---
    trade_log_df = pd.DataFrame(trades).sample(frac=1).reset_index(drop=True) # Shuffle the trades
    log_path = os.path.join(DATA_DIR, 'suspicious_trade_log.csv')
    trade_log_df.to_csv(log_path, index=False)
    print(f"Successfully generated a large, suspicious trade log at: {log_path}")

if __name__ == "__main__":
    generate_suspicious_trade_log()

