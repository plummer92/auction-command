import sqlite3
import requests
import torch
import os
from torchvision import transforms, models
from PIL import Image
from io import BytesIO

# =============================
# CONFIG
# =============================

DB_PATH = "hibid_lots.db"
MODEL_PATH = "models/tool_classifier.pth"
TEMP_DIR = "temp_images"
BATCH_SIZE = 50

DEVICE = torch.device("cpu")  # inference only

CLASS_NAMES = [
    "air_compressor",
    "drill_press",
    "miter_saw",
    "nail_gun",
    "table_saw",
    "welder"
]

# =============================
# MODEL LOAD
# =============================

model = models.resnet18(weights=None)
model.fc = torch.nn.Linear(model.fc.in_features, len(CLASS_NAMES))
model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE))
model.eval()

transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
])

if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

# =============================
# DB CONNECT
# =============================

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
SELECT lot_id, image_url
FROM lots
WHERE predicted_category IS NULL
AND image_url IS NOT NULL
LIMIT ?
""", (BATCH_SIZE,))

rows = cursor.fetchall()

if not rows:
    print("No unclassified lots found.")
    conn.close()
    exit()

print(f"Processing {len(rows)} lots...")

# =============================
# PROCESS LOOP
# =============================

for lot_id, image_url in rows:

    try:
        response = requests.get(image_url, timeout=10)
        img = Image.open(BytesIO(response.content)).convert("RGB")

        input_tensor = transform(img).unsqueeze(0)

        with torch.no_grad():
            outputs = model(input_tensor)
            probs = torch.softmax(outputs, dim=1)
            confidence, predicted = torch.max(probs, 1)

        category = CLASS_NAMES[predicted.item()]
        confidence_score = float(confidence.item()) * 100

        cursor.execute("""
        UPDATE lots
        SET predicted_category = ?,
            classifier_confidence = ?
        WHERE lot_id = ?
        """, (category, confidence_score, lot_id))

        print(f"{lot_id} → {category} ({confidence_score:.2f}%)")

    except Exception as e:
        print(f"Error processing {lot_id}: {e}")

conn.commit()
conn.close()

print("Classification update complete.")
