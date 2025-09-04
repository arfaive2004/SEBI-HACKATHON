from flask import Flask, request, jsonify, send_file, after_this_request
from flask_cors import CORS
import os
from datetime import date, timedelta

# --- 1. Import your Firestore-powered functions from the KYC subfolder ---
# This list is updated to match the final functions in your kycchecker.py
from KYC.kycchecker import (
    setup_database,
    log_kyc_to_database,
    process_local_kyc,
    check_client_funds_from_db,
    generate_margin_report_from_db,
    run_surveillance_checks_from_db,
    generate_suspicious_trade_pdf,
    run_quarterly_settlement_check,
    generate_qs_report_pdf,
    send_kyc_notification,
    get_expiring_kyc_from_db # <-- New function for this endpoint
)

# --- 2. SETUP ---
app = Flask(__name__)
CORS(app)
# DB_PATH is no longer needed here as Firestore connection is managed in kycchecker.py

# --- 3. API ENDPOINTS (Updated for Firestore Logic) ---

@app.route('/api/kyc/onboard', methods=['POST'])
def onboard_client():
    """API endpoint for the local KYC onboarding process."""
    files = request.files
    form_data = request.form
    
    if 'name' not in form_data:
        return jsonify({"error": "Missing 'name' in the request body."}), 400
    if not all(key in files for key in ['selfie', 'pan', 'aadhaar_front', 'aadhaar_back']):
        return jsonify({"error": "Missing one or more required image files."}), 400

    user_name = form_data['name']
    
    # Save temporary files for processing
    selfie_path = "temp_selfie.jpg"; files['selfie'].save(selfie_path)
    pan_path = "temp_pan.jpg"; files['pan'].save(pan_path)
    aadhaar_front_path = "temp_aadhaar_front.jpg"; files['aadhaar_front'].save(aadhaar_front_path)
    aadhaar_back_path = "temp_aadhaar_back.jpg"; files['aadhaar_back'].save(aadhaar_back_path)
    
    result = process_local_kyc(
        selfie_path, pan_path, aadhaar_front_path, aadhaar_back_path, user_name
    )

    os.remove(selfie_path); os.remove(pan_path); os.remove(aadhaar_front_path); os.remove(aadhaar_back_path)

    if result.get("status") == "success":
        kyc_data = result["data"]
        # Log the successful verification to Firestore
        log_kyc_to_database(kyc_data)
        return jsonify({"status": "success", "data": kyc_data}), 200
    else:
        return jsonify(result), 400

# --- DATABASE-DRIVEN COMPLIANCE ENDPOINTS ---

@app.route('/api/compliance/check-funds', methods=['POST'])
def client_funds_check_endpoint():
    """API endpoint for client funds check. Reads balances from Firestore."""
    if 'bank_statement' not in request.files:
        return jsonify({"error": "Missing 'bank_statement' file."}), 400

    bank_path = "temp_bank.csv"; request.files['bank_statement'].save(bank_path)
    result = check_client_funds_from_db(bank_path)
    os.remove(bank_path)

    return jsonify(result)

@app.route('/api/reports/generate-margin-report', methods=['GET'])
def generate_margin_report_endpoint():
    """API endpoint to generate the Daily Margin Report from Firestore."""
    report_path, error = generate_margin_report_from_db()
    if error:
        return jsonify({"error": f"Failed to generate report: {error}"}), 500
    
    @after_this_request
    def cleanup(response):
        try: os.remove(report_path)
        except Exception as e: print(f"Error removing file: {e}")
        return response

    return send_file(report_path, as_attachment=True)

@app.route('/api/surveillance/run-check', methods=['GET'])
def run_surveillance_endpoint():
    """API endpoint to run surveillance checks on Firestore and return a PDF."""
    result, error = run_surveillance_checks_from_db()
    if error:
        return jsonify({"status": "error", "reason": error}), 500
    
    pdf_path, pdf_error = generate_suspicious_trade_pdf(result.get("flagged_trades", []))
    if pdf_error:
        return jsonify({"status": "error", "reason": f"Failed to generate PDF: {pdf_error}"}), 500
    
    @after_this_request
    def cleanup(response):
        try: os.remove(pdf_path)
        except Exception as e: print(f"Error removing PDF file: {e}")
        return response

    return send_file(pdf_path, as_attachment=True)

@app.route('/api/compliance/run-quarterly-settlement', methods=['GET'])
def run_qs_endpoint():
    """API endpoint to run the quarterly settlement check and return a PDF."""
    result, error = run_quarterly_settlement_check()
    if error:
        return jsonify({"status": "error", "reason": error}), 500
    
    pdf_path, pdf_error = generate_qs_report_pdf(result.get("settlement_due_clients", []))
    if pdf_error:
        return jsonify({"status": "error", "reason": f"Failed to generate PDF: {pdf_error}"}), 500
    
    @after_this_request
    def cleanup(response):
        try: os.remove(pdf_path)
        except Exception as e: print(f"Error removing PDF file: {e}")
        return response

    return send_file(pdf_path, as_attachment=True)

@app.route('/api/kyc/expiring', methods=['GET'])
def get_expiring_kyc():
    """API endpoint to get a list of clients from Firestore with expiring KYC."""
    result, error = get_expiring_kyc_from_db()
    if error:
        return jsonify({"error": f"Database error: {error}"}), 500
    return jsonify(result)

@app.route('/api/clients/notify', methods=['POST'])
def notify_client_endpoint():
    """API endpoint to trigger a KYC renewal notification."""
    data = request.get_json()
    if not data or 'client_id' not in data:
        return jsonify({"error": "Missing 'client_id'."}), 400
    
    result, error = send_kyc_notification(data['client_id'])
    if error:
        return jsonify({"status": "error", "reason": error}), 404
    
    return jsonify(result)

if __name__ == '__main__':
    setup_database()
    app.run(debug=True, port=5000)

