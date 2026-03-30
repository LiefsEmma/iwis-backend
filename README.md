# Integrated Water Information System - Backend

# Integrated Water Information System (IWIS) - Backend

This is the FastAPI backend for the Integrated Water Information System (IWIS), a digital monitoring and analytics platform designed to address ecological degradation at Hartbeespoort Dam. It handles data ingestion from environmental sensors, manages citizen-scientist reports, processes automated alerts, and performs real-time exploratory data analysis (EDA).

## Features
* **REST API:** Fast, asynchronous endpoints built with FastAPI.
* **Spatial Database:** PostgreSQL integration with PostGIS for mapping sensor locations and citizen reports.
* **Automated Alerting:** Database triggers automatically generate alerts when ecological thresholds (e.g., nitrates > 5.0 mg/L) are breached.
* **Real-Time Analysis:** On-the-fly Pearson correlation matrices calculated using Pandas.
* **Data Seeding:** Built-in Python script to populate the database with realistic, historical trend data.

## Prerequisites
* Python 3.10+
* PostgreSQL (with the PostGIS extension)
* A terminal environment (Linux/macOS recommended)

## Installation & Setup

**1. Clone the repository**
```bash
git clone git@github.com:LiefsEmma/iwis-backend.git
```
**2. Create and activate a virtual environment**
```bash
python -m venv venv
source venv/bin/activate
```
**3. Install dependencies**
```bash
pip install -r requirements.txt
pip install pandas psycopg2-binary requests
```
**4. Database setup**
```bash
sudo systemctl start postgresql
sudo -u postgres createdb iwis
```

## Running the application

**1. Start the FastAPI server**
```bash
uvicorn app.main:app --reload
```
> The server will at `http://127.0.0.1:8000`. The database tables will be automatically generated upton the first successful connection.

**2. Seed the database**

> Open a second a terminal, and run the seeder script
```bash
python seed_data.py
```

## API Documentation
Once the server is running, FastAPI will automatically generate API documentations

- **Swagger UI:** `http://127.0.0.1:8000/docs`
- **ReDoc:** `http://127.0.0.1:8000/redoc`

