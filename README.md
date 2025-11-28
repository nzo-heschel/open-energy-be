# 🌍 Open Energy Backend — FastAPI Service  
### Electricity Production Mix API (Israel NOGA Integration)

This backend fetches, aggregates, and exposes Israel’s electricity production mix using real-time and historical data from the **NOGA ISO API**.  
It includes hourly averaging, multi-level categorization, UI-friendly endpoints, and CSV/Excel export.

---

## 📁 Project Structure

```
app/
│
├── api/
│   └── v1/
│       ├── energy.py
│       ├── energy_mix.py
│       └── energy_ui.py
│
├── main.py
│
├── services/
│   ├── energy_mix_processor.py
│   ├── energy_mix_service.py
│   ├── energy_processor.py
│   ├── energy_service.py
│   ├── noga_mock_service.py
│   ├── noga_service.py
│   └── user_service.py
│
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

---

# 🚀 Features

- Fetch real-time + historical NOGA production mix data  
- Hourly averaging from 5-minute intervals  
- Level-1 (Renewables / Non-renewables / Others)  
- Level-2 detailed categories (coal, gas, solar, wind, etc.)  
- Export to CSV + Excel  
- Frontend-optimized UI API 

---

# 🔧 Installation

### 1. Clone & Enter Project
```bash
git clone <your-repo-url>
cd open-energy-be
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate         # Windows
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Server
```bash
uvicorn app.main:app --reload
```

### API Docs  
- http://localhost:8000/docs  
- http://localhost:8000/redoc  

---

# 🐳 Docker Setup

```bash
docker-compose up --build
```

API → http://localhost:8000

---

# 📡 API Endpoints

---

# 1️⃣ `/energy` — Core Production Mix API

## **GET `/energy/production-mix`**

Returns aggregated energy mix with hourly averaging.

### Query Parameters
| Name | Default | Options |
|------|---------|---------|
| filter | `year` | `day`, `month`, `year`, `decade` |

### Example Response
```json
{
  "filter": "year",
  "start_date": "01-01-2024",
  "end_date": "28-11-2024",
  "level1": {
    "Non-renewables": 1293923.5,
    "Renewables": 328493.2,
    "Other": 238493.9
  },
  "level2": {
    "Non-renewables": {
      "coal": 390000,
      "natural_Gas": 823000,
      "diesel": 823.45
    },
    "Renewables": {
      "photoVoltaic": 103942,
      "biogas": 12438,
      "wind": 9240,
      "solar_thermal": 3829,
      "pv_storage": 2343
    },
    "Other": {
      "other": 9493,
      "pumped_storage": 29393
    }
  },
  "tooltip": "The pie chart shows Israel’s electricity generation mix..."
}
```

---

## **GET `/energy/production-mix/export`**

Exports Level-1 production mix as **CSV**.

---

# 2️⃣ `/production-mix/ui` — UI-Optimized Endpoint

### GET `/production-mix/ui`

Returns color-coded Level-1 & Level-2 breakdown for frontend pie charts.

```json
{
  "level1": { "Renewables": 23422, "Non-renewables": 98322, "Other": 3920 },
  "level2": {
    "Renewables": [
      { "name": "photoVoltaic", "value": 19200, "color": "#FFD700" }
    ]
  },
  "percentages": { "Renewables": 18.3, "Non-renewables": 77.2 },
  "total_production": 121544
}
```

---

# 3️⃣ `/energy-mix` — Excel Export & Alternative Aggregation

### **GET `/production-mix`**

Supported filters:

- today  
- this_month  
- this_year  
- this_decade  
- between_dates  

Includes:

- hourly average  
- level-1 & level-2  
- percentages  
- totals  

---

## **GET `/production-mix/export`**

Exports detailed production mix as **Excel (.xlsx)** with:

### Sheet 1 → Summary  
| Category | Production | Percentage |

### Sheet 2 → Detailed  
| Category | Subcategory | Production | Percentage |

---

# 🔌 Services

### **NogaService**
- Handles POST requests to NOGA ISO API  
- Flattens nested data  
- Provides:
  - `fetch_production_mix()`
  - `aggregate_energy()`

### **EnergyMixProcessor**
- Aggregates raw NOGA data  
- Produces Level-1, Level-2, percentages, totals  

### **Energy UI Processor**
- Adds color palette  
- Formats breakdown for pie charts  

---

# ⚙ Environment Variables (optional)

| Variable | Description |
|----------|-------------|
| `NOGA_TOKEN` | API key for NOGA |

---

# 📦 Requirements
```
fastapi
uvicorn
sqlalchemy
pydantic
python-dotenv
passlib[bcrypt]
jose
alembic
```

---