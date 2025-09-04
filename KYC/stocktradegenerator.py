import pandas as pd
import numpy as np
import os
from datetime import date

def generate_trade_log_data():
    """
    Generates a mock daily trade log file inside the project's 'data' folder,
    regardless of where the script is run from.
    """
    # --- Configuration ---
    NUM_TRADES = 100
    CLIENT_IDS = [f"CL{1001 + i}" for i in range(20)]
    STOCKS = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"]
    
    # --- Build a reliable, absolute path to the data directory ---
    # os.path.realpath(__file__) gets the full path to this script
    # os.path.dirname(...) gets the folder this script is in (KYC)
    # os.path.join(..., '..', 'data') goes up one level (to SEBI) and then into 'data'
    script_dir = os.path.dirname(os.path.realpath(__file__))
    DATA_DIR = os.path.join(script_dir, '..', 'data')

    # --- Create data directory if it doesn't exist ---
    os.makedirs(DATA_DIR, exist_ok=True)

    # --- Generate Trade Data ---
    trades = []
    for i in range(NUM_TRADES):
        client_id = np.random.choice(CLIENT_IDS)
        stock = np.random.choice(STOCKS)
        trade_type = np.random.choice(["BUY", "SELL"])
        quantity = np.random.randint(10, 500)
        price = round(np.random.uniform(100, 3000), 2)
        margin_collected = round((quantity * price) * np.random.uniform(0.2, 0.3), 2)
        
        trades.append({
            "trade_id": f"TRD{5001 + i}",
            "client_id": client_id,
            "stock_symbol": stock,
            "trade_type": trade_type,
            "quantity": quantity,
            "price_per_share": price,
            "margin_collected": margin_collected
        })
    
    trade_log_df = pd.DataFrame(trades)
    log_path = os.path.join(DATA_DIR, 'daily_trade_log.csv')
    trade_log_df.to_csv(log_path, index=False)
    print(f"Generated daily trade log at: {log_path}")

if __name__ == "__main__":
    generate_trade_log_data()