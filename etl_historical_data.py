import pandas as pd
from sqlalchemy.orm import Session
from app.database import engine, SessionLocal
from app import models
import glob
import os

def run_etl():
    print("Starting ETL process for historical data...")
    db: Session = SessionLocal()
    
    # Check if we already have a lot of data
    count = db.query(models.WaterReading).count()
    if count > 5000:
        print(f"Database already has {count} readings. Skipping ETL.")
        db.close()
        return

    # Find all CSV files in .data/
    csv_files = glob.glob(".data/*.csv")
    
    total_inserted = 0
    for file in csv_files:
        print(f"Processing {file}...")
        try:
            df = pd.read_csv(file)
            
            # Map columns where possible
            if 'date_time' not in df.columns:
                continue
                
            # Filter rows with NaNs in crucial columns if they exist
            if 'pH_Diss_Water' in df.columns:
                df = df.dropna(subset=['pH_Diss_Water'])
                
            readings = []
            for _, row in df.iterrows():
                # Extract values with safe defaults
                ph = row['pH_Diss_Water'] if 'pH_Diss_Water' in df.columns else 7.0
                nitrates = row['NO3_NO2_N_Diss_Water'] if 'NO3_NO2_N_Diss_Water' in df.columns else 1.0
                
                reading = models.WaterReading(
                    sensor_id=1, # Assuming sensor 1 exists
                    recorded_at=pd.to_datetime(row['date_time']),
                    ph=float(ph) if pd.notna(ph) else 7.0,
                    temperature_c=22.0,
                    nitrates_mg_l=float(nitrates) if pd.notna(nitrates) else 1.0,
                    turbidity_ntu=10.0,
                    dissolved_oxygen_mg_l=6.0,
                    latitude=-25.7343,
                    longitude=27.8587
                )
                readings.append(reading)
                
                # Commit in batches of 1000
                if len(readings) >= 1000:
                    db.bulk_save_objects(readings)
                    db.commit()
                    total_inserted += len(readings)
                    readings = []
                    
            if readings:
                db.bulk_save_objects(readings)
                db.commit()
                total_inserted += len(readings)
                
        except Exception as e:
            print(f"Error processing {file}: {e}")
            db.rollback()

    db.close()
    print(f"ETL complete. Inserted {total_inserted} historical records.")

if __name__ == "__main__":
    run_etl()
