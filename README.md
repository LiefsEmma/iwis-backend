# IWIS Backend - FastAPI + PostgreSQL

This backend powers the **Integrated Water Information System (IWIS)** with:
- FastAPI for API endpoints
- PostgreSQL for environmental data storage
- latitude/longitude coordinates for map data

## Tech Stack
- **Framework:** FastAPI
- **Database:** PostgreSQL
- **ORM:** SQLAlchemy

## Local Setup

### 1. Create and activate a virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Create `.env`
Copy `.env.example` to `.env` and configure your DB connection:

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/iwis
```

### 4. Start the API
```bash
fastapi dev app/main.py
```

API base URL: `http://127.0.0.1:8000`

## Main Endpoints
- `GET /health`
- `POST /sensors`
- `GET /sensors`
- `POST /water-readings`
- `GET /water-readings`
- `POST /weather-readings`
- `GET /weather-readings`
- `POST /citizen-reports`
- `GET /citizen-reports`
- `GET /map/sensors` (GeoJSON)
- `GET /map/citizen-reports` (GeoJSON)

## API Docs
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

