from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SensorBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    sensor_type: str = Field(..., min_length=2, max_length=50)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class SensorCreate(SensorBase):
    is_active: bool = True


class SensorRead(SensorBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    installed_at: datetime


class WaterReadingBase(BaseModel):
    sensor_id: Optional[int] = None
    recorded_at: Optional[datetime] = None
    ph: float = Field(..., ge=0, le=14)
    temperature_c: float = Field(..., ge=-5, le=60)
    nitrates_mg_l: float = Field(..., ge=0, le=500)
    phosphate_mg_l: Optional[float] = Field(None, ge=0, le=500)
    turbidity_ntu: float = Field(..., ge=0, le=10000)
    dissolved_oxygen_mg_l: float = Field(..., ge=0, le=25)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class WaterReadingCreate(WaterReadingBase):
    pass


class WaterReadingRead(WaterReadingBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recorded_at: datetime


class WeatherReadingBase(BaseModel):
    recorded_at: Optional[datetime] = None
    wind_speed_m_s: float = Field(..., ge=0, le=80)
    wind_direction_deg: float = Field(..., ge=0, le=360)
    air_temperature_c: float = Field(..., ge=-30, le=60)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class WeatherReadingCreate(WeatherReadingBase):
    pass


class WeatherReadingRead(WeatherReadingBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recorded_at: datetime


class CitizenReportBase(BaseModel):
    description: Optional[str] = Field(default=None, max_length=2000)
    photo_url: Optional[str] = Field(default=None, max_length=500)
    reporter_name: Optional[str] = Field(default=None, max_length=120)
    report_type: Optional[str] = Field(default="citizen-scientist", max_length=50)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class CitizenReportCreate(CitizenReportBase):
    pass


class CitizenReportRead(CitizenReportBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    status: str


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reading_id: Optional[int]
    alert_type: str
    severity: str
    threshold_val: Optional[float]
    created_at: datetime
    resolved: bool

class AlertUpdate(BaseModel):
    resolved: bool

