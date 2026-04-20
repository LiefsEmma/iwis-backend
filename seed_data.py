import requests
import random
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"
HARTIES_LAT = -25.7343
HARTIES_LNG = 27.8587

def seed_database():
    print("Starting database seed...")

    sensors = [
        {"name": "North Shore Auto-Sampler", "sensor_type": "Water Quality", "latitude": HARTIES_LAT + 0.011, "longitude": HARTIES_LNG - 0.03, "is_active": True},
        {"name": "Central Basin Buoy", "sensor_type": "Multi-parameter", "latitude": HARTIES_LAT - 0.004, "longitude": HARTIES_LNG + 0.006, "is_active": True}
    ]
    
    sensor_ids = []
    for s in sensors:
        res = requests.post(f"{BASE_URL}/sensors", json=s)
        if res.status_code == 201:
            sensor_ids.append(res.json()["id"])
            print(f"Created sensor: {s['name']}")
        else:
            print(f"Failed to create sensor. Is the server running? {res.text}")
            return

    print(f"Generating 30 days of water readings for {len(sensor_ids)} sensors...")
    now = datetime.now()
    
    for sensor_id in sensor_ids:
        # Base values to create a realistic trend
        base_nitrate = 1.2
        base_temp = 22.0
        
        for days_ago in range(30, -1, -1):
            base_nitrate += random.uniform(-0.2, 0.3)
            base_temp += random.uniform(-0.5, 0.6)
            nitrate = max(0.1, min(base_nitrate, 8.0))
            temp = max(10.0, min(base_temp, 35.0))
            
            reading_time = now - timedelta(days=days_ago)
            
            reading = {
                "sensor_id": sensor_id,
                "recorded_at": reading_time.isoformat(),
                "ph": round(random.uniform(6.8, 8.5), 2),
                "temperature_c": round(temp, 1),
                "nitrates_mg_l": round(nitrate, 2),
                "phosphate_mg_l": round(random.uniform(0.1, 4.0), 2),
                "turbidity_ntu": round(random.uniform(5.0, 50.0), 1),
                "dissolved_oxygen_mg_l": round(random.uniform(4.0, 8.0), 2),
                "latitude": HARTIES_LAT,
                "longitude": HARTIES_LNG
            }
            requests.post(f"{BASE_URL}/water-readings", json=reading)
            
    print("Water readings generated.")

    weather = {
        "wind_speed_m_s": round(random.uniform(2.0, 8.0), 1),
        "wind_direction_deg": random.randint(0, 360),
        "air_temperature_c": round(random.uniform(20.0, 32.0), 1),
        "latitude": HARTIES_LAT,
        "longitude": HARTIES_LNG
    }
    requests.post(f"{BASE_URL}/weather-readings", json=weather)
    print("Weather reading generated.")

    reports = [
        {"description": "Thick green algae bloom near the boat club.", "reporter_name": "Lerato K.", "report_type": "citizen-scientist", "latitude": HARTIES_LAT - 0.01, "longitude": HARTIES_LNG + 0.02},
        {"description": "Strong chemical smell and dead fish on the eastern shore.", "reporter_name": "Thabo M.", "report_type": "field-worker", "latitude": HARTIES_LAT + 0.005, "longitude": HARTIES_LNG + 0.015}
    ]
    for r in reports:
        requests.post(f"{BASE_URL}/citizen-reports", json=r)
    print("Citizen reports generated.")

    print("Done!")

if __name__ == "__main__":
    seed_database()
