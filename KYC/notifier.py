import sqlite3
from datetime import date, timedelta
import os

# --- 1. CONFIGURATION ---
# Define the path to the database, relative to this script's location.
# '../' goes up one level from KYC to SEBI, then into 'data'.
DB_PATH = os.path.join('..', 'data', 'broker_clients.db')

def check_for_expiring_kyc():
    """
    Checks the database for clients whose KYC is expiring soon.
    """
    notification_days = 60  # Set how many days in advance you want the warning

    print(f"--- Checking for KYC records expiring in the next {notification_days} days ---")
    
    # Check if the database file actually exists before trying to connect
    if not os.path.exists(DB_PATH):
        print(f"❌ Error: The database file was not found at the expected location: {DB_PATH}")
        print("Please make sure you have run the main API server at least once to create it.")
        return

    try:
        # Connect to the SQLite database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        today = date.today()
        notification_period_end = today + timedelta(days=notification_days)
        
        # SQL query to find clients expiring within the date range
        cursor.execute('''
            SELECT full_name, pan_number, kyc_expiry_date 
            FROM clients 
            WHERE kyc_expiry_date BETWEEN ? AND ?
            ORDER BY kyc_expiry_date ASC
        ''', (today, notification_period_end))
        
        expiring_clients = cursor.fetchall()
        conn.close()
        
        if not expiring_clients:
            print("\n✅ No clients have KYC expiring in the notification window.")
        else:
            print(f"\n🔔 WARNING: {len(expiring_clients)} CLIENT(S) NEED KYC RENEWAL 🔔\n")
            for client in expiring_clients:
                full_name = client[0]
                pan = client[1]
                expiry_date = client[2]
                
                # Calculate days remaining
                days_left = (date.fromisoformat(expiry_date) - today).days
                
                print(f"  Client: {full_name}")
                print(f"  PAN: {pan}")
                print(f"  Expires on: {expiry_date} (in {days_left} days)\n")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    check_for_expiring_kyc()

