from typing import Any, Dict, List, Optional
import json
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import models, schemas
from .database import Base, engine, get_db

import pandas as pd


app = FastAPI(title="IWIS Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    # Simplified Water Quality Index (0-100)
    # Weights: pH (0.2), Nitrate (0.3), DO (0.3), Turbidity (0.2)
    # Ideal: pH 7.0, Nitrate < 1.0, DO > 7.0, Turbidity < 5.0
    
    # pH score: 100 if 7.0, decreases as it moves away
    ph_score = 100 - abs(reading.ph - 7.0) * 20
    
    # Nitrate score: 100 if < 1.0, 0 if > 10.0
    nitrate_score = max(0, 100 - reading.nitrates_mg_l * 10)
    
    # DO score: 100 if > 7.0, 0 if < 2.0
    do_score = min(100, max(0, (reading.dissolved_oxygen_mg_l - 2.0) * 20))
    
    # Turbidity score: 100 if < 5.0, 0 if > 50.0
    turb_score = max(0, 100 - (reading.turbidity_ntu - 5.0) * 2)
    
    wqi = (ph_score * 0.2) + (nitrate_score * 0.3) + (do_score * 0.3) + (turb_score * 0.2)
    return round(max(0, min(100, wqi)), 2)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/")
def read_root() -> Dict[str, str]:
    return {"message": "Integrated Water Information System API is running"}


@app.get("/health")
def healthcheck() -> Dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We don't expect the client to send messages, but we keep the connection open
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

    return schemas.SensorRead(
        id=sensor.id,
        name=sensor.name,
        sensor_type=sensor.sensor_type,
        is_active=sensor.is_active,
        installed_at=sensor.installed_at,
        latitude=sensor.latitude,
        longitude=sensor.longitude,
    )


@app.get("/sensors", response_model=List[schemas.SensorRead])
def list_sensors(db: Session = Depends(get_db)) -> List[schemas.SensorRead]:
    sensors = db.query(models.Sensor).order_by(models.Sensor.id.asc()).all()

    return [
        schemas.SensorRead(
            id=sensor.id,
            name=sensor.name,
            sensor_type=sensor.sensor_type,
            is_active=sensor.is_active,
            installed_at=sensor.installed_at,
            latitude=sensor.latitude,
            longitude=sensor.longitude,
        )
        for sensor in sensors
    ]


@app.post("/water-readings", response_model=schemas.WaterReadingRead, status_code=201)
def create_water_reading(
    payload: schemas.WaterReadingCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> schemas.WaterReadingRead:
    if payload.sensor_id is not None:
        sensor_exists = db.query(models.Sensor.id).filter(models.Sensor.id == payload.sensor_id).first()
        if sensor_exists is None:
            raise HTTPException(status_code=404, detail="Sensor not found")

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
    if payload.recorded_at is not None:
        water_reading.recorded_at = payload.recorded_at

    db.add(water_reading)
    db.commit()
    db.refresh(water_reading)
    
    reading_data = schemas.WaterReadingRead.model_validate(water_reading).model_dump()
    reading_data['recorded_at'] = reading_data['recorded_at'].isoformat()

    background_tasks.add_task(
        manager.broadcast,
        json.dumps({"type": "new_reading", "data": reading_data})
    )

    NITRATE_THRESHOLD = 5.0
    if water_reading.nitrates_mg_l > NITRATE_THRESHOLD:
        severity = "high" if water_reading.nitrates_mg_l > 10.0 else "medium"
        new_alert = models.Alert(
                reading_id=water_reading.id,
                alert_type="HIGH NITRATE DETECTED",
                severity=severity,
                threshold_val=NITRATE_THRESHOLD
                )
        db.add(new_alert)
        db.commit()
        db.refresh(new_alert)
        
        alert_data = schemas.AlertRead.model_validate(new_alert).model_dump()
        alert_data['created_at'] = alert_data['created_at'].isoformat()
        
        background_tasks.add_task(
            manager.broadcast,
            json.dumps({"type": "new_alert", "data": alert_data})
        )

    return schemas.WaterReadingRead.model_validate(water_reading)


@app.get("/water-readings", response_model=List[schemas.WaterReadingRead])
def list_water_readings(
    sensor_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> List[schemas.WaterReadingRead]:
    query = db.query(models.WaterReading)
    if sensor_id is not None:
        query = query.filter(models.WaterReading.sensor_id == sensor_id)
    if start_date:
        query = query.filter(models.WaterReading.recorded_at >= start_date)
    if end_date:
        query = query.filter(models.WaterReading.recorded_at <= end_date)

    readings = query.order_by(models.WaterReading.recorded_at.desc()).limit(limit).all()

    return [
        schemas.WaterReadingRead(
            id=reading.id,
            sensor_id=reading.sensor_id,
            recorded_at=reading.recorded_at,
            ph=reading.ph,
            temperature_c=reading.temperature_c,
            nitrates_mg_l=reading.nitrates_mg_l,
            phosphate_mg_l=reading.phosphate_mg_l,
            turbidity_ntu=reading.turbidity_ntu,
            dissolved_oxygen_mg_l=reading.dissolved_oxygen_mg_l,
            latitude=reading.latitude,
            longitude=reading.longitude,
        )
        for reading in readings
    ]


@app.post("/weather-readings", response_model=schemas.WeatherReadingRead, status_code=201)
def create_weather_reading(
    payload: schemas.WeatherReadingCreate,
    db: Session = Depends(get_db),
) -> schemas.WeatherReadingRead:
    weather_reading = models.WeatherReading(
        wind_speed_m_s=payload.wind_speed_m_s,
        wind_direction_deg=payload.wind_direction_deg,
        air_temperature_c=payload.air_temperature_c,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    if payload.recorded_at is not None:
        weather_reading.recorded_at = payload.recorded_at

    db.add(weather_reading)
    db.commit()
    db.refresh(weather_reading)

    return schemas.WeatherReadingRead(
        id=weather_reading.id,
        recorded_at=weather_reading.recorded_at,
        wind_speed_m_s=weather_reading.wind_speed_m_s,
        wind_direction_deg=weather_reading.wind_direction_deg,
        air_temperature_c=weather_reading.air_temperature_c,
        latitude=weather_reading.latitude,
        longitude=weather_reading.longitude,
    )


@app.get("/weather-readings", response_model=List[schemas.WeatherReadingRead])
def list_weather_readings(
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> List[schemas.WeatherReadingRead]:
    readings = db.query(models.WeatherReading).order_by(models.WeatherReading.recorded_at.desc()).limit(limit).all()

    return [
        schemas.WeatherReadingRead(
            id=reading.id,
            recorded_at=reading.recorded_at,
            wind_speed_m_s=reading.wind_speed_m_s,
            wind_direction_deg=reading.wind_direction_deg,
            air_temperature_c=reading.air_temperature_c,
            latitude=reading.latitude,
            longitude=reading.longitude,
        )
        for reading in readings
    ]


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
    if status:
        query = query.filter(models.CitizenReport.status == status)
    if reporter_role:
        query = query.filter(models.CitizenReport.reporter_role == reporter_role)
    if category:
        query = query.filter(models.CitizenReport.category == category)

    reports = query.order_by(models.CitizenReport.created_at.desc()).limit(limit).all()
    return reports


@app.get("/map/sensors")
def sensors_geojson(db: Session = Depends(get_db)) -> Dict[str, Any]:
    sensors = db.query(models.Sensor).all()

    features = []
    for sensor in sensors:
        latest_reading = db.query(models.WaterReading).filter(models.WaterReading.sensor_id == sensor.id).order_by(models.WaterReading.recorded_at.desc()).first()
        
        properties = {
            "name": sensor.name,
            "sensor_type": sensor.sensor_type,
            "is_active": sensor.is_active,
            "installed_at": sensor.installed_at.isoformat() if sensor.installed_at else None,
        }
        
        if latest_reading:
            properties["latest_readings"] = {
                "ph": latest_reading.ph,
                "nitrate": latest_reading.nitrates_mg_l,
                "phosphate": latest_reading.phosphate_mg_l,
                "temperature": latest_reading.temperature_c,
                "dissolvedOxygen": latest_reading.dissolved_oxygen_mg_l,
                "turbidity": latest_reading.turbidity_ntu,
                "recorded_at": latest_reading.recorded_at.isoformat()
            }
        
        features.append(_feature(
            feature_id=sensor.id,
            latitude=sensor.latitude,
            longitude=sensor.longitude,
            properties=properties,
        ))

    return {"type": "FeatureCollection", "features": features}


@app.get("/map/citizen-reports")
def citizen_reports_geojson(db: Session = Depends(get_db)) -> Dict[str, Any]:
    reports = db.query(models.CitizenReport).all()

    features = [
        _feature(
            feature_id=report.id,
            latitude=report.latitude,
            longitude=report.longitude,
            properties={
                "status": report.status,
                "description": report.description,
                "photo_url": report.photo_url,
                "reporter_name": report.reporter_name,
                "report_type": report.report_type,
                "created_at": report.created_at.isoformat() if report.created_at else None,
            },
        )
        for report in reports
    ]

    return {"type": "FeatureCollection", "features": features}

from sqlalchemy import cast, Date, func

...
@app.get("/analysis/trends")
def get_wqi_trends(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    # Calculate daily average WQI
    # In a real app, this would be a more efficient query or a materialized view
    readings = db.query(models.WaterReading).order_by(models.WaterReading.recorded_at.desc()).limit(2000).all()
    
    if not readings:
        return []
        
    df = pd.DataFrame([{
        "date": r.recorded_at.date(),
        "wqi": calculate_wqi(r)
    } for r in readings])
    
    trends = df.groupby("date")["wqi"].mean().round(2).reset_index()
    trends["date"] = trends["date"].apply(lambda x: x.isoformat())
    
    return trends.to_dict(orient="records")

@app.get("/analysis/correlations")
def get_realtime_correlations(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    query = db.query(models.WaterReading)
    
    if start_date:
        query = query.filter(models.WaterReading.recorded_at >= start_date)
    if end_date:
        query = query.filter(models.WaterReading.recorded_at <= end_date)
        
    readings = query.order_by(models.WaterReading.recorded_at.desc()).limit(10000).all()
    
    if len(readings) < 2:
        raise HTTPException(status_code=404, detail="Not enough data for analysis")

    data = [{
        "ph": r.ph,
        "temperature_c": r.temperature_c,
        "nitrates_mg_l": r.nitrates_mg_l,
        "phosphate_mg_l": r.phosphate_mg_l if r.phosphate_mg_l is not None else 0,
        "dissolved_oxygen": r.dissolved_oxygen_mg_l,
        "turbidity": r.turbidity_ntu
    } for r in readings]
    
    df = pd.DataFrame(data)

    corr_matrix = df.corr(method="pearson").fillna(0).round(3).to_dict()

    stats = df.describe().round(2).to_dict()

    return {
        "correlations": corr_matrix,
        "statistics": stats,
        "sample_size": len(df)
    }

@app.get("/analysis/hotspots")
def get_pollution_hotspots(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    # Simple algorithm: Find locations with nitrate > 5.0 or phosphate > 2.0
    high_pollution_readings = db.query(models.WaterReading).filter(
        (models.WaterReading.nitrates_mg_l > 4.0) | (models.WaterReading.phosphate_mg_l > 1.5)
    ).order_by(models.WaterReading.recorded_at.desc()).limit(100).all()
    
    if not high_pollution_readings:
        return []
    
    hotspots = []
    for r in high_pollution_readings:
        intensity = "low"
        if r.nitrates_mg_l > 8.0 or (r.phosphate_mg_l and r.phosphate_mg_l > 3.0):
            intensity = "high"
        elif r.nitrates_mg_l > 5.0 or (r.phosphate_mg_l and r.phosphate_mg_l > 2.0):
            intensity = "medium"
            
        hotspots.append({
            "id": f"hotspot-{r.id}",
            "lat": r.latitude,
            "lng": r.longitude,
            "intensity": intensity,
            "radiusMeters": 400 + (r.nitrates_mg_l * 20)
        })
        
    return hotspots

@app.get("/analysis/wqi-summary")
def get_wqi_summary(db: Session = Depends(get_db)) -> Dict[str, Any]:
    latest_readings = db.query(models.WaterReading).order_by(models.WaterReading.recorded_at.desc()).limit(50).all()
    
    if not latest_readings:
        return {"current_wqi": 0, "status": "No data"}
        
    wqi_values = [calculate_wqi(r) for r in latest_readings]
    avg_wqi = sum(wqi_values) / len(wqi_values)
    
    status = "Excellent"
    if avg_wqi < 50:
        status = "Poor"
    elif avg_wqi < 70:
        status = "Fair"
    elif avg_wqi < 90:
        status = "Good"
    
    return {
        "current_wqi": round(avg_wqi, 1),
        "status": status,
        "sample_size": len(latest_readings)
    }

@app.get("/alerts", response_model=List[schemas.AlertRead])
def list_alerts(db: Session = Depends(get_db)) -> List[schemas.AlertRead]:
    alerts = db.query(models.Alert).filter(not models.Alert.resolved).order_by(models.Alert.created_at.desc()).limit(10).all()
    return alerts

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
    
    alert_data = schemas.AlertRead.model_validate(alert).model_dump()
    alert_data['created_at'] = alert_data['created_at'].isoformat()
    
    background_tasks.add_task(
        manager.broadcast,
        json.dumps({"type": "update_alert", "data": alert_data})
    )
    
    return alert
