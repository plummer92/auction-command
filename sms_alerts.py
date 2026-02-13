import sqlite3
from twilio.rest import Client

DB = "hibid_lots.db"

# Twilio credentials
ACCOUNT_SID = "YOUR_SID"
AUTH_TOKEN = "YOUR_TOKEN"
FROM_NUMBER = "YOUR_TWILIO_NUMBER"
TO_NUMBER = "YOUR_PHONE_NUMBER"

ALERT_THRESHOLD = 60

def send_sms(body):
    client = Client(ACCOUNT_SID, AUTH_TOKEN)
    client.messages.create(
        body=body,
        from_=FROM_NUMBER,
        to=TO_NUMBER
    )

conn = sqlite3.connect(DB)
cursor = conn.cursor()

cursor.execute("""
SELECT lot_id, title, edge_score
FROM lots
WHERE status='pending'
AND edge_score > ?
ORDER BY edge_score DESC
LIMIT 3;
""", (ALERT_THRESHOLD,))

rows = cursor.fetchall()

for lot_id, title, score in rows:
    message = f"🔥 High Edge Deal\nLot: {lot_id}\nScore: {round(score,1)}\n{title[:80]}"
    send_sms(message)

conn.close()
print("SMS alerts processed.")
