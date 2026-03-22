-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. ROLES TABLE
CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(255)
);

-- 2. USERS TABLE
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    role_id INT REFERENCES roles(id) ON DELETE SET NULL,
    username VARCHAR(100) NOT NULL UNIQUE,
    passwd_hash VARCHAR(255) NOT NULL
);

-- 3. SENSORS TABLE
CREATE TABLE sensors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sensor_type VARCHAR(100) NOT NULL, -- e.g., 'Water Quality', 'Weather'
    location GEOMETRY(Point, 4326), -- PostGIS Point for map coordinates
    active BOOLEAN DEFAULT TRUE
);

-- 4. SENSOR READINGS TABLE
CREATE TABLE sensor_readings (
    id BIGSERIAL PRIMARY KEY,
    sensor_id UUID REFERENCES sensors(id) ON DELETE CASCADE,
    reading_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ph NUMERIC(4,2) CHECK (ph >= 0.00 AND ph <= 14.00),
    temperature NUMERIC(5,2), -- Celsius
    nitrates NUMERIC(6,2),    -- mg/L
    turbidity NUMERIC(6,2)    -- NTU
);

-- 5. ALERTS TABLE
CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reading_id BIGINT REFERENCES sensor_readings(id) ON DELETE CASCADE,
    alert_type VARCHAR(150) NOT NULL, -- e.g., 'HIGH NITRATE', 'RAPID GROWTH'
    threshold_val NUMERIC,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved BOOLEAN DEFAULT FALSE -- Acknowledged/Acted on
);

-- 6. CITIZEN REPORTS TABLE
CREATE TABLE citizen_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL, -- Nullable for anonymous reports
    location GEOMETRY(Point, 4326),
    description TEXT,
    media VARCHAR(255), -- S3 or local path
    report_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. SATELLITE IMAGERY TABLE
CREATE TABLE satellite_imagery (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    capture_time TIMESTAMP NOT NULL,
    bounding_box GEOMETRY(Polygon, 4326), -- Spatial area covered
    concentration NUMERIC(6,2),
    vegetation_index NUMERIC(6,2), -- e.g., NDVI
    hyacinth_density NUMERIC(6,2)
);

-- 8. SATELLITE SENSOR COVERAGE (Mapping Table)
CREATE TABLE satellite_sensor_coverage (
    satellite_id UUID REFERENCES satellite_imagery(id) ON DELETE CASCADE,
    sensor_id UUID REFERENCES sensors(id) ON DELETE CASCADE,
    overlap_time TIMESTAMP NOT NULL,
    PRIMARY KEY (satellite_id, sensor_id, overlap_time)
);

-- Recommended Indexes for Performance
CREATE INDEX idx_sensor_readings_time ON sensor_readings(reading_time);
CREATE INDEX idx_sensors_location ON sensors USING GIST(location);
CREATE INDEX idx_satellite_imagery_bbox ON satellite_imagery USING GIST(bounding_box);
