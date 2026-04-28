import os
import random
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import CitizenReport

DATABASE_URL = "postgresql://neondb_owner:npg_6m2ZMSxpTgCj@ep-noisy-bird-anlte678-pooler.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def repopulate():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()

    dummy_reports = [
        {"title": "Heavy Algal Bloom", "cat": "pollution", "sev": "high", "desc": "Large green mass floating near the West shore. Strong odour detected."},
        {"title": "Dead Fish Sighting", "cat": "wildlife", "sev": "critical", "desc": "Observed approximately 20 dead tilapia near the North sampling station."},
        {"title": "Hyacinth Overgrowth", "cat": "hyacinth", "sev": "medium", "desc": "Dense hyacinth mats blocking the secondary canal entrance."},
        {"title": "Broken Monitoring Buoy", "cat": "infrastructure", "sev": "medium", "desc": "Central buoy seems to be tilting and taking on water."},
        {"title": "Illegal Waste Disposal", "cat": "pollution", "sev": "high", "desc": "Commercial vehicle seen dumping unknown liquids into the basin."},
        {"title": "Rare Bird Nesting", "cat": "wildlife", "sev": "low", "desc": "African Fish Eagle nesting pair spotted in the southern reeds."},
        {"title": "Oily Sheen on Water", "cat": "pollution", "sev": "medium", "desc": "Thin rainbow film visible on the surface near the yacht club."},
        {"title": "Litter Accumulation", "cat": "other", "sev": "low", "desc": "Significant plastic waste build-up after the recent heavy rains."},
    ]

    try:
        print("Populating reports...")
        for i, data in enumerate(dummy_reports):
            # Stagger the timestamps over the last 48 hours
            time_offset = timedelta(hours=i * 4)
            created_at = datetime.now() - time_offset

            report = CitizenReport(
                title=data["title"],
                description=data["desc"],
                category=data["cat"],
                severity=data["sev"],
                reporter_name="Auto-Generator",
                reporter_role="official",
                report_type="observation",
                latitude=-25.7343 + random.uniform(-0.01, 0.01),
                longitude=27.8587 + random.uniform(-0.01, 0.01),
                status="new",
                created_at=created_at
            )
            db.add(report)
        
        db.commit()
        print(f"Successfully added {len(dummy_reports)} dummy reports.")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    repopulate()
