from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from .database import Base


class Sensor(Base):
    __tablename__ = "sensors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    sensor_type = Column(String(50), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    installed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    water_readings = relationship("WaterReading", back_populates="sensor", cascade="all, delete-orphan")


class WaterReading(Base):
    __tablename__ = "water_readings"

    id = Column(Integer, primary_key=True, index=True)
    sensor_id = Column(Integer, ForeignKey("sensors.id", ondelete="SET NULL"), nullable=True, index=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    ph = Column(Float, nullable=False)
    temperature_c = Column(Float, nullable=False)
    nitrates_mg_l = Column(Float, nullable=False)
    turbidity_ntu = Column(Float, nullable=False)
    dissolved_oxygen_mg_l = Column(Float, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    sensor = relationship("Sensor", back_populates="water_readings")


class WeatherReading(Base):
    __tablename__ = "weather_readings"

    id = Column(Integer, primary_key=True, index=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    wind_speed_m_s = Column(Float, nullable=False)
    wind_direction_deg = Column(Float, nullable=False)
    air_temperature_c = Column(Float, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)


class CitizenReport(Base):
    __tablename__ = "citizen_reports"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    reporter_name = Column(String(120), nullable=True)
    description = Column(Text, nullable=True)
    photo_url = Column(String(500), nullable=True)
    status = Column(String(30), nullable=False, default="new", index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
