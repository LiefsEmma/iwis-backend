import os
import random
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Use the same models as the app
from app.models import Base, Sensor, WaterReading, WeatherReading, CitizenReport

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/iwis")

def seed_database():
    print(f"Connecting to database for seeding: {DATABASE_URL.split('@')[-1]}")
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        # 1. Create Sensors if they don't exist
        sensors = [
            {"name": "North Shore Auto-Sampler", "sensor_type": "Static Buoy", "lat": -25.725, "lng": 27.855},
            {"name": "Central Basin Buoy", "sensor_type": "Mobile Platform", "lat": -25.735, "lng": 27.865},
        ]

        db_sensors = []
        for s_data in sensors:
            existing = db.query(Sensor).filter(Sensor.name == s_data["name"]).first()
            if not existing:
                s = Sensor(
                    name=s_data["name"],
                    sensor_type=s_data["sensor_type"],
                    latitude=s_data["lat"],
                    longitude=s_data["lng"],
                    is_active=True
                )
                db.add(s)
                db.commit()
                db.refresh(s)
                db_sensors.append(s)
                print(f"Created sensor: {s.name}")
            else:
                db_sensors.append(existing)

        # 2. Generate 30 days of data
        print("Generating 30 days of historical data...")
        start_date = datetime.now() - timedelta(days=30)
        
        for day in range(31):
            current_time = start_date + timedelta(days=day)
            
            for sensor in db_sensors:
                # Water Reading
                wr = WaterReading(
                    sensor_id=sensor.id,
                    recorded_at=current_time,
                    ph=round(random.uniform(6.5, 8.5), 2),
                    temperature_c=round(random.uniform(18.0, 26.0), 1),
                    nitrates_mg_l=round(random.uniform(0.5, 12.0), 2),
                    phosphate_mg_l=round(random.uniform(0.1, 4.0), 2),
                    turbidity_ntu=round(random.uniform(1.0, 45.0), 1),
                    dissolved_oxygen_mg_l=round(random.uniform(3.0, 9.0), 1),
                    latitude=sensor.latitude,
                    longitude=sensor.longitude
                )
                db.add(wr)

            # Weather Reading
            weather = WeatherReading(
                recorded_at=current_time,
                wind_speed_m_s=round(random.uniform(0, 15), 1),
                wind_direction_deg=random.randint(0, 359),
                air_temperature_c=round(random.uniform(15, 30), 1),
                latitude=-25.734,
                longitude=27.858
            )
            db.add(weather)
            
        # 3. Add some reports
        reports = [
            {"title": "Heavy Algal Bloom", "category": "pollution", "severity": "high", "desc": "Significant green coverage near the yacht club."},
            {"title": "Dead Fish Sighted", "category": "wildlife", "severity": "critical", "desc": "Multiple dead fish found near the north shore."},
            {"title": "Illegal Dumping", "category": "pollution", "severity": "high", "desc": "Suspicious liquid being pumped into the dam."}
        ]

        for r_data in reports:
            report = CitizenReport(
                title=r_data["title"],
                category=r_data["category"],
                severity=r_data["severity"],
                description=r_data["desc"],
                reporter_name="System Seeder",
                reporter_role="official",
                report_type="incident",
                latitude=-25.7343 + random.uniform(-0.01, 0.01),
                longitude=27.8587 + random.uniform(-0.01, 0.01),
                status="new"
            )
            db.add(report)

        db.commit()
        print("Database successfully seeded with historical data!")

    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
