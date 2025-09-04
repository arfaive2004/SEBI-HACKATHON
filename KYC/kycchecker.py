import os
from datetime import date, timedelta, datetime
import pandas as pd
import numpy as np
from PIL import Image
import json
import cv2
import pytesseract
import re
from deepface import DeepFace
from cryptography.fernet import Fernet
from fpdf import FPDF
import random
import firebase_admin
from firebase_admin import credentials, firestore

# --- 1. CONFIGURATION & FIREBASE INITIALIZATION ---
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
ENCRYPTION_KEY = Fernet.generate_key() # In a real app, store this key securely!
cipher_suite = Fernet(ENCRYPTION_KEY)

# Initialize Firebase using your service account key
try:
    cred_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'firebase_creds.json')
    cred = credentials.Certificate(cred_path)
    # This check prevents a crash if the script is reloaded (e.g., by Flask's debugger)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase Firestore initialized successfully.")
except Exception as e:
    print(f"❌ FIREBASE INITIALIZATION FAILED: {e}")
    print("Please ensure 'firebase_creds.json' is in your main project folder (SEBI/).")
    db = None

# --- 2. DATABASE FUNCTIONS (REWRITTEN FOR FIRESTORE) ---
def setup_database():
    """Confirms that the Firestore connection is active."""
    if db: print("Firestore connection is active. No setup needed for schemaless DB.")
    else: print("Firestore connection is not available.")

def log_kyc_to_database(kyc_data):
    """Logs verified KYC data and synthesizes a dynamic profile in Firestore."""
    if not db: return

    # Generate a new unique Client ID by counting existing clients
    clients_ref = db.collection('clients')
    client_count = len(list(clients_ref.stream()))
    new_client_id = f"CL{1001 + client_count}"

    today_iso = date.today().isoformat()
    expiry_iso = (date.today() + timedelta(days=8*365)).isoformat()
    
    client_doc_data = {
        'client_id': new_client_id,
        'full_name': kyc_data.get("Name", "N/A"),
        'pan_number': kyc_data.get("PAN Number", "N/A"),
        'dob': kyc_data.get("Date of Birth"),
        'address': kyc_data.get("Address", "N/A"),
        'kyc_last_updated': today_iso,
        'kyc_expiry_date': expiry_iso,
        'risk_category': 'Medium'
    }
    
    # Use a batch to write all data atomically (all succeed or all fail)
    batch = db.batch()
    
    client_ref = clients_ref.document(new_client_id)
    batch.set(client_ref, client_doc_data)
    
    balance_ref = db.collection('client_balances').document(new_client_id)
    batch.set(balance_ref, {
        'balance': round(random.uniform(50000, 200000), 2),
        'last_updated': firestore.SERVER_TIMESTAMP
    })
    
    batch.commit()
    print(f"\n✅ KYC for {kyc_data.get('Name')} logged to Firestore. Client ID: {new_client_id}")

# --- 3. LOCAL KYC PROCESSING ENGINE (Unchanged) ---
def process_local_kyc(selfie_path, pan_path, aadhaar_front_path, aadhaar_back_path, user_name_input):
    # This entire function and its helpers remain the same as they operate before the database.
    try:
        face_result = DeepFace.verify(img1_path=selfie_path, img2_path=aadhaar_front_path, model_name="VGG-Face", enforce_detection=False)
        if not face_result.get("verified", False): return {"status": "failed", "reason": "Face verification failed."}
    except Exception as e: return {"status": "failed", "reason": f"DeepFace error: {e}"}
    aadhaar_text = extract_text_from_image(aadhaar_front_path)
    extracted_name = find_name_on_aadhaar(aadhaar_text)
    if not extracted_name or user_name_input.lower() != extracted_name.lower(): return {"status": "failed", "reason": f"Name verification failed."}
    pan_text = extract_text_from_image(pan_path)
    aadhaar_back_text = extract_text_from_image(aadhaar_back_path)
    pan_details = parse_other_details(pan_text)
    aadhaar_front_details = parse_other_details(aadhaar_text)
    aadhaar_back_details = parse_other_details(aadhaar_back_text)
    final_data = {
        "Name": user_name_input.upper(), "Date of Birth": aadhaar_front_details["Date of Birth"] or pan_details["Date of Birth"],
        "PAN Number": pan_details["PAN Number"], "Address": aadhaar_back_details["Address"],
        "PAN Number (Masked)": mask_number(pan_details["PAN Number"])
    }
    return {"status": "success", "data": final_data}

# --- Helper functions for local processing (Unchanged) ---
def extract_text_from_image(image_path):
    if not os.path.exists(image_path): return ""
    image = cv2.imread(image_path); gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    thresh = cv2.threshold(resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    return pytesseract.image_to_string(thresh, config='--oem 3 --psm 6')

def find_name_on_aadhaar(raw_text):
    name_pattern = r"\b[A-Z]{2,}\s[A-Z\s]+\b"; potential_names = re.findall(name_pattern, raw_text)
    filtered_names = [name.strip() for name in potential_names if "GOVERNMENT" not in name and "INDIA" not in name]
    return filtered_names[0] if filtered_names else None

def parse_other_details(raw_text):
    details = {"Date of Birth": None, "PAN Number": None, "Address": None}
    pan_match = re.search(r"([A-Z]{5}[0-9]{4}[A-Z]{1})", raw_text)
    if pan_match: details["PAN Number"] = pan_match.group(0)
    dob_match = re.search(r"(\d{2}/\d{2}/\d{4})", raw_text)
    if dob_match: details["Date of Birth"] = dob_match.group(0)
    addr_match = re.search(r"(Address|addres)[\s\S]*?(\d{6})", raw_text, re.IGNORECASE)
    if addr_match: details["Address"] = addr_match.group(0).replace("\n", " ").strip()
    return details

def mask_number(number, visible_digits=4):
    if number is None or len(number) <= visible_digits: return number
    return "X" * (len(number) - visible_digits) + number[-visible_digits:]

# --- 4. DATABASE-DRIVEN COMPLIANCE FUNCTIONS (REWRITTEN FOR FIRESTORE) ---
def check_client_funds_from_db(bank_statement_path):
    """Compares client funds from Firestore with the bank statement balance."""
    if not db: return {"status": "ERROR", "reason": "Firestore not connected."}
    try:
        balances_ref = db.collection('client_balances').stream()
        total_required_funds = sum(doc.to_dict().get('balance', 0) for doc in balances_ref if doc.to_dict().get('balance', 0) > 0)
        bank_df = pd.read_csv(bank_statement_path)
        actual_bank_balance = bank_df['balance'].iloc[0]
        if actual_bank_balance >= total_required_funds:
            return {"status": "PASS", "surplus": f"{actual_bank_balance - total_required_funds:,.2f}"}
        else:
            return {"status": "FAIL", "shortfall": f"{total_required_funds - actual_bank_balance:,.2f}"}
    except Exception as e:
        return {"status": "ERROR", "reason": str(e)}

def get_expiring_kyc_from_db():
    """Queries Firestore to find clients with KYC expiring soon."""
    if not db: return None, "Firestore not connected."
    try:
        today_iso = date.today().isoformat()
        thirty_days_from_now_iso = (date.today() + timedelta(days=30)).isoformat()
        expiring_clients_query = db.collection('clients').where('kyc_expiry_date', '>=', today_iso).where('kyc_expiry_date', '<=', thirty_days_from_now_iso).stream()
        expiring_list = [doc.to_dict() for doc in expiring_clients_query]
        return {"expiring_clients": expiring_list}, None
    except Exception as e:
        return None, str(e)

def send_kyc_notification(client_id):
    """Simulates sending a KYC renewal notification by fetching data from Firestore."""
    if not db: return None, "Firestore not connected."
    try:
        client_ref = db.collection('clients').document(client_id)
        client = client_ref.get()
        if client.exists:
            client_name = client.to_dict().get('full_name', 'N/A')
            print(f"--- SIMULATING NOTIFICATION to {client_name} (ID: {client_id}) ---")
            return {"status": "success", "message": f"Notification sent to {client_name}."}, None
        else:
            return None, f"Client with ID '{client_id}' not found."
    except Exception as e:
        return None, str(e)

# (Other complex functions like reports and surveillance would also be refactored)
# For now, here are the placeholders showing they would connect to Firestore
def generate_margin_report_from_db():
    """
    Generates a Daily Margin Report by querying the Firestore 'trades' collection
    for all trades that occurred on the current day.
    """
    if not db:
        return None, "Firestore not connected."
    try:
        # --- Step 1: Query Firestore for Today's Trades ---
        today = date.today()
        start_of_day = datetime.combine(today, datetime.min.time())
        end_of_day = datetime.combine(today, datetime.max.time())

        # Create a query to get all documents from the 'trades' collection for the current day
        trades_query = db.collection('trades').where('trade_date', '>=', start_of_day).where('trade_date', '<=', end_of_day).stream()
        
        # Convert the Firestore documents into a list of dictionaries
        trades_list = [trade.to_dict() for trade in trades_query]
        
        if not trades_list:
            return None, "No trades found for today in the Firestore database."

        # Convert the list into a Pandas DataFrame for easy calculation
        trade_df = pd.DataFrame(trades_list)

        # --- Step 2: Perform Calculations ---
        trade_df['total_trade_value'] = trade_df['quantity'] * trade_df['price_per_share']
        
        # Assume a flat 20% margin requirement for this example
        trade_df['margin_required'] = trade_df['total_trade_value'] * 0.20
        
        # In a real system, margin_collected would also be in the DB. We'll simulate it.
        trade_df['margin_collected'] = trade_df['margin_required'] * np.random.uniform(0.95, 1.2, size=len(trade_df))
        trade_df['margin_collected'] = trade_df['margin_collected'].round(2)

        # Check if collected margin meets the requirement
        trade_df['margin_status'] = np.where(
            trade_df['margin_collected'] >= trade_df['margin_required'], 
            'OK', 
            'SHORTFALL'
        )

        # --- Step 3: Format and Save the Report ---
        report_columns = [
            'client_id', 'stock_symbol', 'trade_type', 'quantity', 
            'price_per_share', 'total_trade_value', 'margin_required', 
            'margin_collected', 'margin_status'
        ]
        # Ensure all required columns exist before trying to select them
        report_df = trade_df.reindex(columns=report_columns, fill_value='N/A')

        report_filename = f"Margin_Report_{today.strftime('%d-%m-%Y')}.csv"
        report_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'data', report_filename)
        
        report_df.to_csv(report_path, index=False)
        
        return report_path, None

    except Exception as e:
        return None, str(e)

def run_surveillance_checks_from_db():
    """
    Runs surveillance checks by querying the Firestore 'trades' collection for today's trades.
    """
    if not db: return None, "Firestore not connected."
    try:
        # Helper function to get today's trades
        def get_trades_for_today():
            today = date.today()
            start_of_day = datetime.combine(today, datetime.min.time())
            end_of_day = datetime.combine(today, datetime.max.time())
            trades_query = db.collection('trades').where('trade_date', '>=', start_of_day).where('trade_date', '<=', end_of_day).stream()
            return pd.DataFrame([trade.to_dict() for trade in trades_query])

        df = get_trades_for_today()
        if df.empty:
            return {"status": "success", "flagged_trades": []}, None

        flagged_trades = []
        df['trade_value'] = df['quantity'] * df['price_per_share']

        # --- Run All Surveillance Rules ---
        # Rule 1: Large Trade Value
        large_trades = df[df['trade_value'] > 500000]
        for _, row in large_trades.iterrows():
             flagged_trades.append({"client_id": row['client_id'], "stock_symbol": row['stock_symbol'], "reason": "Large Trade Value"})
        
        # (Your other surveillance rules would be added here in the same way)

        unique_flags = [dict(t) for t in {tuple(d.items()) for d in flagged_trades}]
        return {"status": "success", "flagged_trades": unique_flags}, None
    except Exception as e:
        return None, str(e)

def generate_suspicious_trade_pdf(flagged_trades):
    """
    Takes a list of flagged trades and generates a formatted PDF report.
    This function does not need to change as it only formats data.
    """
    try:
        pdf = FPDF()
        pdf.add_page()

        # Report Header
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, 'Suspicious Activity Report', 0, 1, 'C')
        pdf.set_font("Arial", '', 10)
        pdf.cell(0, 10, f"Date: {date.today().strftime('%d-%m-%Y')}", 0, 1, 'C')
        pdf.ln(10)

        # Report Body
        if not flagged_trades:
            pdf.set_font("Arial", '', 12)
            pdf.cell(0, 10, "No suspicious activities were detected.", 0, 1, 'C')
        else:
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(40, 10, 'Client ID', 1)
            pdf.cell(40, 10, 'Stock Symbol', 1)
            pdf.cell(0, 10, 'Reason for Flag', 1)
            pdf.ln()
            pdf.set_font("Arial", '', 10)
            for trade in flagged_trades:
                pdf.cell(40, 10, str(trade.get("client_id", "N/A")), 1)
                pdf.cell(40, 10, str(trade.get("stock_symbol", "N/A")), 1)
                pdf.multi_cell(0, 10, str(trade.get("reason", "N/A")), 1)

        # Save the PDF
        report_filename = f"Suspicious_Activity_Report_{date.today().strftime('%d-%m-%Y')}.pdf"
        report_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'data', report_filename)
        pdf.output(report_path)
        
        return report_path, None
    except Exception as e:
        return None, str(e)

def run_quarterly_settlement_check():
    """
    Identifies clients from Firestore whose funds are idle for more than 90 days.
    """
    if not db: return None, "Firestore not connected."
    try:
        ninety_days_ago = datetime.now() - timedelta(days=90)
        settlement_due_clients = []
        
        # Get all clients with a positive balance
        balances_ref = db.collection('client_balances').where('balance', '>', 0).stream()
        
        for bal_doc in balances_ref:
            client_id = bal_doc.id
            balance = bal_doc.to_dict().get('balance', 0)
            
            # For each client, find their most recent trade
            trades_query = db.collection('trades').where('client_id', '==', client_id).order_by('trade_date', direction=firestore.Query.DESCENDING).limit(1).stream()
            last_trade = next(trades_query, None)
            
            # Check if the last trade was more than 90 days ago
            if last_trade and last_trade.to_dict()['trade_date'] < ninety_days_ago:
                client_doc = db.collection('clients').document(client_id).get()
                if client_doc.exists:
                    settlement_due_clients.append({
                        "client_id": client_id,
                        "full_name": client_doc.to_dict().get('full_name'),
                        "balance": balance,
                        "days_since_last_trade": (datetime.now() - last_trade.to_dict()['trade_date']).days
                    })
        
        return {"status": "success", "settlement_due_clients": settlement_due_clients}, None
    except Exception as e:
        return None, str(e)

def generate_qs_report_pdf(settlement_due_clients):
    """
    Takes a list of clients due for settlement and generates a formatted PDF report.
    """
    try:
        pdf = FPDF()
        pdf.add_page()

        # Report Header
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, 'Quarterly Settlement Report for Payout', 0, 1, 'C')
        pdf.set_font("Arial", '', 10)
        pdf.cell(0, 10, f"Report Date: {date.today().strftime('%d-%m-%Y')}", 0, 1, 'C')
        pdf.ln(10)

        # Report Body
        if not settlement_due_clients:
            pdf.set_font("Arial", '', 12)
            pdf.cell(0, 10, "No clients are due for quarterly settlement at this time.", 0, 1, 'C')
        else:
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(30, 10, 'Client ID', 1)
            pdf.cell(70, 10, 'Client Name', 1)
            pdf.cell(40, 10, 'Balance to Settle', 1)
            pdf.cell(0, 10, 'Days Idle', 1)
            pdf.ln()
            pdf.set_font("Arial", '', 10)
            for client in settlement_due_clients:
                pdf.cell(30, 10, str(client.get("client_id", "N/A")), 1)
                pdf.cell(70, 10, str(client.get("full_name", "N/A")), 1)
                pdf.cell(40, 10, f"Rs. {client.get('balance', 0):,.2f}", 1)
                pdf.cell(0, 10, str(int(client.get("days_since_last_trade", 0))), 1)
                pdf.ln()

        # Save the PDF
        report_filename = f"Quarterly_Settlement_Report_{date.today().strftime('%d-%m-%Y')}.pdf"
        report_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'data', report_filename)
        pdf.output(report_path)
        
        return report_path, None
    except Exception as e:
        return None, str(e)



# (Other functions like generate reports, run surveillance would be similarly refactored)
# Placeholder for other functions




