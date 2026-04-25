curl -X POST "https://iwis-backend.onrender.com/water-readings" \
    -H "Content-Type: application/json" \
    -d '{
        "sensor_id": 1,
        "ph": 7.2,
        "temperature_c": 22.5,
        "nitrates_mg_l": 12.5,
        "turbidity_ntu": 5.0,
        "dissolved_oxygen_mg_l: 6.2,
        "latitude": -25.7343
        "longitude": 27.8587
    }'

