# Integrated Water Information System (IWIS) - Backend

This is the FastAPI backend for the Integrated Water Information System (IWIS), a digital monitoring and analytics platform designed to address ecological degradation at Hartbeespoort Dam. It handles data ingestion from environmental sensors, manages citizen-scientist reports, processes automated alerts, and performs real-time exploratory data analysis (EDA).

## Features
* **REST API:** Fast, asynchronous endpoints built with FastAPI.
* **Spatial Database:** PostgreSQL integration with PostGIS for mapping sensor locations and citizen reports.
* **Automated Alerting:** Database triggers automatically generate alerts when ecological thresholds (e.g., nitrates > 5.0 mg/L) are breached.
* **Real-Time Analysis:** On-the-fly Pearson correlation matrices calculated using Pandas.
* **Data Seeding:** Built-in Python script to populate the database with realistic, historical trend data.

## Prerequisites
* Python 3.13 recommended (3.10+ supported)
* PostgreSQL (with the PostGIS extension)
* A terminal environment (Windows PowerShell, macOS Terminal, or Linux shell)

## Installation & Setup

**1. Clone the repository**
```bash
git clone git@github.com:username/iwis-backend.git
cd iwis-backend
```
**2. Create and activate a virtual environment**
```powershell
# Windows (PowerShell)
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
```
```cmd
# Windows (Command Prompt)
py -3.13 -m venv .venv
.venv\Scripts\activate.bat
```
```bash
# macOS / Linux
python -m venv .venv
source .venv/bin/activate
```
**3. Install dependencies**
```bash
pip install -r requirements.txt
pip install pandas psycopg2-binary requests
```
**4. Database setup**
```powershell
# Windows (Service name can be postgresql-x64-17, postgresql-x64-18, ...)
Get-Service *postgres*
Start-Service postgresql-x64-18

# If createdb is in PATH
createdb -h localhost -p 5432 -U postgres iwis
```
```bash
# macOS (Homebrew)
brew services start postgresql
createdb -h localhost -p 5432 -U postgres iwis

# macOS (EnterpriseDB installer)
# 1) Add PostgreSQL bin folder to PATH in your current shell session:
# export PATH="/Library/PostgreSQL/<version>/bin:$PATH"
# 2) Then run:
pg_isready -h localhost -p 5432
createdb -h localhost -p 5432 -U postgres iwis
```
```bash
# Linux (systemd)
sudo systemctl start postgresql
sudo -u postgres createdb iwis
```
```bash
# Optional check on any OS
psql -h localhost -p 5432 -U postgres -d iwis -c "SELECT version();"
```

## Running the application

**1. Start the FastAPI server**
```bash
python -m uvicorn app.main:app --reload
```
> The server will run at `http://127.0.0.1:8000`. Database tables are created on the first successful connection.

**2. Seed the database**

> Open a second terminal, and run the seeder script
```bash
python seed_data.py
```

## API Documentation
Once the server is running, FastAPI automatically generates API documentation.

- **Swagger UI:** `http://127.0.0.1:8000/docs`
- **ReDoc:** `http://127.0.0.1:8000/redoc`

