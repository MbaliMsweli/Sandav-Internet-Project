import requests
import base64
import os
from dotenv import load_dotenv
from datetime import date
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --------------------
# LOAD ENV VARIABLES
# --------------------
load_dotenv()

SMSPORTAL_CLIENT_ID = os.getenv("SMSPORTAL_CLIENT_ID")
SMSPORTAL_API_SECRET = os.getenv("SMSPORTAL_API_SECRET")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")

print("CLIENT_ID:", SMSPORTAL_CLIENT_ID)
print("API_SECRET:", SMSPORTAL_API_SECRET)

if not SMSPORTAL_CLIENT_ID or not SMSPORTAL_API_SECRET:
    raise ValueError("Missing SMSPortal credentials in .env file")

if not GOOGLE_SHEET_ID or not SERVICE_ACCOUNT_FILE:
    raise ValueError("Missing Google Sheets credentials in .env file")

# --------------------
# MANUAL PAYMENT DETAILS
# --------------------
BANK_DETAILS = (
    "Bank: FNB\n"
    "Account Name: Sandav Digital\n"
    "Account Number: 63154953244\n"
    "Account Type: Cheque"
)

HOME_BUSINESS_PAYMENT_LINK = "https://sandavdigital.co.za/Home_internet_payment.html"
APARTMENT_PAYMENT_LINK = "https://sandavdigital.co.za/suspended.html"

# --------------------
# GOOGLE SHEETS AUTH
# --------------------
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_name(
    SERVICE_ACCOUNT_FILE, scope
)
client = gspread.authorize(creds)

sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1
rows = sheet.get_all_records()  # list of dictionaries

# --------------------
# ENCODE SMS CREDENTIALS
# --------------------
credentials = f"{SMSPORTAL_CLIENT_ID}:{SMSPORTAL_API_SECRET}"
encoded_credentials = base64.b64encode(credentials.encode()).decode()

SMS_URL = "https://rest.smsportal.com/v1/bulkmessages"

HEADERS = {
    "Authorization": f"Basic {encoded_credentials}",
    "Content-Type": "application/json"
}

# --------------------
# TODAY'S DATE
# --------------------
today = date.today().isoformat()
print("Sending SMS for date:", today)

# --------------------
# BUILD MESSAGES FROM GOOGLE SHEET
# --------------------
messages = []

for row in rows:
    # ---- DATE FILTER ----
    row_date = str(row.get("PAY DATE", "")).strip()
    if row_date != today:
        continue

    name = str(row.get("CLIENT FULL NAME", "")).strip()
    phone = (
        str(row.get("PHONE NUMBER", ""))
        .strip()
        .replace(" ", "")
        .replace("+", "")
    )
    reference = str(row.get("REFFERENCE", "")).strip()
    amount = str(row.get("MONTHLY FEE", "")).strip()

    # ---- INTERNET TYPE (NORMALISED) ----
    internet_type_raw = str(row.get("INTERNET TYPE", "")).strip().lower()

    if "home" in internet_type_raw or "home/bussiness" in internet_type_raw:
        payment_link = HOME_BUSINESS_PAYMENT_LINK
    elif "apartment" in internet_type_raw or "flat" in internet_type_raw:
        payment_link = APARTMENT_PAYMENT_LINK
    else:
        print(f"Skipping {name} – unknown internet type: {internet_type_raw}")
        continue

    # ---- PHONE VALIDATION ----
    if not phone or not phone.isdigit():
        print(f"Skipping invalid phone number: {phone}")
        continue

    # ---- MESSAGE ----
    message_text = (
        f"Hi {name}, this is a friendly reminder to please pay for your internet service.\n\n"
        f"Payment Reference: {reference}\n\n"
        f"{f'Amount Due: R{amount}\n\n' if amount else ''}"
        "You can make payment using either option below:\n\n"
        "👉 Bank Details:\n"
        f"{BANK_DETAILS}\n\n"
        "👉 Or pay online using this link:\n"
        f"{payment_link}\n\n"
        "Thank you."
    )

    messages.append({
        "destination": phone,
        "content": message_text
    })

if not messages:
    raise ValueError("Google Sheet contains no valid messages for today")

# --------------------
# SEND SMS
# --------------------
payload = {
    "messages": messages,
    "sender_id": "SANDAV"
}

response = requests.post(SMS_URL, headers=HEADERS, json=payload)

print("Status Code:", response.status_code)
print("Response Body:", response.text)


