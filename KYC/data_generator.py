import os
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import date, timedelta, datetime
import random
import string
import numpy as np

# --- 1. CONFIGURATION & FIREBASE INITIALIZATION ---
try:
    cred_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'firebase_creds.json')
    cred = credentials.Certificate(cred_path)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Firebase Firestore initialized successfully.")
except Exception as e:
    print(f"❌ FIREBASE INITIALIZATION FAILED: {e}")
    db = None

# --- Configuration for Data Generation ---
NUM_CLIENTS = 100
SIMULATION_DAYS = 180 # The number of past days to simulate data for
TRADES_PER_DAY_PER_CLIENT = 0.5 # Avg trades per client per day

# --- Helper Functions ---
def generate_random_name():
    first_names = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan"]
    last_names = ["Sharma", "Verma", "Gupta", "Singh", "Patel", "Kumar", "Das", "Mehta", "Shah", "Jain"]
    return f"{random.choice(first_names)} {random.choice(last_names)}".upper()

def generate_random_pan():
    return ''.join(random.choices(string.ascii_uppercase, k=5)) + ''.join(random.choices(string.digits, k=4)) + random.choice(string.ascii_uppercase)

def generate_random_dob():
    start_date = date(1960, 1, 1)
    end_date = date(2004, 1, 1)
    return start_date + timedelta(days=random.randrange((end_date - start_date).days))

# --- Main Synthesizer Function ---
def synthesize_historical_data_to_firestore():
    """
    Generates a rich, historical dataset and uploads it to Firestore.
    """
    if not db:
        print("Cannot synthesize data. Firestore is not connected.")
        return

    print(f"\nSynthesizing historical data for {NUM_CLIENTS} clients over {SIMULATION_DAYS} days...")
    
    # --- 1. Plan the Client Onboarding Timeline ---
    all_potential_clients = []
    for i in range(NUM_CLIENTS):
        all_potential_clients.append({
            "client_id": f"CL{1001+i}", "name": generate_random_name(), "pan": generate_random_pan(),
            "onboarding_day": random.randint(1, SIMULATION_DAYS)
        })

    # --- 2. Run the Daily Simulation Loop ---
    print("Running daily simulation to generate historical logs...")
    active_clients = []
    
    # Use a batch to upload data efficiently
    batch = db.batch()
    commit_counter = 0

    for day_ago in range(SIMULATION_DAYS, 0, -1):
        current_date = date.today() - timedelta(days=day_ago)
        current_datetime = datetime.combine(current_date, datetime.min.time())
        
        # Onboard clients scheduled for this day
        for client in all_potential_clients:
            if client["onboarding_day"] == (SIMULATION_DAYS - day_ago + 1):
                active_clients.append(client)
                
                # Add client to the 'clients' collection
                client_ref = db.collection('clients').document(client['client_id'])
                batch.set(client_ref, {
                    'client_id': client['client_id'], 'full_name': client['name'], 'pan_number': client['pan'],
                    'dob': generate_random_dob().isoformat(), 'address': "123, Sample St, Mumbai",
                    'kyc_last_updated': current_date.isoformat(),
                    'kyc_expiry_date': (current_date + timedelta(days=8*365)).isoformat(),
                    'risk_category': 'Medium'
                })
                
                # Add their starting balance
                balance_ref = db.collection('client_balances').document(client['client_id'])
                batch.set(balance_ref, {'balance': round(random.uniform(50000, 200000), 2), 'last_updated': current_datetime})
                commit_counter += 2

        # Generate trades for currently active clients
        if active_clients:
            num_daily_trades = int(len(active_clients) * TRADES_PER_DAY_PER_CLIENT)
            for _ in range(num_daily_trades):
                active_client_id = random.choice(active_clients)['client_id']
                trade_ref = db.collection('trades').document() # Firestore auto-generates ID
                batch.set(trade_ref, {
                    'client_id': active_client_id, 'trade_date': current_datetime,
                    'stock_symbol': random.choice(["RELIANCE", "TCS", "HDFCBANK"]),
                    'trade_type': random.choice(["BUY", "SELL"]),
                    'quantity': random.randint(10, 500),
                    'price_per_share': round(random.uniform(500, 3000), 2)
                })
                commit_counter += 1
        
        # Commit the batch periodically to avoid exceeding limits
        if commit_counter >= 400:
            print(f"  ...committing {commit_counter} operations to Firestore...")
            batch.commit()
            batch = db.batch() # Start a new batch
            commit_counter = 0

    # Final commit for any remaining operations
    if commit_counter > 0:
        print(f"  ...committing final {commit_counter} operations to Firestore...")
        batch.commit()

    print("\n✅ Historical database synthesized and uploaded to Firestore successfully.")

if __name__ == "__main__":
    synthesize_historical_data_to_firestore()
    
