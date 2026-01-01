import gspread
from oauth2client.service_account import ServiceAccountCredentials

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_name(
    "service_account.json", scope
)

client = gspread.authorize(creds)
sheet = client.open_by_key("1N0vkk6BgQTXK39Ce_z-51R64bW5VkQ9GDU2nKKSP-U8").sheet1

print(sheet.get_all_records())