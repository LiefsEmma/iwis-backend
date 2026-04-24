# Integrated Water Information System (IWIS) - Backend

This is the FastAPI backend for the Integrated Water Information System (IWIS), a digital monitoring and analytics platform designed to address ecological degradation at Hartbeespoort Dam.

## Features
* **REST API:** Fast, asynchronous endpoints built with FastAPI.
* **Spatial Database:** PostgreSQL integration for mapping sensor locations and citizen reports.
* **Automated Alerting:** Processes alerts when ecological thresholds (e.g., nitrates > 5.0 mg/L) are breached.
* **Real-Time Analysis:** On-the-fly Pearson correlation matrices calculated using Pandas.
* **Live Updates:** WebSocket support for real-time sensor data and alerts.

## Prerequisites
* **Python 3.13+**
* **PostgreSQL:** Installed and listening on the default port `5432`.
* **PostGIS Extension:** (Optional, but recommended for advanced spatial features).

## Quick Start (New Users)

**1. Create a Virtual Environment**
Navigate to the project root and create the shared `venv` folder:

- **macOS / Linux:**
  ```bash
  python -m venv venv
  ```
- **Windows (PowerShell):**
  ```powershell
  python -m venv venv
  ```

**2. Start PostgreSQL Service**
Ensure the PostgreSQL server is running on port `5432`:

- **Windows (PowerShell):**
  ```powershell
  # Replace 'postgresql-x64-18' with your installed version
  Start-Service postgresql*
  ```
- **macOS (Homebrew):**
  ```bash
  brew services start postgresql
  ```
- **Linux:**
  ```bash
  sudo systemctl start postgresql
  ```

**3. Database Setup**
Create the `iwis` database:

- **Windows (PowerShell):**
  ```powershell
  createdb -U postgres iwis
  ```
- **macOS (Homebrew):**
  ```bash
  createdb -U postgres iwis
  ```
- **Linux:**
  ```bash
  sudo -u postgres createdb iwis
  ```

**4. Configure Environment**
From the `iwis-backend` directory, copy the example environment file:

- **macOS / Linux:**
  ```bash
  cp .env.example .env
  ```
- **Windows (PowerShell):**
  ```powershell
  copy .env.example .env
  ```

Update `.env` with your database URL (using `127.0.0.1` is recommended):
```env
DATABASE_URL=postgresql+psycopg2://postgres:YOUR_PASSWORD@127.0.0.1:5432/iwis
```

**5. Install Dependencies**
The project uses the `venv` created in Step 1. From the project root:

- **macOS / Linux:**
  ```bash
  ./venv/bin/pip install -r iwis-backend/requirements.txt
  ./venv/bin/pip install websockets
  ```
- **Windows (PowerShell):**
  ```powershell
  .\venv\Scripts\pip install -r iwis-backend\requirements.txt
  .\venv\Scripts\pip install websockets
  ```

**6. Start the FastAPI Server**
From the `iwis-backend` directory:

- **macOS / Linux:**
  ```bash
  ../venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
  ```
- **Windows (PowerShell):**
  ```powershell
  ..\venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
  ```

The server will be available at `http://127.0.0.1:8000`.

**7. Seed Historical Data (Optional)**
Populate the database with realistic trend data for testing:

- **macOS / Linux:**
  ```bash
  ../venv/bin/python seed_data.py
  ```
- **Windows (PowerShell):**
  ```powershell
  ..\venv\Scripts\python seed_data.py
  ```

## API Documentation
Once the server is running, you can explore the API using:
- **Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

## Troubleshooting
- **Connection Refused (DB):** Ensure the `DATABASE_URL` matches your local PostgreSQL credentials and that the service is running on port `5432`.
- **WebSocket Error:** Ensure the `websockets` library is installed and you are connecting to `ws://127.0.0.1:8000/ws/live`.
