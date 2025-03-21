import requests
import csv
import copy
from collections import defaultdict
import json
import os
from decouple import config
from icecream import ic



URL_GET = "https://uat-synergy.halopsa.com/api/RecurringInvoice/{}"
URL_POST = "https://uat-synergy.halopsa.com/api/RecurringInvoice"
CSV_FILE = "./invoice_updates.csv"
TOKEN = None

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}"
}

def get_token():
    global TOKEN, HEADERS
    auth_endpoint = "https://uat-synergy.halopsa.com/auth/token"
    client_id = config('client_id')
    secret = config('client_secret')

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "halo-app-name": "halo-web-application"
    }
    body = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": secret,
        "scope": "all"
    }
    response = requests.post(auth_endpoint, headers=headers, data=body)
    
    if response.status_code != 200:
        print(f"❌ Failed to retrieve token: {response.status_code}")
        print(response.text)
        return None

    try:
        response_data = response.json()
        print("✅ New token retrieved")
        TOKEN = response_data['access_token']
        HEADERS["Authorization"] = f"Bearer {TOKEN}"
        return TOKEN
    except json.JSONDecodeError:
        print("❌ Failed to decode JSON response")
        print(response.text)
        return None

def read_csv_updates():
    updates_by_invoice = defaultdict(dict)
    with open(CSV_FILE, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            try:
                invoice_id = int(row["invoice_id"])
                line_id = int(row["invoice_line_id"])
                pro_rata = int(row["new_pro_rata_value"])
                updates_by_invoice[invoice_id][line_id] = pro_rata
            except ValueError:
                print(f"⚠️ Skipping invalid row: {row}")
    return updates_by_invoice

def get_invoice(invoice_id):
    url = URL_GET.format(invoice_id)
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ GET failed for invoice {invoice_id}: {response.status_code}")
        print(response.text)
        return None

def update_invoice(invoice_data, updates_for_invoice):
    updated_lines = []

    for line in invoice_data.get("lines", []):
        line_id = line.get("id")
        line_copy = copy.deepcopy(line)

        if line_id in updates_for_invoice:
            updated = False
            for field in ["quantity_licences", "quantity_subscriptions"]:
                for item in line_copy.get(field, []):
                    if item.get("invoice_line_id") == line_id or item.get("id") == line_id:
                        item["pro_rata"] = updates_for_invoice[line_id]
                        updated = True
                        print(f"✅ Updated line {line_id} → pro_rata: {updates_for_invoice[line_id]} in {field}")

        updated_lines.append(line_copy)  # Always include the full line

    payload = [{
        "id": invoice_data["id"],
        "lines": updated_lines
    }]

    print("📤 Sending updated invoice with all lines...")
    response = requests.post(URL_POST, headers=HEADERS, json=payload)
    print(f"🔁 Response [{response.status_code}]")


if __name__ == "__main__":
    get_token()
    updates_by_invoice = read_csv_updates()
    for invoice_id, updates in updates_by_invoice.items():
        print(f"\n🔍 Processing invoice {invoice_id}...")
        invoice_data = get_invoice(invoice_id)
        if invoice_data:
            update_invoice(invoice_data, updates)