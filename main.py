from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
from datetime import datetime, timedelta
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

# Allow CORS for Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SQLite database setup
def init_db():
    conn = sqlite3.connect("water_flow.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS flow_data
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT,
                  flow_rate REAL,
                  total_volume REAL,
                  valve_state INTEGER)''')
    conn.commit()
    conn.close()

init_db()

# Data model for incoming Arduino data
class FlowData(BaseModel):
    flow_rate: float
    total_volume: float
    quality_units: float  # Included but not stored in DB
    valve_state: bool
    timestamp: str

# Global valve command state
valve_command = "close"

@app.post("/data")
async def receive_data(data: FlowData):
    conn = sqlite3.connect("water_flow.db")
    c = conn.cursor()
    c.execute("INSERT INTO flow_data (timestamp, flow_rate, total_volume, valve_state) VALUES (?, ?, ?, ?)",
              (data.timestamp, data.flow_rate, data.total_volume, 1 if data.valve_state else 0))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.get("/valve")
async def get_valve_command():
    return valve_command

@app.post("/set_valve/{state}")
async def set_valve(state: str):
    global valve_command
    if state in ["open", "close"]:
        valve_command = state
        return {"status": "success", "valve": state}
    raise HTTPException(status_code=400, detail="Invalid state")

@app.get("/metrics")
async def get_metrics():
    conn = sqlite3.connect("water_flow.db")
    c = conn.cursor()
    
    # Today's usage
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT MAX(total_volume) - MIN(total_volume) FROM flow_data WHERE timestamp LIKE ?", (f"{today}%",))
    today_usage = c.fetchone()[0] or 0.0
    
    # Last 7 days
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    c.execute("SELECT MAX(total_volume) - MIN(total_volume) FROM flow_data WHERE timestamp >= ?", (week_ago,))
    week_usage = c.fetchone()[0] or 0.0
    
    # Last 30 days
    month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    c.execute("SELECT MAX(total_volume) - MIN(total_volume) FROM flow_data WHERE timestamp >= ?", (month_ago,))
    month_usage = c.fetchone()[0] or 0.0
    
    conn.close()
    return {
        "today": today_usage,
        "last_week": week_usage,
        "last_month": month_usage
    }

@app.get("/history")
async def get_history():
    conn = sqlite3.connect("water_flow.db")
    c = conn.cursor()
    c.execute("SELECT timestamp, flow_rate, total_volume, valve_state FROM flow_data ORDER BY id DESC LIMIT 100")
    data = [{"timestamp": row[0], "flow_rate": row[1], "total_volume": row[2], "valve_state": bool(row[3])} for row in c.fetchall()]
    conn.close()
    return data

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)