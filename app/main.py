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
from groq import Groq


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


def _build_chat_context(db: Session) -> str:
    latest = db.query(models.WaterReading).order_by(models.WaterReading.recorded_at.desc()).first()
    alerts_count = db.query(models.Alert).filter(models.Alert.resolved.is_(False)).count()
    reports_count = db.query(models.CitizenReport).count()

    if latest is None:
        return (
            "No recent water reading data is available yet. "
            f"Open alerts: {alerts_count}. Citizen reports: {reports_count}."
        )

    return (
        f"Latest water reading at {latest.recorded_at.isoformat()}: "
        f"pH={latest.ph}, temperature_c={latest.temperature_c}, nitrates_mg_l={latest.nitrates_mg_l}, "
        f"phosphate_mg_l={latest.phosphate_mg_l}, turbidity_ntu={latest.turbidity_ntu}, "
        f"dissolved_oxygen_mg_l={latest.dissolved_oxygen_mg_l}. "
        f"Open alerts: {alerts_count}. Citizen reports: {reports_count}."
    )


def _looks_like_greeting_or_test(message: str) -> bool:
    text = message.strip().lower()
    return text in {"test", "hi", "hello", "hey", "yo", "hallo"}


def _looks_like_swimming_question(message: str) -> bool:
    text = message.lower()
    return bool(
        re.search(
            r"swim|swimming|can i swim|safe to swim|"
            r"zwem|zwemmen|mag ik zwemmen|"
            r"veilig|veiligheid|"
            r"water safe",
            text,
        )
    )


def _looks_like_nitrate_question(message: str) -> bool:
    text = message.lower()
    return "nitrate" in text or "nitrates" in text or "nitraat" in text


@app.post("/chat", response_model=schemas.ChatResponse)
def chat_with_ai(payload: schemas.ChatRequest, db: Session = Depends(get_db)) -> schemas.ChatResponse:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not configured")

    context = _build_chat_context(db)
    latest = db.query(models.WaterReading).order_by(models.WaterReading.recorded_at.desc()).first()
    model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

    if _looks_like_greeting_or_test(payload.message):
        return schemas.ChatResponse(
            bot_response=(
                "Hi! I am your IWIS assistant. I can answer questions about recent readings, nitrates, alerts, "
                "and whether conditions look safe based on available data."
            )
        )

    if latest is None:
        if _looks_like_swimming_question(payload.message):
            return schemas.ChatResponse(
                bot_response=(
                    "I cannot confirm swimming safety yet because there are no recent water readings in IWIS. "
                    "Please treat it as unknown risk until new measurements are available."
                )
            )
        if _looks_like_nitrate_question(payload.message):
            return schemas.ChatResponse(
                bot_response=(
                    "There is no recent nitrate reading available in IWIS yet, so I cannot assess current risk. "
                    "For this platform, nitrate alerts are triggered above 5.0 mg/L."
                )
            )
        return schemas.ChatResponse(
            bot_response=(
                "I do not have recent water reading data yet. Ask me again after new sensor data is ingested, "
                "or ask about platform features and alerts."
            )
        )

    if _looks_like_nitrate_question(payload.message):
        threshold = 5.0
        risk = "low"
        if latest.nitrates_mg_l > 10.0:
            risk = "high"
        elif latest.nitrates_mg_l > threshold:
            risk = "medium"

        return schemas.ChatResponse(
            bot_response=(
                f"The latest nitrate level is {latest.nitrates_mg_l:.2f} mg/L (recorded at {latest.recorded_at.isoformat()}). "
                f"Using IWIS alert rules (> {threshold:.1f} mg/L), this is currently a {risk} risk reading."
            )
        )

    if _looks_like_swimming_question(payload.message):
        ph_ok = 6.5 <= latest.ph <= 8.5
        nitrate_ok = latest.nitrates_mg_l <= 5.0
        do_ok = latest.dissolved_oxygen_mg_l >= 5.0
        turb_ok = latest.turbidity_ntu <= 5.0
        signals_ok = sum([ph_ok, nitrate_ok, do_ok, turb_ok])
        verdict = "likely acceptable with caution" if signals_ok >= 3 else "not recommended right now"

        return schemas.ChatResponse(
            bot_response=(
                f"Based on the latest IWIS reading (pH {latest.ph:.2f}, nitrate {latest.nitrates_mg_l:.2f} mg/L, "
                f"DO {latest.dissolved_oxygen_mg_l:.2f} mg/L, turbidity {latest.turbidity_ntu:.2f} NTU), "
                f"swimming is {verdict}. Please still follow official local advisories."
            )
        )

    history: List[Dict[str, str]] = []
    for item in payload.history[-10:]:
        if item.role in {"user", "assistant"}:
            history.append({"role": item.role, "content": item.content.strip()[:2000]})

    try:
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are the IWIS assistant for Hartbeespoort Dam. "
                        "Always answer in 2-4 concise sentences. "
                        "Use only the provided context and never invent values. "
                        "If a value is missing, explicitly say it is unavailable. "
                        "Do not include meta text such as 'Live platform context' in your answer. "
                        f"Context: {context}"
                    ),
                },
                *history,
                {"role": "user", "content": payload.message.strip()},
            ],
        )
        answer = completion.choices[0].message.content or "No response generated."
        return schemas.ChatResponse(bot_response=answer.strip())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate chat response: {exc}")


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
    water_reading = models.WaterReading(**payload.model_dump())
    db.add(water_reading)
    db.commit()
    db.refresh(water_reading)
    
    # THRESHOLD CHECKER (The "Alert Generator")
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
        db.refresh(alert)
        
        # Broadcast Alert
        background_tasks.add_task(manager.broadcast, json.dumps({
            "type": "new_alert", 
            "data": schemas.AlertRead.model_validate(alert).model_dump(mode='json')
        }))

    # Broadcast reading
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
    return {"current_wqi": round(avg, 1), "status": "Excellent" if avg > 90 else "Good" if avg > 70 else "Fair"}

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
