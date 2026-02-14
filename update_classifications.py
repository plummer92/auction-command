import os
import sqlite3
import requests
import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image
from io import BytesIO
import logging
from datetime import datetime

# -----------------------------
# CONFIG
# -----------------------------

DB_PATH = "/home/theplummer92/auction-command/hibid_lots.db"
MODEL_PATH = "/home/theplummer92/auction-command/models/tool_classifier.pth"
BATCH_SIZE = 50
TEMP_DIR = "/tmp/auction_images"

CLASS_NAMES = [
    "drill_press",
    "table_saw",
    "miter_saw",
    "welder",
    "nail_gun",
    "air_compressor"
]

# -----------------------------
# LOGGING SETUP
# -----------------------------

logging.basicConfig(
    filename="/home/theplummer92/auction-command/logs/inference.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

os.makedirs(TEMP_DIR, exist_ok=True)

# -----------------------------
# LOAD MODEL (CPU MODE)
# -----------------------------

device = torch.device("cpu")

model = models.resnet18(weights=None)
model.fc = nn.Linear(model.fc.in_features, len(CLASS_NAMES))
model.load_state_dict(torch.load(MODEL_PATH, map_location=device))
model.to(device)
model.eval()

# Disable gradient tracking (important for CPU performance)
torch.set_grad_enabled(False)

# -----------------------------
# IMAGE TRANSFORM
# -----------------------------

transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])

# -----------------------------
# DB CONNECTION
# -----------------------------

def get_unclassified_lots(conn):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT lot_id, image_url
        FROM lots
        WHERE predicted_category IS NULL
        AND image_url IS NOT NULL
        LIMIT ?
    """, (BATCH_SIZE,))
    return cursor.fetchall()

def update_lot(conn, lot_id, category, confidence):
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE lots
        SET predicted_category = ?,
            classifier_confidence = ?
        WHERE lot_id = ?
    """, (category, confidence, lot_id))
    conn.commit()

# -----------------------------
# IMAGE DOWNLOAD
# -----------------------------

def download_image(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return Image.open(BytesIO(response.content)).convert("RGB")
    except Exception as e:
        logging.error(f"Image download failed: {url} | {e}")
        return None

# -----------------------------
# INFERENCE
# -----------------------------

def classify_image(image):
    input_tensor = transform(image).unsqueeze(0).to(device)
    outputs = model(input_tensor)
    probabilities = torch.softmax(outputs, dim=1)
    confidence, predicted_idx = torch.max(probabilities, 1)
    return CLASS_NAMES[predicted_idx.item()], confidence.item()

# -----------------------------
# MAIN LOOP
# -----------------------------

def main():
    logging.info("Starting inference cycle")

    conn = sqlite3.connect(DB_PATH)

    while True:
        lots = get_unclassified_lots(conn)

        if not lots:
            logging.info("No more unclassified lots. Exiting.")
            break

        for lot_id, image_url in lots:
            try:
                image = download_image(image_url)

                if image is None:
                    continue

                category, confidence = classify_image(image)

                update_lot(conn, lot_id, category, confidence)

                logging.info(f"Lot {lot_id} classified as {category} ({confidence:.3f})")

            except Exception as e:
                logging.error(f"Failed processing lot {lot_id}: {e}")

    conn.close()
    logging.info("Inference cycle complete")

if __name__ == "__main__":
    main()
