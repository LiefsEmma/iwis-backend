from typing import Any, Dict, List, Optional
import json
import os
import re
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import cast, Date, func

from . import models, schemas
from .database import Base, engine, get_db

import pandas as pd


app = FastAPI(title="IWIS Backend")

# PERMISSIVE CORS FOR PRODUCTION
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

def _feature(feature_id: int, latitude: float, longitude: float, properties: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "Feature",
        "id": feature_id,
        "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
        "properties": properties,
    }

def calculate_wqi(reading: models.WaterReading) -> float:
    ph_score = 100 - abs(reading.ph - 7.0) * 20
    nitrate_score = max(0, 100 - reading.nitrates_mg_l * 10)
    do_score = min(100, max(0, (reading.dissolved_oxygen_mg_l - 2.0) * 20))
    turb_score = max(0, 100 - (reading.turbidity_ntu - 5.0) * 2)
    
    wqi = (ph_score * 0.2) + (nitrate_score * 0.3) + (do_score * 0.3) + (turb_score * 0.2)
    return round(max(0, min(100, wqi)), 2)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/")
def read_root() -> Dict[str, str]:
    return {"status": "online", "message": "IWIS API is live"}


@app.get("/health")
def healthcheck() -> Dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.post("/sensors", response_model=schemas.SensorRead, status_code=201)
def create_sensor(payload: schemas.SensorCreate, db: Session = Depends(get_db)) -> schemas.SensorRead:
    sensor = models.Sensor(**payload.model_dump())
    db.add(sensor)
    db.commit()
    db.refresh(sensor)
    return sensor


@app.get("/sensors", response_model=List[schemas.SensorRead])
def list_sensors(db: Session = Depends(get_db)) -> List[schemas.SensorRead]:
    return db.query(models.Sensor).order_by(models.Sensor.id.asc()).all()


@app.post("/water-readings", response_model=schemas.WaterReadingRead, status_code=201)
def create_water_reading(
    payload: schemas.WaterReadingCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> schemas.WaterReadingRead:
    water_reading = models.WaterReading(**payload.model_dump())
    db.add(water_reading)
    db.commit()
    db.refresh(water_reading)
    
    if water_reading.nitrates_mg_l > 5.0:
        severity = "high" if water_reading.nitrates_mg_l > 10.0 else "medium"
        alert = models.Alert(
            reading_id=water_reading.id,
            alert_type="Nitrate Level Breach",
            severity=severity,
            threshold_val=water_reading.nitrates_mg_l,
            resolved=False
        )
        db.add(alert)
        db.commit()
        
        background_tasks.add_task(manager.broadcast, json.dumps({
            "type": "new_alert", 
            "data": schemas.AlertRead.model_validate(alert).model_dump(mode='json')
        }))

    background_tasks.add_task(manager.broadcast, json.dumps({
        "type": "new_reading", 
        "data": schemas.WaterReadingRead.model_validate(water_reading).model_dump(mode='json')
    }))
    
    return water_reading


@app.get("/water-readings", response_model=List[schemas.WaterReadingRead])
def list_water_readings(
    sensor_id: Optional[int] = None,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> List[schemas.WaterReadingRead]:
    query = db.query(models.WaterReading)
    if sensor_id:
        query = query.filter(models.WaterReading.sensor_id == sensor_id)
    return query.order_by(models.WaterReading.recorded_at.desc()).limit(limit).all()


@app.post("/citizen-reports", response_model=schemas.CitizenReportRead, status_code=201)
def create_citizen_report(
    payload: schemas.CitizenReportCreate,
    db: Session = Depends(get_db),
) -> schemas.CitizenReportRead:
    report = models.CitizenReport(**payload.model_dump())
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@app.get("/citizen-reports", response_model=List[schemas.CitizenReportRead])
def list_citizen_reports(
    status: Optional[str] = None,
    reporter_role: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> List[schemas.CitizenReportRead]:
    query = db.query(models.CitizenReport)
    if status: query = query.filter(models.CitizenReport.status == status)
    if reporter_role: query = query.filter(models.CitizenReport.reporter_role == reporter_role)
    if category: query = query.filter(models.CitizenReport.category == category)
    return query.order_by(models.CitizenReport.created_at.desc()).limit(limit).all()


@app.get("/map/sensors")
def sensors_geojson(db: Session = Depends(get_db)) -> Dict[str, Any]:
    sensors = db.query(models.Sensor).all()
    features = []
    for sensor in sensors:
        latest = db.query(models.WaterReading).filter(models.WaterReading.sensor_id == sensor.id).order_by(models.WaterReading.recorded_at.desc()).first()
        properties = {"name": sensor.name, "is_active": sensor.is_active}
        if latest:
            properties["latest_readings"] = {
                "ph": latest.ph, "nitrate": latest.nitrates_mg_l, "temperature": latest.temperature_c, "dissolvedOxygen": latest.dissolved_oxygen_mg_l
            }
        features.append(_feature(sensor.id, sensor.latitude, sensor.longitude, properties))
    return {"type": "FeatureCollection", "features": features}


@app.get("/map/citizen-reports")
def reports_geojson(db: Session = Depends(get_db)) -> Dict[str, Any]:
    reports = db.query(models.CitizenReport).all()
    features = []
    for r in reports:
        features.append(_feature(r.id, r.latitude, r.longitude, {
            "title": r.title, "description": r.description, "category": r.category, "severity": r.severity, "created_at": r.created_at.isoformat()
        }))
    return {"type": "FeatureCollection", "features": features}


@app.get("/analysis/trends")
def get_wqi_trends(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    readings = db.query(models.WaterReading).order_by(models.WaterReading.recorded_at.desc()).limit(1000).all()
    if not readings: return []
    df = pd.DataFrame([{"date": r.recorded_at.date(), "wqi": calculate_wqi(r)} for r in readings])
    trends = df.groupby("date")["wqi"].mean().round(2).reset_index()
    trends["date"] = trends["date"].apply(lambda x: x.isoformat())
    return trends.to_dict(orient="records")


@app.get("/analysis/correlations")
def get_realtime_correlations(db: Session = Depends(get_db)) -> Dict[str, Any]:
    readings = db.query(models.WaterReading).limit(1000).all()
    if len(readings) < 2: raise HTTPException(status_code=404, detail="Not enough data")
    data = [{"ph": r.ph, "temp": r.temperature_c, "nitrate": r.nitrates_mg_l, "do": r.dissolved_oxygen_mg_l, "turbidity": r.turbidity_ntu} for r in readings]
    df = pd.DataFrame(data)
    return {
        "correlations": df.corr().fillna(0).round(3).to_dict(),
        "statistics": df.describe().round(2).to_dict(),
        "sample_size": len(df)
    }

@app.get("/analysis/hotspots")
def get_pollution_hotspots(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    high_pollution_readings = db.query(models.WaterReading).filter((models.WaterReading.nitrates_mg_l > 4.0) | (models.WaterReading.phosphate_mg_l > 1.5)).limit(100).all()
    return [{"id": f"hotspot-{r.id}", "lat": r.latitude, "lng": r.longitude, "intensity": "high" if r.nitrates_mg_l > 8.0 else "medium", "radiusMeters": 400 + (r.nitrates_mg_l * 20)} for r in high_pollution_readings]

@app.get("/analysis/wqi-summary")
def get_wqi_summary(db: Session = Depends(get_db)) -> Dict[str, Any]:
    latest = db.query(models.WaterReading).order_by(models.WaterReading.recorded_at.desc()).limit(50).all()
    if not latest: return {"current_wqi": 0, "status": "No data"}
    wqi_vals = [calculate_wqi(r) for r in latest]
    avg = sum(wqi_vals) / len(wqi_vals)
    status = "Excellent"
    if avg < 50: status = "Poor"
    elif avg < 70: status = "Fair"
    elif avg < 90: status = "Good"
    return {"current_wqi": round(avg, 1), "status": status}

@app.get("/alerts", response_model=List[schemas.AlertRead])
def list_alerts(db: Session = Depends(get_db)) -> List[schemas.AlertRead]:
    return db.query(models.Alert).order_by(models.Alert.created_at.desc()).limit(50).all()

@app.put("/alerts/{alert_id}/status", response_model=schemas.AlertRead)
def update_alert_status(alert_id: int, payload: schemas.AlertUpdate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
    if not alert: raise HTTPException(status_code=404, detail="Alert not found")
    alert.resolved = payload.resolved
    db.commit()
    db.refresh(alert)
    background_tasks.add_task(manager.broadcast, json.dumps({"type": "update_alert", "data": schemas.AlertRead.model_validate(alert).model_dump(mode='json')}))
    return alert

@app.post("/chat", response_model=schemas.ChatResponse)
def chatbot_interaction(payload: schemas.ChatRequest, db: Session = Depends(get_db)):
    msg = payload.message.lower()
    
    # DATA SNAPSHOT (Context for the bot)
    latest = db.query(models.WaterReading).order_by(models.WaterReading.recorded_at.desc()).first()
    wqi = get_wqi_summary(db)
    active_alerts = db.query(models.Alert).filter(models.Alert.resolved == False).all()
    report_count = db.query(models.CitizenReport).count()
    sensor_count = db.query(models.Sensor).count()
    pollution_hotspots = get_pollution_hotspots(db)

    # 1. CORE STATUS & WQI
    if any(k in msg for k in ["status", "how is", "condition", "wqi", "health"]):
        res = f"The overall health of Hartbeespoort Dam is currently rated as '{wqi['status']}' with a Water Quality Index of {wqi['current_wqi']}/100. "
        if active_alerts:
            res += f"I have detected {len(active_alerts)} active security breaches that require immediate attention."
        else:
            res += "All monitored parameters are currently within safe operational limits."
        return {"bot_response": res}

    # 2. SAFETY & SWIMMING
    if any(k in msg for k in ["swim", "safe", "contact", "danger"]):
        if wqi['current_wqi'] > 75:
            res = f"Water quality is currently {wqi['current_wqi']} (Good). It appears safe for contact, but keep an eye out for surface algae."
        else:
            res = f"Caution recommended. The WQI is {wqi['current_wqi']} ({wqi['status']}). I advise against swimming until levels improve above 75."
        return {"bot_response": res}

    # 3. REPORT DATA
    if any(k in msg for k in ["report", "sighting", "citizen", "people"]):
        res = f"Our community is active! There are currently {report_count} environmental reports logged in the system. "
        if report_count > 0:
            latest_rep = db.query(models.CitizenReport).order_by(models.CitizenReport.created_at.desc()).first()
            res += f"The most recent sighting was '{latest_rep.title}' regarding {latest_rep.category}."
        return {"bot_response": res}

    # 4. CHEMICALS & SENSORS
    if any(k in msg for k in ["nitrate", "chemical", "ph", "temp", "oxygen", "sensor"]):
        if not latest: return {"bot_response": "I'm unable to reach the sensors right now. Please check the 'Offline Mode' indicator on the dashboard."}
        
        if "nitrate" in msg:
            res = f"Nitrate levels are {latest.nitrates_mg_l} mg/L. (Safety Limit: 5.0 mg/L)."
        elif "ph" in msg:
            res = f"The current alkalinity is pH {latest.ph}. Neutral is 7.0."
        elif "temp" in msg:
            res = f"Water temperature is {latest.temperature_c}°C."
        elif "oxygen" in msg:
            res = f"Dissolved Oxygen is at {latest.dissolved_oxygen_mg_l} mg/L."
        else:
            res = f"We have {sensor_count} active monitoring stations. The primary station is reporting: pH {latest.ph}, Nitrates {latest.nitrates_mg_l} mg/L, and Temp {latest.temperature_c}°C."
        return {"bot_response": res}

    # 5. POLLUTION & HOTSPOTS
    if any(k in msg for k in ["pollution", "hotspot", "dirty", "where"]):
        if pollution_hotspots:
            res = f"I have identified {len(pollution_hotspots)} pollution hotspots in the basin. The most intense areas are currently showing high nitrate concentrations."
        else:
            res = "No significant pollution clusters are detected on the geospatial heatmap at this time."
        return {"bot_response": res}

    # 6. FALLBACK (Conversational)
    return {"bot_response": "I am the IWIS Intelligent Assistant. I have real-time access to the dam's database. You can ask me about: \n- Water Quality (WQI)\n- Safety/Swimming info\n- Specific sensor data (Nitrates, pH, Temp)\n- Community reports and sightings."}
