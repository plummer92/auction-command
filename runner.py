import subprocess
import time

print("=== AUCTION AUTONOMOUS CYCLE START ===")

# Run scraper
subprocess.run(["python", "scraper_v8.py"])

# Run lifecycle
subprocess.run(["python", "lifecycle_manager.py"])

# Run velocity computation
subprocess.run(["python", "compute_velocity.py"])

# Run category stats (rarity)
subprocess.run(["python", "compute_category_stats.py"])

# Run edge scoring
subprocess.run(["python", "compute_edge_score.py"])

# Run alerts
subprocess.run(["python", "edge_alerts.py"])

print("=== CYCLE COMPLETE ===")
