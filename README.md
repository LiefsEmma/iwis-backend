# IWIS Backend - Hartbeespoort Dam Monitoring

This is the FastAPI backend for the **Integrated Water Information System (IWIS)**. It handles data ingestion from water quality sensors, weather APIs, and citizen reports, storing them in a PostgreSQL database for analysis.

## Tech Stack
- **Framework:** FastAPI (Python)
- **Database:** PostgreSQL
- **ORM:** SQLAlchemy
- **Data Analysis:** Pandas, Numpy, Seaborn, Plotly

## Setup Instructions

### 1. Clone and Enter
```bash
git clone
cd iwis-backend
```

### 2. Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate # On windows, run .\venv\Scripts\activate
```


### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Server
```
fastapi dev app/main.py
```

The API will be available at http://127.0.0.1:8000.

## Project Structure
app/main.py: Entry point and API routes.

app/models.py: Database table definitions (Postgres).

app/database.py: Connection logic.

app/schemas.py: Data validation for sensor inputs.

## API Documentation
Once the server is running, visit:

Swagger UI: http://127.0.0.1:8000/docs

ReDoc: http://127.0.0.1:8000/redoc

