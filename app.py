import os
import shutil
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Assuming 'KYC' is a folder in the same directory as this app.py
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
    get_expiring_kyc_from_db
)

app = FastAPI(
    title="KYC & Compliance API",
    description="An API for handling client KYC, compliance checks, and reporting.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class NotifyClientRequest(BaseModel):
    client_id: str

def remove_file(path: str) -> None:
    """Utility function to remove a file from /tmp, used in background tasks."""
    try:
        if os.path.exists(path):
            os.remove(path)
            print(f"Successfully removed temporary file: {path}")
    except Exception as e:
        print(f"Error removing file {path}: {e}")

@app.on_event("startup")
async def startup_event():
    """Initializes the database connection when the API starts."""
    print("Setting up database connection...")
    setup_database()
    print("Database connection established.")

@app.post('/api/kyc/onboard', tags=["KYC"])
async def onboard_client(
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    selfie: UploadFile = File(...),
    pan: UploadFile = File(...),
    aadhaar_front: UploadFile = File(...),
    aadhaar_back: UploadFile = File(...)
):
    # CRITICAL FIX: Save temporary files to /tmp directory
    temp_dir = "/tmp"
    selfie_path = os.path.join(temp_dir, f"selfie_{selfie.filename}")
    pan_path = os.path.join(temp_dir, f"pan_{pan.filename}")
    aadhaar_front_path = os.path.join(temp_dir, f"aadhaar_front_{aadhaar_front.filename}")
    aadhaar_back_path = os.path.join(temp_dir, f"aadhaar_back_{aadhaar_back.filename}")
    
    temp_files = [selfie_path, pan_path, aadhaar_front_path, aadhaar_back_path]
    
    try:
        with open(selfie_path, "wb") as buffer: shutil.copyfileobj(selfie.file, buffer)
        with open(pan_path, "wb") as buffer: shutil.copyfileobj(pan.file, buffer)
        with open(aadhaar_front_path, "wb") as buffer: shutil.copyfileobj(aadhaar_front.file, buffer)
        with open(aadhaar_back_path, "wb") as buffer: shutil.copyfileobj(aadhaar_back.file, buffer)

        result = process_local_kyc(selfie_path, pan_path, aadhaar_front_path, aadhaar_back_path, name)

        if result.get("status") == "success":
            kyc_data = result["data"]
            log_kyc_to_database(kyc_data)
            return {"status": "success", "data": kyc_data}
        else:
            raise HTTPException(status_code=400, detail=result)
            
    finally:
        for path in temp_files:
            background_tasks.add_task(remove_file, path)

@app.post('/api/compliance/check-funds', tags=["Compliance"])
async def client_funds_check_endpoint(
    background_tasks: BackgroundTasks,
    bank_statement: UploadFile = File(...)
):
    # CRITICAL FIX: Save temporary file to /tmp directory
    bank_path = os.path.join("/tmp", f"bank_{bank_statement.filename}")
    try:
        with open(bank_path, "wb") as buffer:
            shutil.copyfileobj(bank_statement.file, buffer)
        result = check_client_funds_from_db(bank_path)
        return result
    finally:
        background_tasks.add_task(remove_file, bank_path)

@app.get('/api/reports/generate-margin-report', tags=["Reports"])
async def generate_margin_report_endpoint():
    report_path, error = generate_margin_report_from_db()
    if error:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {error}")
    return FileResponse(path=report_path, filename=os.path.basename(report_path), background=BackgroundTasks([lambda: remove_file(report_path)]))

@app.get('/api/surveillance/run-check', tags=["Surveillance"])
async def run_surveillance_endpoint():
    result, error = run_surveillance_checks_from_db()
    if error:
        raise HTTPException(status_code=500, detail=f"Surveillance check failed: {error}")
    pdf_path, pdf_error = generate_suspicious_trade_pdf(result.get("flagged_trades", []))
    if pdf_error:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {pdf_error}")
    return FileResponse(path=pdf_path, filename=os.path.basename(pdf_path), background=BackgroundTasks([lambda: remove_file(pdf_path)]))

@app.get('/api/compliance/run-quarterly-settlement', tags=["Compliance"])
async def run_qs_endpoint():
    result, error = run_quarterly_settlement_check()
    if error:
        raise HTTPException(status_code=500, detail=f"Quarterly settlement check failed: {error}")
    pdf_path, pdf_error = generate_qs_report_pdf(result.get("settlement_due_clients", []))
    if pdf_error:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {pdf_error}")
    return FileResponse(path=pdf_path, filename=os.path.basename(pdf_path), background=BackgroundTasks([lambda: remove_file(pdf_path)]))

@app.get('/api/kyc/expiring', tags=["KYC"])
async def get_expiring_kyc():
    result, error = get_expiring_kyc_from_db()
    if error:
        raise HTTPException(status_code=500, detail=f"Database error: {error}")
    return result

@app.post('/api/clients/notify', tags=["Clients"])
async def notify_client_endpoint(request: NotifyClientRequest):
    result, error = send_kyc_notification(request.client_id)
    if error:
        raise HTTPException(status_code=404, detail=error)
    return result

if __name__ == '__main__':
    # Corrected uvicorn command for local running
    uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=True)