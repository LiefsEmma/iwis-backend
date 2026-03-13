from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import models, schemas
from .database import Base, engine, get_db


app = FastAPI(title="IWIS Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _feature(feature_id: int, latitude: float, longitude: float, properties: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "Feature",
        "id": feature_id,
        "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
        "properties": properties,
    }


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/")
def read_root() -> Dict[str, str]:
    return {"message": "Integrated Water Information System API is running"}


@app.get("/health")
def healthcheck() -> Dict[str, str]:
    return {"status": "ok"}


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

    return schemas.WaterReadingRead(
        id=water_reading.id,
        sensor_id=water_reading.sensor_id,
        recorded_at=water_reading.recorded_at,
        ph=water_reading.ph,
        temperature_c=water_reading.temperature_c,
        nitrates_mg_l=water_reading.nitrates_mg_l,
        turbidity_ntu=water_reading.turbidity_ntu,
        dissolved_oxygen_mg_l=water_reading.dissolved_oxygen_mg_l,
        latitude=water_reading.latitude,
        longitude=water_reading.longitude,
    )


@app.get("/water-readings", response_model=List[schemas.WaterReadingRead])
def list_water_readings(
    sensor_id: Optional[int] = None,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> List[schemas.WaterReadingRead]:
    query = db.query(models.WaterReading)
    if sensor_id is not None:
        query = query.filter(models.WaterReading.sensor_id == sensor_id)

    readings = query.order_by(models.WaterReading.recorded_at.desc()).limit(limit).all()

    return [
        schemas.WaterReadingRead(
            id=reading.id,
            sensor_id=reading.sensor_id,
            recorded_at=reading.recorded_at,
            ph=reading.ph,
            temperature_c=reading.temperature_c,
            nitrates_mg_l=reading.nitrates_mg_l,
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
        description=payload.description,
        photo_url=payload.photo_url,
        reporter_name=payload.reporter_name,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return schemas.CitizenReportRead(
        id=report.id,
        created_at=report.created_at,
        description=report.description,
        photo_url=report.photo_url,
        reporter_name=report.reporter_name,
        status=report.status,
        latitude=report.latitude,
        longitude=report.longitude,
    )


@app.get("/citizen-reports", response_model=List[schemas.CitizenReportRead])
def list_citizen_reports(
    status: Optional[str] = None,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> List[schemas.CitizenReportRead]:
    query = db.query(models.CitizenReport)
    if status:
        query = query.filter(models.CitizenReport.status == status)

    reports = query.order_by(models.CitizenReport.created_at.desc()).limit(limit).all()

    return [
        schemas.CitizenReportRead(
            id=report.id,
            created_at=report.created_at,
            description=report.description,
            photo_url=report.photo_url,
            reporter_name=report.reporter_name,
            status=report.status,
            latitude=report.latitude,
            longitude=report.longitude,
        )
        for report in reports
    ]


@app.get("/map/sensors")
def sensors_geojson(db: Session = Depends(get_db)) -> Dict[str, Any]:
    sensors = db.query(models.Sensor).all()

    features = [
        _feature(
            feature_id=sensor.id,
            latitude=sensor.latitude,
            longitude=sensor.longitude,
            properties={
                "name": sensor.name,
                "sensor_type": sensor.sensor_type,
                "is_active": sensor.is_active,
                "installed_at": sensor.installed_at.isoformat() if sensor.installed_at else None,
            },
        )
        for sensor in sensors
    ]

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
                "created_at": report.created_at.isoformat() if report.created_at else None,
            },
        )
        for report in reports
    ]

    return {"type": "FeatureCollection", "features": features}
