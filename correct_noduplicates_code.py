import requests
import base64
import os
from dotenv import load_dotenv
from datetime import date, datetime, timedelta
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

if not SMSPORTAL_CLIENT_ID or not SMSPORTAL_API_SECRET:
    raise ValueError("Missing SMSPortal credentials")

if not GOOGLE_SHEET_ID or not SERVICE_ACCOUNT_FILE:
    raise ValueError("Missing Google Sheets credentials")

# --------------------
# PAYMENT DETAILS
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

spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)

sheet = spreadsheet.worksheet("January 2026")

rows = sheet.get_all_records()


# Column indexes
sms_sent_col = sheet.find("SMS SENT").col
sms_sent_at_col = sheet.find("SMS SENT AT").col
block_sms_col = sheet.find("BLOCK SMS SENT").col

# --------------------
# SMS AUTH
# --------------------
credentials = f"{SMSPORTAL_CLIENT_ID}:{SMSPORTAL_API_SECRET}"
encoded_credentials = base64.b64encode(credentials.encode()).decode()

SMS_URL = "https://rest.smsportal.com/v1/bulkmessages"

HEADERS = {
    "Authorization": f"Basic {encoded_credentials}",
    "Content-Type": "application/json"
}

# --------------------
# TODAY
# --------------------
today = date.today()
print("Running SMS automation for:", today)

messages = []

# --------------------
# PROCESS ROWS
# --------------------
for idx, row in enumerate(rows, start=2):

    name = str(row.get("CLIENT FULL NAME", "")).strip()
    phone = (
        str(row.get("PHONE NUMBER", ""))
        .strip()
        .replace(" ", "")
        .replace("+", "")
    )

    if not phone or not phone.isdigit():
        continue

    internet_type = str(row.get("INTERNET TYPE", "")).strip().lower()
    monthly_fee = str(row.get("MONTHLY FEE", "")).strip()
    reference = str(row.get("REFFERENCE", "")).strip()

    paid_status = str(row.get("PAID/UNPAID", "")).strip().upper()
    sms_sent = str(row.get("SMS SENT", "")).strip().upper()
    block_sms_sent = str(row.get("BLOCK SMS SENT", "")).strip().upper()
    sms_sent_at = str(row.get("SMS SENT AT", "")).strip()

    # --------------------
    # DETERMINE PAYMENT LINK
    # --------------------
    if "home" in internet_type or "business" in internet_type:
        payment_link = HOME_BUSINESS_PAYMENT_LINK
    elif "apartment" in internet_type or "flat" in internet_type:
        payment_link = APARTMENT_PAYMENT_LINK
    else:
        continue

    # --------------------
    # BLOCK SMS (AFTER 2 DAYS)
    # --------------------
    if sms_sent_at and paid_status == "UNPAID" and block_sms_sent != "YES":
        try:
            sent_date = datetime.strptime(sms_sent_at, "%Y-%m-%d").date()
            if today >= sent_date + timedelta(days=2):

                block_message = (
                    f"Hi {name},\n\n"
                    "Your internet service has been blocked due to non-payment.\n\n"
                    f"Monthly Fee: R{monthly_fee}\n"
                    f"Payment Reference: {reference}\n\n"
                    "Please make payment using the details below:\n\n"
                    f"{BANK_DETAILS}\n\n"
                    "Or pay online using this link:\n"
                    f"{payment_link}\n\n"
                    "Once payment is received, your internet will be restored. Please ignore this if you've paid already\n\n"
                    "Thank you."
                )

                messages.append({
                    "destination": phone,
                    "content": block_message
                })

                sheet.update_cell(idx, block_sms_col, "YES")
                continue
        except ValueError:
            pass

    # --------------------
    # FIRST REMINDER (PAY DATE)
    # --------------------
    pay_date = str(row.get("PAY DATE", "")).strip()
    if pay_date != today.isoformat():
        continue

    # 🔹 DO NOT MESSAGE PAID CLIENTS
    if paid_status != "UNPAID":
        continue

    if sms_sent == "YES":
        continue

    reminder_message = (
        f"Hi {name}, this is a friendly reminder to please pay for your internet service.\n\n"
        f"Payment Reference: {reference}\n"
        f"Amount Due: R{monthly_fee}\n\n"
        "You can make payment using either option below:\n\n"
        f"{BANK_DETAILS}\n\n"
        "Or pay online using this link:\n"
        f"{payment_link}\n\n"
        "Thank you."
    )

    messages.append({
        "destination": phone,
        "content": reminder_message
    })

    sheet.update_cell(idx, sms_sent_col, "YES")
    sheet.update_cell(idx, sms_sent_at_col, today.isoformat())

# --------------------
# SEND SMS
# --------------------
if not messages:
    print("No SMS to send today.")
    exit()

payload = {
    "messages": messages,
    "sender_id": "SANDAV"
}

response = requests.post(SMS_URL, headers=HEADERS, json=payload)

print("Status Code:", response.status_code)
print("Response Body:", response.text)
