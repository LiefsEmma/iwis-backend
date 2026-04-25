from typing import Any, Dict, List, Optional
import json
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
    # This will create tables if they don't exist
    Base.metadata.create_all(bind=engine)


@app.get("/")
def read_root() -> Dict[str, str]:
    return {
        "status": "online",
        "message": "IWIS API is live",
        "timestamp": datetime.now().isoformat()
    }


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
    sensor = models.Sensor(
        name=payload.name,
        sensor_type=payload.sensor_type,
        is_active=payload.is_active,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
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
    water_reading = models.WaterReading(
        sensor_id=payload.sensor_id,
        ph=payload.ph,
        temperature_c=payload.temperature_c,
        nitrates_mg_l=payload.nitrates_mg_l,
        phosphate_mg_l=payload.phosphate_mg_l,
        turbidity_ntu=payload.turbidity_ntu,
        dissolved_oxygen_mg_l=payload.dissolved_oxygen_mg_l,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    db.add(water_reading)
    db.commit()
    db.refresh(water_reading)
    
    # Broadcast update
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
    report = models.CitizenReport(
        title=payload.title,
        description=payload.description,
        photo_url=payload.photo_url,
        reporter_name=payload.reporter_name,
        reporter_role=payload.reporter_role,
        report_type=payload.report_type,
        severity=payload.severity,
        category=payload.category,
        latitude=payload.latitude,
        longitude=payload.longitude,
        role_specific_data=payload.role_specific_data,
    )
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
        properties = {
            "name": sensor.name,
            "is_active": sensor.is_active,
        }
        if latest:
            properties["latest_readings"] = {
                "ph": latest.ph, "nitrate": latest.nitrates_mg_l, "temperature": latest.temperature_c, "dissolvedOxygen": latest.dissolved_oxygen_mg_l
            }
        features.append(_feature(sensor.id, sensor.latitude, sensor.longitude, properties))
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
    
    data = [{
        "ph": r.ph, 
        "temp": r.temperature_c, 
        "nitrate": r.nitrates_mg_l, 
        "do": r.dissolved_oxygen_mg_l,
        "turbidity": r.turbidity_ntu
    } for r in readings]
    
    df = pd.DataFrame(data)
    
    return {
        "correlations": df.corr().fillna(0).round(3).to_dict(),
        "statistics": df.describe().round(2).to_dict(),
        "sample_size": len(df)
    }

@app.get("/alerts", response_model=List[schemas.AlertRead])
def list_alerts(db: Session = Depends(get_db)) -> List[schemas.AlertRead]:
    return db.query(models.Alert).order_by(models.Alert.created_at.desc()).limit(50).all()

@app.put("/alerts/{alert_id}/status", response_model=schemas.AlertRead)
def update_alert_status(
    alert_id: int,
    payload: schemas.AlertUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.resolved = payload.resolved
    db.commit()
    db.refresh(alert)
    
    # Broadcast the update
    background_tasks.add_task(manager.broadcast, json.dumps({
        "type": "update_alert", 
        "data": schemas.AlertRead.model_validate(alert).model_dump(mode='json')
    }))
    
    return alert
