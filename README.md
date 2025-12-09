# 🌍 Open Energy — Backend (FastAPI)

### Israel Electricity Production Mix & Market Data API (NOGA Integration)

A comprehensive backend web service that collects, processes, and exposes Israel's electricity production data, pricing information, and market insights through modern REST API endpoints. Integrates with NOGA (Israel's Independent System Operator) to provide real-time and historical energy generation data.

The service is designed for dashboards, analytics platforms, energy market analysis tools, and other applications requiring reliable access to Israel's energy data.

---

## 📋 Table of Contents

- [What This Project Does](#what-this-project-does)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [API Documentation](#api-documentation)
- [Complete Endpoint Reference](#complete-endpoint-reference)
- [Architecture](#architecture)
- [Development & Extension](#development--extension)
- [Troubleshooting](#troubleshooting)

---

## What This Project Does

- **Collects** real-time and historical electricity generation data from NOGA (Israel's Independent System Operator)
- **Processes** high-frequency (5-minute interval) raw measurements into hourly averages
- **Aggregates** energy sources into hierarchical, human-readable categories (fossil, renewable, other)
- **Calculates** key metrics: renewable percentage, total generation, pricing, market trends
- **Exposes** processed data via REST API endpoints returning JSON and Excel exports
- **Tracks** market data: System Marginal Price (SMP), private supplier connections, consumer switching requests

---

## Key Features

✅ **Real-time & Historical Data** — Query production mix for any date range  
✅ **Multi-level Aggregation** — Level-1 broad categories + Level-2 detailed sources  
✅ **Renewable Share Calculation** — Automatic percentage calculations and insights  
✅ **Excel Export** — Download data with summaries and detailed breakdowns  
✅ **System Marginal Price (SMP)** — Real-time and historical electricity pricing  
✅ **Private Suppliers Tracking** — Monitor private supplier connections by segment  
✅ **Consumer Switching Requests** — Analyze supplier switching trends  
✅ **UI-Optimized Endpoints** — Data formatted with colors for frontend visualization  
✅ **Interactive Documentation** — Swagger UI + ReDoc for exploration and testing  
✅ **Error Handling** — Graceful responses with meaningful error messages

---

## Tech Stack

| Component            | Technology                           |
| -------------------- | ------------------------------------ |
| **Language**         | Python 3.11+                         |
| **Framework**        | FastAPI (modern async web framework) |
| **Server**           | Uvicorn (ASGI server)                |
| **Data Processing**  | Pandas, NumPy                        |
| **Export**           | OpenPyXL (Excel generation)          |
| **Containerization** | Docker & Docker Compose              |
| **External API**     | NOGA (Israel System Operator) HTTP   |
| **Config**           | python-dotenv                        |

---

## Project Structure

```
open-energy-be/
app/
  api/
    v1/
      data_files.py
      energy.py
      energy_mix.py
      energy_overview.py
      energy_ui.py
      private_suppliers.py
      smp.py
      smp_production_vs_marginal_price.py
      switching_requests.py
  config.py
  main.py
  security.py
  services/
    data_file_manager.py
    energy_mix_processor.py
    energy_mix_service.py
    energy_overview_service.py
    energy_processor.py
    energy_service.py
    noga_service.py
    private_suppliers_service.py
    smp_processor.py
    smp_production_service.py
    smp_service.py
    switching_requests_service.py
    user_service.py
  utils/
    date_utils.py
    response_formatter.py
data_extractor.py
data_files/
  Files_Netunei_hashmal_mp_niyud_05-12-2025.csv
  Files_Netunei_hashmal_mp_tzarchan_05-12-2025.csv
docker-compose.yml
Dockerfile
README.md
requirements.txt
```

---

## Getting Started

### Prerequisites

**Using Docker (Recommended):**

- Docker Desktop installed and running

**. Access the API:**

- **Swagger UI:** http://127.0.0.1:8000/docs
- **ReDoc:** http://127.0.0.1:8000/redoc

### Running with Docker

**1. Build the image:**

```powershell
docker build -t open-energy-be .
```

**2. Run the container:**

```powershell
docker run -d -p 8000:8000 `
  -e NOGA_API_TOKEN="your-token-here" `
  --name open-energy-app `
  open-energy-be
```

**3. Access at:** http://localhost:8000/docs

### Running with Docker Compose

```powershell
docker-compose up -d
```

---

## Configuration

**Setting in .env file (create in project root):**

```
NOGA_API_TOKEN
SMP_TOKEN
INTERNAL_API_KEY
PROXY_URL
```

**Using with Docker:**

```powershell
docker run -d -p 8000:8000 -e NOGA_API_TOKEN="token" open-energy-be
```

---

## API Documentation

### Interactive Docs

Once running, access interactive documentation at:

- **Swagger UI (Recommended):** http://localhost:8000/docs

  - Try endpoints directly in browser
  - See request/response schemas
  - Auto-populated examples

- **ReDoc (Alternative):** http://localhost:8000/redoc
  - Clean, detailed API reference
  - Good for reading specifications

---

## Complete Endpoint Reference

All date parameters use `YYYY-MM-DD` format. Omitted dates default to sensible ranges (usually last 365 days or last 1 day).

### 1. Energy Production Mix Endpoints

#### `GET /api/v1/energy/production-mix`

**Description:** Aggregated electricity production mix by source type (fossil, renewable, other)

**Query Parameters:**

- `start_date` (optional, YYYY-MM-DD)
- `end_date` (optional, YYYY-MM-DD)

**Response (200 OK):**

```json
{
  "start_date": "2025-11-05",
  "end_date": "2025-12-05",
  "filter": "month",
  "level1": {
    "non_renewables": 4848764.2775,
    "renewables": 746006.005,
    "other": 145755.1475
  },
  "level2": {
    "non_renewables": {
      "coal": 426128.9025,
      "natural_gas": 4422635.375,
      "diesel": 0
    },
    "renewables": {
      "photovoltaic": 581749.4041,
      "biogas": 6464.5783,
      "wind": 69364.7841,
      "solar_thermal": 31179.23,
      "pv_storage": 57248.0083
    },
    "other": {
      "other": 19267.07,
      "pumped_storage": 126488.0775
    }
  },
  "total_generation": 5740525.43,
  "renewable_share_percent": 13,
  "categories": [
    {
      "category_name": "renewables",
      "total_value": 746006.005,
      "sub_categories": [
        {
          "name": "photovoltaic",
          "value": 581749.4041
        }
      ]
    }
  ],
  "tooltip": "The pie chart shows Israel's electricity generation mix..."
}
```

---

#### `GET /api/v1/production-mix/ui`

**Description:** Production mix data formatted for UI components with color codes

**Query Parameters:**

- `start_date` (optional)
- `end_date` (optional)

**Response:** Production mix with hex colors for each energy source

```json
{
  "level1": {...},
  "level2": {
    "Renewables": [
      {"name": "photoVoltaic", "value": 200.0, "color": "#FFD700"},
      {"name": "wind", "value": 30.2, "color": "#00BFFF"}
    ]
  },
  "percentages": {...},
  "total_production": 1501.0
}
```

---

#### `GET /api/v1/energy/production-mix/export`

**Description:** Export production mix to Excel file

**Query Parameters:**

- `start_date` (optional)
- `end_date` (optional)

**Response:** Streamed Excel file (`production_mix.xlsx`) with summary and detailed sheets

---

### 2. Energy Overview Endpoints

#### `GET /api/v1/energy/overview`

**Description:** Hierarchical breakdown of energy sources with percentages

**Query Parameters:**

- `start_date` (optional)
- `end_date` (optional)

**Response (200 OK):**

```json
{
  "start_date": "2024-12-05",
  "end_date": "2025-12-05",
  "filter": "year",
  "total": 80454683.55,
  "level1": {
    "fossil_energy": 66691009.15,
    "renewable_energy": 12193200.52,
    "other": 1570473.88
  },
  "level2": {
    "fossil_energy": {
      "coal": 8057076.35,
      "natural_gas": 58628439.92,
      "diesel": 5492.87
    },
    "renewable_energy": {
      "photovoltaic": 10518690.13,
      "biogas": 83390.6,
      "wind": 840861.71,
      "solar": 750258.06
    }
  },
  "renewable_generation": 12193200.52,
  "renewable_share_percent": 15.16,
  "category_percentages": {
    "renewables": 15.16,
    "non_renewables": 82.89,
    "other": 1.95
  },
  "categories": [...]
}
```

---

#### `GET /api/v1/energy/overview/details`

**Description:** Detailed hierarchical view for deep analysis

**Response:** Same structure as `/overview` with additional details

---

#### `GET /api/v1/energy/overview/export`

**Description:** Export energy overview to Excel

**Response:** Streamed Excel file (`energy_overview.xlsx`)

---

### 3. System Marginal Price (SMP) Endpoints

#### `GET /api/v1/energy/smp`

**Description:** System Marginal Price (electricity market clearing price) data

**Query Parameters:**

- `start_date` (optional, defaults to last 1 day)
- `end_date` (optional)

**Response (200 OK):**

```json
{
  "start_date": "2023-10-15",
  "end_date": "2023-10-15",
  "view": "day",
  "chart_with_constraints": [
    {
      "timestamp": "2023-10-15T00:00:00",
      "price": 425.5
    }
  ],
  "chart_without_constraints": [
    {
      "timestamp": "2023-10-15T00:00:00",
      "price": 420
    }
  ],
  "min_price": 380.5,
  "max_price": 510.3,
  "avg_price": 445.2
}
```

---

#### `GET /api/v1/energy/smp-production-vs-marginal-price`

**Description:** Correlate electricity production with marginal pricing for market analysis

**Query Parameters:**

- `start_date` (optional)
- `end_date` (optional)

**Response (200 OK):**

```json
{
  "start_date": "2023-10-15",
  "end_date": "2023-10-15",
  "view": "day",
  "smp_series": [
    {
      "timestamp": "2023-10-15T00:00:00",
      "smp": 425.5
    }
  ],
  "net_demand_series": [
    {
      "timestamp": "2023-10-15T00:00:00",
      "net_demand": 3200.1
    }
  ],
  "monthly_average": [{"period": "2023-10", "avg_smp": 410}]
}
```

---

### 4. Private Suppliers Endpoints

#### `GET /api/v1/private-supplier-connected-consumers`

**Description:** Monthly time series of consumers connected to private electricity suppliers

**Query Parameters:**

- `start_date` (optional, format: MM-YYYY)
- `end_date` (optional, format: MM-YYYY)

**Response (200 OK):**

```json
{
  "start_date": "2024-11-01",
  "end_date": "2025-10-01",
  "unit": "count",
  "data": [
    {
      "month": "2024-11",
      "total_consumers": 319380,
      "new_additions": 74192
    },
    { "...": "..." }
  ],
  "segments": {
    "location": [
      {
        "month": "2024-11",
        "location": "existing_regulation",
        "total_consumers": 139323
      },
      { "...": "..." }
    ]
  }
}
```

---

#### `GET /api/v1/private-supplier-connected-consumers/export`

**Description:** Export private suppliers data to Excel

**Query Parameters:**

- `start_date` (optional)
- `end_date` (optional)

**Response:** Streamed Excel file (`private_suppliers_consumers.xlsx`)

---

#### `GET /api/v1/private-supplier-connected-consumers/download-source`

**Description:** Download raw source CSV file with all private supplier data

**Response:** CSV file download

---

### 5. Consumer Switching Requests Endpoints

#### `GET /api/v1/switching-requests`

**Description:** Consumer electricity supplier switching request data as residential and non_residential

**Query Parameters:**

- residential and non_residential

**Response (200 OK):**

```json
{
  "start_year": 2023,
  "end_year": 2023,
  "total_requests": 45000,
  "by_quarter": [
    { "quarter": "Q1", "requests": 10500 },
    { "quarter": "Q2", "requests": 11200 },
    { "quarter": "Q3", "requests": 11800 },
    { "quarter": "Q4", "requests": 11500 }
  ],
  "by_supplier": [
    { "supplier": "Supplier A", "requests": 22000 },
    { "supplier": "Supplier B", "requests": 18000 },
    { "supplier": "Supplier C", "requests": 5000 }
  ],
  "by_segment": [
    { "segment": "Residential", "requests": 35000 },
    { "segment": "Commercial", "requests": 8000 },
    { "segment": "Industrial", "requests": 2000 }
  ],
  "trend": "increasing"
}
```

---

#### `GET /api/v1/switching-requests/export`

**Description:** Export switching request data to Excel

**Query Parameters:**

- `year` (optional)

**Response:** Streamed Excel file (`switching_requests_YYYY.xlsx`)

---

## Architecture

### Data Flow Diagram

```
┌──────────────────────────────────────────────────────┐
│           Client/Frontend Application                │
└──────────────────────┬───────────────────────────────┘
                       │ HTTP Request (GET)
                       ▼
┌──────────────────────────────────────────────────────┐
│              FastAPI Application                     │
├──────────────────────────────────────────────────────┤
│                                                      │
│  API Routes (app/api/v1/)                            │
│  ├─ energy.py                                        │
│  ├─ energy_overview.py                               │
│  ├─ smp.py                                           │
│  ├─ private_suppliers.py                             │
│  └─ switching_requests.py                            │
│           │                                          │
│           ▼                                          │
│  Services Layer (app/services/)                      │
│  ├─ noga_service.py (fetch data)                     │
│  ├─ energy_mix_processor.py (process)                │
│  ├─ smp_processor.py (calculate)                     │
│  └─ *_service.py (aggregate)                         │
│           │                                          │
│           ▼                                          │
│  Utils (app/utils/)                                  │
│  ├─ date_utils.py                                    │
│  └─ response_formatter.py                            │
└──────────────────────┬───────────────────────────────┘
                       │ HTTP Response (JSON/Excel)
                       ▼
┌──────────────────────────────────────────────────────┐
│           External Data Sources                      │
│  ├─ NOGA API (production mix, pricing)               │
│  ├─ CSV Files (private suppliers, switching)         │
│  └─ Mock Services (testing)                          │
└──────────────────────────────────────────────────────┘
```

### Processing Pipeline

1. **Request** — Client calls an API endpoint with optional date range
2. **Route Handler** — API endpoint receives and validates parameters
3. **Service Fetch** — Service queries NOGA or loads local data
4. **Transform** — Raw data converted to common format (5-min → hourly)
5. **Aggregate** — Data grouped into categories and levels
6. **Calculate** — Compute metrics (totals, percentages, trends)
7. **Format** — Structure response as JSON or Excel
8. **Return** — Send response to client

---

## Development & Extension

### Adding a New Endpoint

**1. Create API file** (`app/api/v1/new_feature.py`):

```python
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v1/new-feature", tags=["New Feature"])

@router.get("/")
async def get_new_data(start_date: str = None, end_date: str = None):
    """Endpoint description."""
    try:
        # Your logic here
        return {"data": "result"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**2. Create Service** (`app/services/new_feature_service.py`):

```python
class NewFeatureService:
    @staticmethod
    async def fetch_and_process(start, end):
        # Fetch, process, return data
        pass
```

**3. Register in** `app/main.py`:

```python
from app.api.v1 import new_feature
app.include_router(new_feature.router)
```

### Testing

```powershell
# Install pytest
pip install pytest pytest-asyncio

# Run all tests
pytest

# Run specific test
pytest tests/test_energy.py -v

# Run with coverage
pytest --cov=app
```

### Code Style

- Follow PEP 8 guidelines
- Use type hints in all functions
- Document with docstrings
- Use meaningful variable names

---

## Error Handling

The API returns standard HTTP status codes:

| Code | Meaning      | Example                    |
| ---- | ------------ | -------------------------- |
| 200  | Success      | Data returned successfully |
| 400  | Bad Request  | Invalid date format        |
| 404  | Not Found    | Endpoint doesn't exist     |
| 500  | Server Error | Internal processing failed |
| 502  | Bad Gateway  | External API unreachable   |

**Example error response:**

```json
{
  "detail": "Failed to fetch SMP data: NOGA API unreachable"
}
```

---

## Troubleshooting

### Module Not Found Errors

**Solution:** Activate virtual environment and install dependencies:

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### NOGA API Unreachable

**Solution:**

- Check `NOGA_API_TOKEN` is set correctly
- Verify network connectivity
- Check NOGA service status

### Date Parsing Errors

**Solution:** Use `YYYY-MM-DD` format for all date parameters

### PowerShell Execution Policy Error

**Solution:**

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Port Already in Use

**Solution:** Use different port:

```powershell
uvicorn app.main:app --port 8001
```

---

## Deployment

### Production Docker Deployment

```powershell
docker run -d \
  --restart always \
  -p 8000:8000 \
  -e NOGA_API_TOKEN="production-token" \
  --name open-energy-prod \
  open-energy-be
```

### Using Docker Compose

```bash
docker-compose up -d
```

### Environment Configuration for Production

- Set actual `NOGA_API_TOKEN`, `PROXY_URL`, `INTERNAL_API_KEY`, `SMP_TOKEN`

---