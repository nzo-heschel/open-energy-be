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
  "start_date": "2025-01-06",
  "end_date": "2026-01-06",
  "filter": "year",
  "categories": [
    {
      "category_name": "renewables",
      "total_value": 12174782.644166637,
      "sub_categories": [
        {
          "sub_category_name": "photo_voltaic",
          "value": 10497594.438333333
        }
      ]
    }
  ],
  "category_percentages": {
    "renewables": 15.11,
    "non_renewables": 82.89,
    "other": 2.0
  },
  "tooltip": "The chart shows Israel's electricity generation mix and illustrates the different energy sources: non-renewables (coal, natural gas, diesel) and renewables (PV, biogas, wind, solar). Data updated hourly from NOGA.",
  "total": 80561884.0441667,
  "level1": {
    "non_renewables": 66778572.510000065,
    "renewables": 12174782.644166637,
    "other": 1608528.8900000043
  },
  "level2": {
    "non_renewables": {
      "coal": 7572099.632500037,
      "natural_gas": 59201014.21333336,
      "diesel": 5458.664166666667
    },
    "renewables": {
      "photovoltaic": 10497594.438333333,
      "biogas": 82409.06916666636,
      "wind": 858797.3016666656,
      "solar": 735981.8349999726
    },
    "other": {
      "other": 264540.0499999997,
      "pumped_storage": 1343988.8400000045
    }
  },
  "renewable_generation": 12174782.644166637,
  "renewable_share_percent": 15.11
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
  "start_date": "2025-01-06",
  "end_date": "2026-01-06",
  "filter": "year",
  "level1": {
    "Non-renewables": 66781294.08916675,
    "Renewables": 12176723.06749998,
    "Other": 1608640.2725000037
  },
  "level2": {
    "Non-renewables": {
      "coal": 7562174.278333369,
      "natural_gas": 59213661.14666672,
      "diesel": 5458.664166666667
    },
    "Renewables": {
      "photoVoltaic": 9685906.072500007,
      "biogas": 82452.64083333302,
      "wind": 857284.9949999995,
      "solar_thermal": 736795.7516666393,
      "pv_storage": 814283.6075000009
    },
    "Other": {
      "other": 264388.7949999998,
      "pumped_storage": 1344251.477500004
    }
  },
  "total_generation": 80566657.42916673,
  "renewable_share_percent": 15.11,
  "categories": [
    {
      "category_name": "renewables",
      "total_value": 12176723.06749998,
      "sub_categories": [
        {
          "sub_category_name": "photo_voltaic",
          "value": 9685906.072500007
        }
      ]
    }
  ],
  "series_granularity": "year",
  "series_units": "MW averaged from 5-minute NOGA samples (summed per bucket).",
  "series": [
    {
      "period": "2025-01",
      "label": "Jan 2025",
      "non_renewables_mw": 4609401.98,
      "renewables_mw": 609303.35,
      "other_mw": 93979.92,
      "total_mw": 5312685.25,
      "non_renewables_share_percent": 86.76,
      "renewables_share_percent": 11.47,
      "other_share_percent": 1.77,
      "renewable_share_percent": 11.47,
      "coal_mw": 757796.09,
      "natural_gas_mw": 3851605.88,
      "diesel_mw": 0.0,
      "photoVoltaic_mw": 477442.01,
      "biogas_mw": 6202.32,
      "wind_mw": 56104.92,
      "solar_thermal_mw": 29482.78,
      "pv_storage_mw": 40071.32,
      "other_source_mw": 19212.88,
      "pumped_storage_mw": 74767.04,
      "level2": {
        "Non-renewables": {
          "coal": 757796.09,
          "natural_gas": 3851605.88,
          "diesel": 0.0
        },
        "Renewables": {
          "photoVoltaic": 477442.01,
          "biogas": 6202.32,
          "wind": 56104.92,
          "solar_thermal": 29482.78,
          "pv_storage": 40071.32
        },
        "Other": {
          "other": 19212.88,
          "pumped_storage": 74767.04
        }
      }
    }
  ],
  "tooltip": "Israel's electricity generation mix. Time series points are aggregated by the chosen view (day=hourly, month=daily, year=monthly). Each point sums 5-minute samples, converts them to hourly averages, and reports renewable share."
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
      "period": "2026-01-05",
      "price_with_constraints": 166.88145833333334,
      "price_without_constraints": 125.8285416666667,
      "net_demand": 9285.825833333332
    }
  ],
  "monthly_average": [
    {
      "period": "2026-01",
      "price_with_constraints": 159.22885416666665,
      "price_without_constraints": 121.94937500000007,
      "net_demand": 9126.247708333334
    }
  ],
  "chart_without_constraints": [
    {
      "timestamp": "2026-01-05T00:00:00",
      "price": 181.89
    }
  ],
  "chart_with_constraints": [
    {
      "timestamp": "2026-01-05T00:00:00",
      "price": 181.89
    }
  ],
  "correlation_view": [
    {
      "timestamp": "2026-01-05T00:00:00",
      "net_demand": 8905.19,
      "price": 181.89
    }
  ],
  "samples": [
    {
      "timestamp": "2026-01-05T00:00:00",
      "price_with_constraints": 181.89,
      "price_without_constraints": 181.89,
      "net_demand": 8905.19,
      "date": "05-01-2026"
    }
  ],
  "view": "day",
  "start_date": "2026-01-05",
  "end_date": "2026-01-06"
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
  "start_date": "2026-01-05",
  "end_date": "2026-01-06",
  "view": "day",
  "smp_series": [
    {
      "timestamp": "2026-01-05T00:00:00",
      "smp": 181.89,
      "price_with_constraints": 181.89,
      "price_without_constraints": 181.89
    }
  ],
  "net_demand_series": [
    {
      "timestamp": "2026-01-05T00:00:00",
      "net_demand": 8905.19
    }
  ],
  "combined_series": [
    {
      "timestamp": "2026-01-05T00:00:00",
      "smp": 181.89,
      "price_with_constraints": 181.89,
      "price_without_constraints": 181.89,
      "net_demand": 8905.19
    }
  ],
  "correlation": [
    {
      "timestamp": "2026-01-05T00:00:00",
      "price_with_constraints": 181.89,
      "price_without_constraints": 181.89,
      "net_demand": 8905.19
    }
  ],
  "correlation_by_view": {
    "day": [
      {
        "timestamp": "2026-01-05T00:00:00",
        "price_with_constraints": 181.89,
        "price_without_constraints": 181.89,
        "net_demand": 8905.19
      }
    ],
    "month": [
      {
        "period": "2026-01",
        "price_with_constraints": 159.22885416666665,
        "price_without_constraints": 121.94937500000007,
        "net_demand": 9126.247708333334
      }
    ],
    "year": [
      {
        "period": "2026",
        "price_with_constraints": 159.22885416666665,
        "price_without_constraints": 121.94937500000007,
        "net_demand": 9126.247708333334
      }
    ]
  },
  "daily_average": [
    {
      "period": "2026-01-05",
      "avg_smp": 166.88145833333334,
      "price_with_constraints": 166.88145833333334,
      "price_without_constraints": 125.8285416666667,
      "net_demand": 9285.825833333332
    }
  ],
  "daily_smp": [
    {
      "date": "2026-01-05",
      "daily_smp_avg": 166.88145833333334,
      "daily_smp_avg_with_constraints": 166.88145833333334,
      "daily_smp_avg_without_constraints": 125.8285416666667
    }
  ],
  "monthly_average": [
    {
      "period": "2026-01",
      "avg_smp": 159.22885416666665,
      "price_with_constraints": 159.22885416666665,
      "price_without_constraints": 121.94937500000007,
      "net_demand": 9126.247708333334
    }
  ],
  "yearly_average": [
    {
      "period": "2026",
      "avg_smp": 159.22885416666665,
      "price_with_constraints": 159.22885416666665,
      "price_without_constraints": 121.94937500000007,
      "net_demand": 9126.247708333334
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
  "start_date": "2026-01-01",
  "end_date": "2026-01-01",
  "unit": "count",
  "labels": {
    "month": "Month",
    "total_consumers": "Total Consumers",
    "new_additions": "New Additions"
  },
  "data": [
    {
      "month": "2026-01",
      "total_consumers": 316929.0,
      "new_additions": 316929.0
    }
  ],
  "segments": {
    "regulation_type": [
      {
        "month": "2026-01",
        "regulation_type": "competitive_supply",
        "total_consumers": 106501.0,
        "new_additions": 106501.0
      }
    ],
    "sector": [
      {
        "month": "2026-01",
        "sector": "non_residential",
        "total_consumers": 25383.0,
        "new_additions": 25383.0
      }
    ],
    "meter_type": [
      {
        "month": "2026-01",
        "meter_type": "basic",
        "total_consumers": 89519.0,
        "new_additions": 89519.0
      }
    ]
  },
  "note": "Month derived from file name/modified date because no date column was provided."
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
  "filter": {
    "customer_type": "all",
    "year": "all"
  },
  "unit": "count",
  "available_years": [
    2021
  ],
  "start_year": 2021,
  "charts": {
    "requests_by_status": {
      "label": "Number of requests by status",
      "data": [
        {
          "label": "approved",
          "count": 611174
        },
        {
          "label": "rejected",
          "count": 277708
        }
      ]
    },
    "requests_by_customer_type": {
      "label": "Number of requests by customer type",
      "data": [
        {
          "label": "residential",
          "count": 786336
        }
      ]
    },
    "requests_by_regulation_type": {
      "label": "Number of requests by regulation type",
      "data": [
        {
          "label": "suppliers_with_generation",
          "count": 472491
        }
      ]
    },
    "requests_by_competition_type": {
      "label": "Number of requests by supply competition/existing regulation",
      "data": [
        {
          "label": "existing_regulation",
          "count": 472491
        }
      ]
    },
    "requests_by_rejection_reason": {
      "label": "Number of requests by rejection reason",
      "data": [
        {
          "label": "missing_power_of_attorney",
          "count": 12457
        },
        {
          "label": "meter_issues",
          "count": 8921
        },
        {
          "label": "request_form_issues",
          "count": 10132
        },
        {
          "label": "other",
          "count": 246198
        }
      ]
    }
  },
  "monthly_requests": [
    {
      "month": "2021-09",
      "requests": 157
    }
  ],
  "monthly_rejections_by_reason": [
    {
      "month": "2021-09",
      "missing_power_of_attorney": 12,
      "meter_issues": 3,
      "request_form_issues": 5,
      "other": 2,
      "total_rejections": 22
    }
  ],
  "total_requests": 888882,
  "total_rejections": 277708
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
    "description": "Hierarchical breakdown of generation by source.",
    "params": [
      "start_date (query, string, optional)",
      "end_date (query, string, optional)"
    ],
    "sample_response": [
      "200"
    ],
    "sample_response_body": {
      "start_date": "2025-01-06",
      "end_date": "2026-01-06",
      "filter": "year",
      "categories": [
        {
          "category_name": "renewables",
          "total_value": 12174782.644166637,
          "sub_categories": [
            {
              "sub_category_name": "photo_voltaic",
              "value": 10497594.438333333
            }
          ]
        }
      ],
      "category_percentages": {
        "renewables": 15.11,
        "non_renewables": 82.89,
        "other": 2.0
      },
      "tooltip": "The chart shows Israel's electricity generation mix and illustrates the different energy sources: non-renewables (coal, natural gas, diesel) and renewables (PV, biogas, wind, solar). Data updated hourly from NOGA.",
      "total": 80561884.0441667,
      "level1": {
        "non_renewables": 66778572.510000065,
        "renewables": 12174782.644166637,
        "other": 1608528.8900000043
      },
      "level2": {
        "non_renewables": {
          "coal": 7572099.632500037,
          "natural_gas": 59201014.21333336,
          "diesel": 5458.664166666667
        },
        "renewables": {
          "photovoltaic": 10497594.438333333,
          "biogas": 82409.06916666636,
          "wind": 858797.3016666656,
          "solar": 735981.8349999726
        },
        "other": {
          "other": 264540.0499999997,
          "pumped_storage": 1343988.8400000045
        }
      },
      "renewable_generation": 12174782.644166637,
      "renewable_share_percent": 15.11
    }
  }
]
```


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
