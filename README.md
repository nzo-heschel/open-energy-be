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
      api_catalog.py
      data_files.py
      energy.py
      energy_mix.py
      energy_overview.py
      energy_ui.py
      private_suppliers.py
      renewable_mix.py
      renewable_potential_industry.py
      renewable_transition.py
      smp.py
      smp_production_vs_marginal_price.py
      switching_requests.py
  config.py
  main.py
  security.py
  services/
    data_file_manager.py
    demand_service.py
    energy_mix_processor.py
    energy_mix_service.py
    energy_overview_service.py
    energy_processor.py
    energy_service.py
    noga_mock_service.py
    noga_service.py
    private_suppliers_service.py
    renewable_mix_service.py
    renewable_potential_industry_service.py
    renewable_transition_service.py
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
│  └─ switching_requests.py
|           │
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

## Complete Endpoint Reference

All date parameters use `YYYY-MM-DD` format. Omitted dates default to sensible ranges (usually last 365 days or last 1 day).

### 1. Energy Overview Endpoints

#### `GET /api/v1/energy/overview`

**Description:** Hierarchical breakdown of energy sources with percentages

**Query Parameters:**

- `start_date` (optional)
- `end_date` (optional)

**Response (200 OK):**

```json
{
  "start_date": "2024-12-17",
  "end_date": "2025-12-17",
  "filter": "year",
  "categories": [
    {
      "category_name": "renewables",
      "total_value": 12137497.925833311,
      "sub_categories": [
        {
          "sub_category_name": "photo_voltaic",
          "value": 10480818.796666665
        },
        {
          "sub_category_name": "biogas",
          "value": 82941.32000000004
        },
        {
          "sub_category_name": "wind",
          "value": 832359.5816666678
        },
        {
          "sub_category_name": "solar_thermal",
          "value": 741378.2274999794
        },
        {
          "sub_category_name": "pv_storage",
          "value": 0
        }
      ]
    },
    {
      "category_name": "non_renewables",
      "total_value": 66823638.22416678,
      "sub_categories": [
        {
          "sub_category_name": "coal",
          "value": 7905235.079166689
        },
        {
          "sub_category_name": "natural_gas",
          "value": 58912910.27250009
        },
        {
          "sub_category_name": "diesel",
          "value": 5492.8725
        }
      ]
    },
    {
      "category_name": "other",
      "total_value": 1586189.4508333367,
      "sub_categories": [
        {
          "sub_category_name": "other",
          "value": 265945.2974999997
        },
        {
          "sub_category_name": "pumped_storage",
          "value": 1320244.153333337
        }
      ]
    }
  ],
  "category_percentages": {
    "renewables": 15.07,
    "non_renewables": 82.96,
    "other": 1.97
  },
  "tooltip": "The chart shows Israel's electricity generation mix and illustrates the different energy sources: fossil (coal, natural gas, diesel) and renewables (PV, biogas, wind, solar). Data updated hourly from NOGA.",
  "total": 80547325.60083343,
  "level1": {
    "fossil_energy": 66823638.22416678,
    "renewable_energy": 12137497.925833311,
    "other": 1586189.4508333367
  },
  "level2": {
    "fossil_energy": {
      "coal": 7905235.079166689,
      "natural_gas": 58912910.27250009,
      "diesel": 5492.8725
    },
    "renewable_energy": {
      "photovoltaic": 10480818.796666665,
      "biogas": 82941.32000000004,
      "wind": 832359.5816666678,
      "solar": 741378.2274999794
    },
    "other": {
      "other": 265945.2974999997,
      "pumped_storage": 1320244.153333337
    }
  },
  "renewable_generation": 12137497.925833311,
  "renewable_share_percent": 15.07
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


### 2. Energy Production Mix Endpoints

#### `GET /api/v1/energy/production-mix`

**Description:** Aggregated electricity production mix by source type (fossil, renewable, other)

**Query Parameters:**

- `start_date` (optional, YYYY-MM-DD)
- `end_date` (optional, YYYY-MM-DD)
- `granularity` (optional, Day, Month or Year)

**Response (200 OK):**

```json
{
  "start_date": "2025-12-16",
  "end_date": "2025-12-17",
  "filter": "day",
  "level1": {
    "Non-renewables": 170190.43916666668,
    "Renewables": 22384.326666666664,
    "Other": 4002.075
  },
  "level2": {
    "Non-renewables": {
      "coal": 12618.000000000002,
      "natural_gas": 157572.43916666668,
      "diesel": 0
    },
    "Renewables": {
      "photoVoltaic": 18484.755,
      "biogas": 208.82250000000002,
      "wind": 888.8866666666667,
      "solar_thermal": 854.3849999999998,
      "pv_storage": 1947.4775000000004
    },
    "Other": {
      "other": 555.6383333333333,
      "pumped_storage": 3446.4366666666665
    }
  },
  "total_generation": 196576.84083333335,
  "renewable_share_percent": 11.39,
  "categories": [
    {
      "category_name": "renewables",
      "total_value": 22384.326666666664,
      "sub_categories": [
        {
          "sub_category_name": "photo_voltaic",
          "value": 18484.755
        },
        {
          "sub_category_name": "biogas",
          "value": 208.82250000000002
        },
        {
          "sub_category_name": "wind",
          "value": 888.8866666666667
        },
        {
          "sub_category_name": "solar_thermal",
          "value": 854.3849999999998
        },
        {
          "sub_category_name": "pv_storage",
          "value": 1947.4775000000004
        }
      ]
    },
    {
      "category_name": "non_renewables",
      "total_value": 170190.43916666668,
      "sub_categories": [
        {
          "sub_category_name": "coal",
          "value": 12618.000000000002
        },
        {
          "sub_category_name": "natural_gas",
          "value": 157572.43916666668
        },
        {
          "sub_category_name": "diesel",
          "value": 0
        }
      ]
    },
    {
      "category_name": "other",
      "total_value": 4002.075,
      "sub_categories": [
        {
          "sub_category_name": "other",
          "value": 555.6383333333333
        },
        {
          "sub_category_name": "pumped_storage",
          "value": 3446.4366666666665
        }
      ]
    }
  ],
  "series_granularity": "day",
  "series_units": "MW averaged from 5-minute NOGA samples (summed per bucket).",
  "series": [
    {
      "period": "2025-12-16T17:00",
      "label": "17:00",
      "non_renewables_mw": 3380.67,
      "renewables_mw": 165.19,
      "other_mw": 188.1,
      "total_mw": 3733.96,
      "non_renewables_share_percent": 90.54,
      "renewables_share_percent": 4.42,
      "other_share_percent": 5.04,
      "renewable_share_percent": 4.42
    },
    {
      "period": "2025-12-16T18:00",
      "label": "18:00",
      "non_renewables_mw": 10200.81,
      "renewables_mw": 491.89,
      "other_mw": 570.06,
      "total_mw": 11262.77,
      "non_renewables_share_percent": 90.57,
      "renewables_share_percent": 4.37,
      "other_share_percent": 5.06,
      "renewable_share_percent": 4.37
    },
    {
      "period": "2025-12-16T19:00",
      "label": "19:00",
      "non_renewables_mw": 10201.71,
      "renewables_mw": 403.98,
      "other_mw": 564.49,
      "total_mw": 11170.18,
      "non_renewables_share_percent": 91.33,
      "renewables_share_percent": 3.62,
      "other_share_percent": 5.05,
      "renewable_share_percent": 3.62
    },
    {
      "period": "2025-12-16T20:00",
      "label": "20:00",
      "non_renewables_mw": 10059.48,
      "renewables_mw": 367.07,
      "other_mw": 535.35,
      "total_mw": 10961.89,
      "non_renewables_share_percent": 91.77,
      "renewables_share_percent": 3.35,
      "other_share_percent": 4.88,
      "renewable_share_percent": 3.35
    },
    {
      "period": "2025-12-16T21:00",
      "label": "21:00",
      "non_renewables_mw": 8967.46,
      "renewables_mw": 261.89,
      "other_mw": 464.93,
      "total_mw": 9694.27,
      "non_renewables_share_percent": 92.5,
      "renewables_share_percent": 2.7,
      "other_share_percent": 4.8,
      "renewable_share_percent": 2.7
    },
    {
      "period": "2025-12-16T22:00",
      "label": "22:00",
      "non_renewables_mw": 9397.69,
      "renewables_mw": 108.01,
      "other_mw": 500.22,
      "total_mw": 10005.93,
      "non_renewables_share_percent": 93.92,
      "renewables_share_percent": 1.08,
      "other_share_percent": 5,
      "renewable_share_percent": 1.08
    },
    {
      "period": "2025-12-16T23:00",
      "label": "23:00",
      "non_renewables_mw": 8495.65,
      "renewables_mw": 74.85,
      "other_mw": 473.29,
      "total_mw": 9043.79,
      "non_renewables_share_percent": 93.94,
      "renewables_share_percent": 0.83,
      "other_share_percent": 5.23,
      "renewable_share_percent": 0.83
    },
    {
      "period": "2025-12-17T00:00",
      "label": "00:00",
      "non_renewables_mw": 7726.21,
      "renewables_mw": 78.31,
      "other_mw": 329.26,
      "total_mw": 8133.78,
      "non_renewables_share_percent": 94.99,
      "renewables_share_percent": 0.96,
      "other_share_percent": 4.05,
      "renewable_share_percent": 0.96
    },
    {
      "period": "2025-12-17T01:00",
      "label": "01:00",
      "non_renewables_mw": 7443.23,
      "renewables_mw": 92.8,
      "other_mw": 32.17,
      "total_mw": 7568.2,
      "non_renewables_share_percent": 98.35,
      "renewables_share_percent": 1.23,
      "other_share_percent": 0.43,
      "renewable_share_percent": 1.23
    },
    {
      "period": "2025-12-17T02:00",
      "label": "02:00",
      "non_renewables_mw": 7374.09,
      "renewables_mw": 131.78,
      "other_mw": 24.5,
      "total_mw": 7530.37,
      "non_renewables_share_percent": 97.92,
      "renewables_share_percent": 1.75,
      "other_share_percent": 0.33,
      "renewable_share_percent": 1.75
    },
    {
      "period": "2025-12-17T03:00",
      "label": "03:00",
      "non_renewables_mw": 7235.39,
      "renewables_mw": 149.48,
      "other_mw": 24.18,
      "total_mw": 7409.05,
      "non_renewables_share_percent": 97.66,
      "renewables_share_percent": 2.02,
      "other_share_percent": 0.33,
      "renewable_share_percent": 2.02
    },
    {
      "period": "2025-12-17T04:00",
      "label": "04:00",
      "non_renewables_mw": 7402.28,
      "renewables_mw": 93.32,
      "other_mw": 26.04,
      "total_mw": 7521.64,
      "non_renewables_share_percent": 98.41,
      "renewables_share_percent": 1.24,
      "other_share_percent": 0.35,
      "renewable_share_percent": 1.24
    },
    {
      "period": "2025-12-17T05:00",
      "label": "05:00",
      "non_renewables_mw": 7796.2,
      "renewables_mw": 72.28,
      "other_mw": 27.96,
      "total_mw": 7896.45,
      "non_renewables_share_percent": 98.73,
      "renewables_share_percent": 0.92,
      "other_share_percent": 0.35,
      "renewable_share_percent": 0.92
    },
    {
      "period": "2025-12-17T06:00",
      "label": "06:00",
      "non_renewables_mw": 8234.21,
      "renewables_mw": 45.11,
      "other_mw": 28.64,
      "total_mw": 8307.96,
      "non_renewables_share_percent": 99.11,
      "renewables_share_percent": 0.54,
      "other_share_percent": 0.34,
      "renewable_share_percent": 0.54
    },
    {
      "period": "2025-12-17T07:00",
      "label": "07:00",
      "non_renewables_mw": 8760.29,
      "renewables_mw": 296.45,
      "other_mw": 26.94,
      "total_mw": 9083.68,
      "non_renewables_share_percent": 96.44,
      "renewables_share_percent": 3.26,
      "other_share_percent": 0.3,
      "renewable_share_percent": 3.26
    },
    {
      "period": "2025-12-17T08:00",
      "label": "08:00",
      "non_renewables_mw": 8221.87,
      "renewables_mw": 1324.98,
      "other_mw": 28.79,
      "total_mw": 9575.65,
      "non_renewables_share_percent": 85.86,
      "renewables_share_percent": 13.84,
      "other_share_percent": 0.3,
      "renewable_share_percent": 13.84
    },
    {
      "period": "2025-12-17T09:00",
      "label": "09:00",
      "non_renewables_mw": 7683.81,
      "renewables_mw": 2588.65,
      "other_mw": 31.94,
      "total_mw": 10304.4,
      "non_renewables_share_percent": 74.57,
      "renewables_share_percent": 25.12,
      "other_share_percent": 0.31,
      "renewable_share_percent": 25.12
    },
    {
      "period": "2025-12-17T10:00",
      "label": "10:00",
      "non_renewables_mw": 6956.28,
      "renewables_mw": 3319.51,
      "other_mw": 26.99,
      "total_mw": 10302.79,
      "non_renewables_share_percent": 67.52,
      "renewables_share_percent": 32.22,
      "other_share_percent": 0.26,
      "renewable_share_percent": 32.22
    },
    {
      "period": "2025-12-17T11:00",
      "label": "11:00",
      "non_renewables_mw": 6605.39,
      "renewables_mw": 3561.3,
      "other_mw": 25.44,
      "total_mw": 10192.13,
      "non_renewables_share_percent": 64.81,
      "renewables_share_percent": 34.94,
      "other_share_percent": 0.25,
      "renewable_share_percent": 34.94
    },
    {
      "period": "2025-12-17T12:00",
      "label": "12:00",
      "non_renewables_mw": 6556.74,
      "renewables_mw": 3542.08,
      "other_mw": 26.25,
      "total_mw": 10125.07,
      "non_renewables_share_percent": 64.76,
      "renewables_share_percent": 34.98,
      "other_share_percent": 0.26,
      "renewable_share_percent": 34.98
    },
    {
      "period": "2025-12-17T13:00",
      "label": "13:00",
      "non_renewables_mw": 6774.2,
      "renewables_mw": 3360.23,
      "other_mw": 26.98,
      "total_mw": 10161.41,
      "non_renewables_share_percent": 66.67,
      "renewables_share_percent": 33.07,
      "other_share_percent": 0.27,
      "renewable_share_percent": 33.07
    },
    {
      "period": "2025-12-17T14:00",
      "label": "14:00",
      "non_renewables_mw": 4716.76,
      "renewables_mw": 1855.16,
      "other_mw": 19.54,
      "total_mw": 6591.47,
      "non_renewables_share_percent": 71.56,
      "renewables_share_percent": 28.14,
      "other_share_percent": 0.3,
      "renewable_share_percent": 28.14
    }
  ],
  "tooltip": "Israel's electricity generation mix. Time series points are aggregated by the chosen view (day=hourly, month=daily, year=monthly). Each point sums 5-minute samples, converts them to hourly averages, and reports renewable share."
}
```

---

#### `GET /api/v1/energy/production-mix`

**Description:** Production mix data

**Query Parameters:**

- `start_date` (optional)
- `end_date` (optional)

**Response:** Production mix for each energy source

```json
{
  "start_date": "2024-12-11",
  "end_date": "2024-12-12",
  "filter": "day",
  "level1": {
    "Non-renewables": 183995.4291666667,
    "Renewables": 18608.73416666667,
    "Other": 3045.853333333333
  },
  "level2": {
    "Non-renewables": {
      "coal": 27659.465833333332,
      "natural_gas": 156335.96333333338,
      "diesel": 0
    },
    "Renewables": {
      "photoVoltaic": 14896.114166666666,
      "biogas": 278.78083333333336,
      "wind": 1250.155,
      "solar_thermal": 969.4625,
      "pv_storage": 1214.2216666666666
    },
    "Other": {
      "other": 687.1691666666667,
      "pumped_storage": 2358.6841666666664
    }
  },
  "total_generation": 205650.0166666667,
  "renewable_share_percent": 9.05,
  "categories": [
    {
      "category_name": "renewables",
      "total_value": 18608.73416666667,
      "sub_categories": [
        {
          "sub_category_name": "photo_voltaic",
          "value": 14896.114166666666
        },
        {
          "sub_category_name": "biogas",
          "value": 278.78083333333336
        },
        {
          "sub_category_name": "wind",
          "value": 1250.155
        },
        {
          "sub_category_name": "solar_thermal",
          "value": 969.4625
        },
        {
          "sub_category_name": "pv_storage",
          "value": 1214.2216666666666
        }
      ]
    },
    {
      "category_name": "non_renewables",
      "total_value": 183995.4291666667,
      "sub_categories": [
        {
          "sub_category_name": "coal",
          "value": 27659.465833333332
        },
        {
          "sub_category_name": "natural_gas",
          "value": 156335.96333333338
        },
        {
          "sub_category_name": "diesel",
          "value": 0
        }
      ]
    },
    {
      "category_name": "other",
      "total_value": 3045.853333333333,
      "sub_categories": [
        {
          "sub_category_name": "other",
          "value": 687.1691666666667
        },
        {
          "sub_category_name": "pumped_storage",
          "value": 2358.6841666666664
        }
      ]
    }
  ],
  "tooltip": "The pie chart shows Israel's electricity generation mix and illustrates the different energy sources: fossil (coal, natural gas, diesel), renewables (photovoltaic, biogas, wind, solar-thermal, photovoltaic with storage), and other (other, pumped storage). Data are updated hourly from the NOGA system operator."
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


### 3. System Marginal Price (SMP) Endpoints

#### `GET /api/v1/energy/smp`

**Description:** System Marginal Price (electricity market clearing price) data

**Query Parameters:**

- `start_date` (optional, defaults to last 1 day)
- `end_date` (optional)

**Response (200 OK):**

```json
{
  "daily_average": [
    {
      "period": "2025-12-16",
      "price_with_constraints": 125.04812500000001,
      "price_without_constraints": 106.55854166666664,
      "net_demand": 9127.322708333331
    },
    {
      "period": "2025-12-17",
      "price_with_constraints": 139.42812499999997,
      "price_without_constraints": 131.58166666666668,
      "net_demand": 9328.587291666667
    }
  ],
  "monthly_average": [
    {
      "period": "2025-12",
      "price_with_constraints": 132.23812499999997,
      "price_without_constraints": 119.07010416666672,
      "net_demand": 9227.954999999996
    }
  ],
  "chart_without_constraints": [
    {
      "timestamp": "2025-12-16T00:00:00",
      "price": 86.2
    },
    {
      "timestamp": "2025-12-17T21:00:00",
      "price": 119.83
    },
    {
      "timestamp": "2025-12-17T21:30:00",
      "price": 104.18
    },
    {
      "timestamp": "2025-12-17T22:00:00",
      "price": 145.5
    },
    {
      "timestamp": "2025-12-17T22:30:00",
      "price": 192.53
    },
    {
      "timestamp": "2025-12-17T23:00:00",
      "price": 192.7
    },
    {
      "timestamp": "2025-12-17T23:30:00",
      "price": 181.36
    }
  ],
  "chart_with_constraints": [
    {
      "timestamp": "2025-12-16T08:30:00",
      "price": 78.57
    },
    {
      "timestamp": "2025-12-16T09:00:00",
      "price": 82.34
    },
    {
      "timestamp": "2025-12-16T09:30:00",
      "price": 78.57
    },
    {
      "timestamp": "2025-12-16T10:00:00",
      "price": 77.26
    },
    {
      "timestamp": "2025-12-16T10:30:00",
      "price": 75.97
    },
    {
      "timestamp": "2025-12-16T11:00:00",
      "price": 78.55
    },
    {
      "timestamp": "2025-12-16T11:30:00",
      "price": 86.5
    },
    {
      "timestamp": "2025-12-17T23:00:00",
      "price": 200
    },
    {
      "timestamp": "2025-12-17T23:30:00",
      "price": 119.83
    }
  ],
  "correlation_view": [
    {
      "timestamp": "2025-12-16T00:00:00",
      "net_demand": 8372.21,
      "price": 82.34
    },
    {
      "timestamp": "2025-12-16T00:30:00",
      "net_demand": 7887,
      "price": 75.97
    },
    {
      "timestamp": "2025-12-16T01:00:00",
      "net_demand": 7554.63,
      "price": 75.96
    },
    {
      "timestamp": "2025-12-16T09:00:00",
      "net_demand": 9123.66,
      "price": 82.34
    },
    {
      "timestamp": "2025-12-16T09:30:00",
      "net_demand": 9176.15,
      "price": 78.57
    },
    
  ],
  "samples": [
    {
      "timestamp": "2025-12-16T00:00:00",
      "price_with_constraints": 82.34,
      "price_without_constraints": 86.2,
      "net_demand": 8372.21,
      "date": "16-12-2025"
    },
    {
      "timestamp": "2025-12-16T02:00:00",
      "price_with_constraints": 77.25,
      "price_without_constraints": 89.32,
      "net_demand": 7040.23,
      "date": "16-12-2025"
    },
    {
      "timestamp": "2025-12-16T02:30:00",
      "price_with_constraints": 82.34,
      "price_without_constraints": 87.3,
      "net_demand": 6900.97,
      "date": "16-12-2025"
    },
    {
      "timestamp": "2025-12-16T03:00:00",
      "price_with_constraints": 82.34,
      "price_without_constraints": 87.3,
      "net_demand": 6791.46,
      "date": "16-12-2025"
    },
   
  ],
  "view": "day",
  "start_date": "2025-12-16",
  "end_date": "2025-12-17"
}
```

---

### 4. SMP Production vs Marginal Price Endpoint

#### `GET /api/v1/energy/smp-production-vs-marginal-price`

**Description:** Correlate electricity production with marginal pricing for market analysis

**Query Parameters:**

- `start_date` (optional)
- `end_date` (optional)

**Response (200 OK):**

```json
{
  "start_date": "2025-12-16",
  "end_date": "2025-12-17",
  "view": "day",
  "smp_series": [
    {
      "timestamp": "2025-12-16T00:00:00",
      "smp": 82.34
    },
    {
      "timestamp": "2025-12-16T00:30:00",
      "smp": 75.97
    },
    {
      "timestamp": "2025-12-17T23:00:00",
      "smp": 200
    },
    {
      "timestamp": "2025-12-17T23:30:00",
      "smp": 119.83
    }
  ],
  "net_demand_series": [
    {
      "timestamp": "2025-12-16T13:00:00",
      "net_demand": 9306.82
    },
    {
      "timestamp": "2025-12-16T13:30:00",
      "net_demand": 9462.98
    },
    {
      "timestamp": "2025-12-16T14:00:00",
      "net_demand": 9598.24
    },
    {
      "timestamp": "2025-12-17T03:00:00",
      "net_demand": 6815.21
    },
    {
      "timestamp": "2025-12-17T03:30:00",
      "net_demand": 6785.95
    }
  ],
  "combined_series": [
    {
      "timestamp": "2025-12-16T00:00:00",
      "smp": 82.34,
      "net_demand": 8372.21
    },
    {
      "timestamp": "2025-12-16T00:30:00",
      "smp": 75.97,
      "net_demand": 7887
    },
    {
      "timestamp": "2025-12-17T23:30:00",
      "smp": 119.83,
      "net_demand": 8959
    }
  ],
  "correlation": [
    {
      "smp": 82.34,
      "net_demand": 8372.21
    },
    {
      "smp": 75.97,
      "net_demand": 7887
    },
    {
      "smp": 75.96,
      "net_demand": 7554.63
    },
    {
      "smp": 75.96,
      "net_demand": 7300.21
    }
  ],
  "daily_smp": [
    {
      "date": "2025-12-16",
      "daily_smp_avg": 125.04812500000001
    },
    {
      "date": "2025-12-17",
      "daily_smp_avg": 139.42812499999997
    }
  ],
  "daily_average": [
    {
      "period": "2025-12-16",
      "avg_smp": 125.04812500000001
    },
    {
      "period": "2025-12-17",
      "avg_smp": 139.42812499999997
    }
  ],
  "monthly_average": [
    {
      "period": "2025-12",
      "avg_smp": 132.23812499999997
    }
  ]
}
```

---

### 5. Private Suppliers Endpoints

#### `GET /api/v1/private-supplier-connected-consumers`

**Description:** Monthly time series of consumers connected to private electricity suppliers

**Query Parameters:**

- `start_date` (optional, format: MM-YYYY)
- `end_date` (optional, format: MM-YYYY)

**Response (200 OK):**

```json
{
  "start_date": "2024-12-01",
  "end_date": "2025-11-01",
  "unit": "count",
  "labels": {
    "month": "Month",
    "total_consumers": "Total Consumers",
    "new_additions": "New Additions"
  },
  "data": [
    {
      "month": "2024-12",
      "total_consumers": 375904,
      "new_additions": 56524
    },
    {
      "month": "2025-01",
      "total_consumers": 422893,
      "new_additions": 46989
    },
    {
      "month": "2025-10",
      "total_consumers": 852353,
      "new_additions": 51242
    },
    {
      "month": "2025-11",
      "total_consumers": 888882,
      "new_additions": 36529
    }
  ],
  "segments": {
    "location": [
      {
        "month": "2024-12",
        "location": "existing_regulation",
        "total_consumers": 172587,
        "new_additions": 33264
      },
      {
        "month": "2025-01",
        "location": "existing_regulation",
        "total_consumers": 195807,
        "new_additions": 23220
      },
      {
        "month": "2025-11",
        "location": "competitive_supply",
        "total_consumers": 416391,
        "new_additions": 9576
      }
    ],
    "sector": [
      {
        "month": "2024-12",
        "sector": "residential",
        "total_consumers": 328797,
        "new_additions": 52395
      },
      {
        "month": "2025-01",
        "sector": "residential",
        "total_consumers": 368627,
        "new_additions": 39830
      },
      {
        "month": "2025-11",
        "sector": "non_residential",
        "total_consumers": 102546,
        "new_additions": 3742
      }
    ],
    "meter_type": [
      {
        "month": "2024-12",
        "meter_type": "virtual_suppliers",
        "total_consumers": 203317,
        "new_additions": 23260
      },
      {
        "month": "2025-01",
        "meter_type": "virtual_suppliers",
        "total_consumers": 227086,
        "new_additions": 23769
      },
      {
        "month": "2025-05",
        "meter_type": "suppliers_with_generation",
        "total_consumers": 299403,
        "new_additions": 27227
      },
      {
        "month": "2025-06",
        "meter_type": "suppliers_with_generation",
        "total_consumers": 335425,
        "new_additions": 36022
      },
      {
        "month": "2025-07",
        "meter_type": "suppliers_with_generation",
        "total_consumers": 375110,
        "new_additions": 39685
      },
      {
        "month": "2025-08",
        "meter_type": "suppliers_with_generation",
        "total_consumers": 392534,
        "new_additions": 17424
      },
      {
        "month": "2025-09",
        "meter_type": "suppliers_with_generation",
        "total_consumers": 413457,
        "new_additions": 20923
      },
      {
        "month": "2025-10",
        "meter_type": "suppliers_with_generation",
        "total_consumers": 445538,
        "new_additions": 32081
      },
      {
        "month": "2025-11",
        "meter_type": "suppliers_with_generation",
        "total_consumers": 472491,
        "new_additions": 26953
      }
    ]
  },
  "note": null
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

### 6. Consumer Switching Requests Endpoints

#### `GET /api/v1/switching-requests`

**Description:** Consumer electricity supplier switching request data as residential and non_residential

**Query Parameters:**

- residential and non_residential

**Response (200 OK):**

```json
{
  "filter": "residential",
  "unit": "count",
  "charts": {
    "by_customer_type": {
      "label": "Requests by customer type",
      "data": [
        {
          "label": "residential",
          "count": 291546
        }
      ]
    },
    "by_region": {
      "label": "Requests by region",
      "data": [
        {
          "label": "central",
          "count": 101375
        },
        {
          "label": "north",
          "count": 17656
        },
        {
          "label": "judea_samaria",
          "count": 16426
        }
      ]
    },
    "by_voltage": {
      "label": "Requests by voltage level",
      "data": [
        {
          "label": "low",
          "count": 291545
        },
        {
          "label": "high",
          "count": 1
        }
      ]
    },
    "by_meter_type": {
      "label": "Requests by meter type",
      "data": [
        {
          "label": "smart",
          "count": 202400
        },
        {
          "label": "basic",
          "count": 89146
        }
      ]
    },
    "by_regulation": {
      "label": "Requests by regulation",
      "data": [
        {
          "label": "existing_regulation",
          "count": 194741
        }
      ]
    },
    "by_connection_size": {
      "label": "Requests by connection size (GVA)",
      "data": [
        {
          "label": "0-0.05",
          "count": 290269
        }
      ]
    },
    "requests_by_status": {
      "label": "Requests by status",
      "data": []
    },
    "requests_by_rejection_reason": {
      "label": "Requests by rejection reason",
      "data": []
    },
    "total_requests": {
      "label": "Total requests",
      "data": [
        {
          "count": 291546
        }
      ]
    }
  }
}
```

---

#### `GET /api/v1/switching-requests/export`

**Description:** Export switching request data to Excel

**Query Parameters:**

- `year` (optional)

**Response:** Streamed Excel file (`switching_requests_YYYY.xlsx`)

---

### 7. Data Files Endpoints

#### `GET /api/v1/data-files/status`

**Description:** Returns freshness status for both datasets (private_suppliers and switching_requests).

**Response (200 OK):**

```json
{
  "private_suppliers": {
    "dataset": "private_suppliers",
    "status": "fresh",
    "age_days": 0.002003953148148148,
    "filename": "Files_Netunei_hashmal_mp_niyud_17-12-2025.csv"
  },
  "switching_requests": {
    "dataset": "switching_requests",
    "status": "fresh",
    "age_days": 0.00029118113425925926,
    "filename": "Files_Netunei_hashmal_mp_tzarchan_17-12-2025.csv"
  }
}
```

---

#### `POST /api/v1/data-files/upload`

**Description:** Uploads a new data file for a specific source (`private_suppliers` or `switching_requests`).

**Request Body:**

- `source`: `DataFileSource` (Enum: "private_suppliers" or "switching_requests")
- `file`: `UploadFile`

**Response (200 OK):**

```json
{
  "dataset": "private_suppliers",
  "stored_as": "some_file_name.csv",
  "message": "File uploaded. Re-run the target API to get the updated results."
}
```

---


### 8. API Catalog Endpoint


#### `GET /api/v1/apis/`

**Description:** Returns a catalog of all registered public-facing `/api` endpoints, useful for service discovery.

**Response (200 OK):**

```json
[
  {
    "title": "Energy Overview",
    "link": "/api/v1/energy/overview",
    "method": "GET",
    "description": "Hierarchical breakdown of generation by source...",
    "params": ["start_date (query, string, optional)", "end_date (query, string, optional)"],
    "sample_response": ["200"],
    "sample_response_body": { "...": "..." }
  }
]

```


---
### 9. Renewable Energy Endpoints

#### `GET /api/v1/renewables/production-mix`

**Description:** Provides a detailed view of renewable energy production, focusing on sources like solar, wind, and biogas.

**Query Parameters:**

- `start_date` (optional, YYYY-MM-DD)
- `end_date` (optional, YYYY-MM-DD)
- `category` (optional, one of: `solar`, `wind`, `other`)

**Response (200 OK):**

```json
{
  "start_date": "2025-11-05",
  "end_date": "2025-12-05",
  "category_filter": "solar",
  "series": [
    {
      "timestamp": "2025-11-05T00:00:00",
      "solar": 1234.5,
      "wind": 567.8,
      "other": 123.4
    }
  ],
  "totals": {
    "solar": 50000,
    "wind": 20000,
    "other": 5000
  }
}
```

---

#### `GET /api/v1/renewables/production-mix/export`

**Description:** Exports the renewable production mix data to an Excel file.

**Query Parameters:**

- `start_date` (optional, YYYY-MM-DD)
- `end_date` (optional, YYYY-MM-DD)
- `category` (optional, one of: `solar`, `wind`, `other`)

**Response:** Streamed Excel file (`renewable_production_mix.xlsx`).

---

#### `GET /api/v1/renewables/transition`

**Description:** Shows the daily total of renewable energy generation over a specified year, illustrating the transition towards renewables.

**Query Parameters:**

- `year` (optional, YYYY)

**Response (200 OK):**

```json
{
  "year": 2025,
  "series": [
    {
      "date": "2025-01-01",
      "total_generation": 15000
    }
  ],
  "totals": {
    "total_generation": 5475000
  }
}
```

---

#### `GET /api/v1/renewables/transition/export`

**Description:** Exports the renewable energy transition data to an Excel file.

**Query Parameters:**

- `year` (optional, YYYY)

**Response:** Streamed Excel file (`renewable_transition_YYYY.xlsx`).

---

#### `GET /api/v1/renewables/potential-by-industry`

**Description:** Details the potential for renewable energy production, categorized by industry type (solar, wind, biogas), with daily totals for a given year.

**Query Parameters:**

- `year` (optional, YYYY)

**Response (200 OK):**

```json
{
  "year": 2025,
  "series": [
    {
      "date": "2025-01-01",
      "solar": 10000,
      "wind": 4000,
      "biogas": 1000
    }
  ],
  "totals": {
    "solar": 3650000,
    "wind": 1460000,
    "biogas": 365000
  }
}
```

---

#### `GET /api/v1/renewables/potential-by-industry/export`

**Description:** Exports the renewable potential by industry data to an Excel file.

**Query Parameters:**

- `year` (optional, YYYY)

**Response:** Streamed Excel file (`renewable_potential_industry_YYYY.xlsx`).

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