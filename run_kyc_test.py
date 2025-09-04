import requests
import os

# --- CONFIGURATION ---
API_ENDPOINT = "http://127.0.0.1:5000/api/kyc/onboard"
TEST_FOLDER = "test"

def run_onboarding_test(user_id, user_name):
    """
    Simulates a frontend application by sending a user's documents
    from the 'test' folder to the KYC onboarding API.
    """
    print(f"--- Starting KYC Onboarding Test for User: {user_id} ({user_name}) ---")

    # --- 1. Define the file paths based on the user ID ---
    file_paths = {
        'selfie': os.path.join(TEST_FOLDER, f"{user_id}_selfie.jpg"),
        'pan': os.path.join(TEST_FOLDER, f"{user_id}_pan.jpg"),
        'aadhaar_front': os.path.join(TEST_FOLDER, f"{user_id}_aadhaar_front.jpg"),
        'aadhaar_back': os.path.join(TEST_FOLDER, f"{user_id}_aadhaar_back.jpg")
    }

    # --- 2. Check if all files exist before proceeding ---
    for key, path in file_paths.items():
        if not os.path.exists(path):
            print(f"❌ ERROR: Missing file for '{key}'. Expected at: {path}")
            return

    try:
        # --- 3. Prepare the multipart/form-data request ---
        # The 'files' dictionary will hold the open file objects
        files_to_upload = {
            key: (os.path.basename(path), open(path, 'rb'), 'image/jpeg')
            for key, path in file_paths.items()
        }
        
        # The 'data' dictionary holds the text fields
        form_data = {
            "name": user_name
        }

        # --- 4. Send the request to the API ---
        print("Sending documents to the API endpoint...")
        response = requests.post(API_ENDPOINT, files=files_to_upload, data=form_data)
        
        # --- 5. Print the result ---
        print("\n" + "="*40)
        print(f"API Response (Status Code: {response.status_code}):")
        print("="*40)
        print(response.json())

    except requests.exceptions.ConnectionError:
        print("\n❌ CONNECTION ERROR: Could not connect to the API.")
        print("Please make sure your 'app.py' server is running.")
    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {e}")
    finally:
        # --- 6. Clean up: Close all the opened files ---
        for file_obj in files_to_upload.values():
            file_obj[1].close()

if __name__ == "__main__":
    # Define the user you want to test
    test_user_id = "u1"
    test_user_name = "Abhyuday Rastogi" # The name must match the documents
    
    run_onboarding_test(test_user_id, test_user_name)


    
