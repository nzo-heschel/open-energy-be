# 🌍 Open Energy — Backend (FastAPI)

### Israel Electricity Production Mix & Market Data API (NOGA Integration)

A comprehensive backend web service that collects, processes, and exposes Israel's electricity production data, pricing information, and market insights through modern REST API endpoints. Integrates with NOGA (Israel's Independent System Operator) to provide real-time and historical energy generation data.

The service is designed for dashboards, analytics platforms, energy market analysis tools, and other applications requiring reliable access to Israel's energy data.

## 📋 Table of Contents

- [What This Project Does](#what-this-project-does)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [API Documentation](#api-documentation)
- [Architecture](#architecture)
- [Delivery 1 - Core Energy & Market Endpoints](#delivery-1---core-energy--market-endpoints)
- [Delivery 2 - Renewable Infrastructure & Response Capacity](#delivery-2---renewable-infrastructure--response-capacity)
- [Delivery 3 - CO2 Emissions Endpoints](#delivery-3---co2-emissions-endpoints)
- [Delivery 4 - Forecasts & International Comparisons](#delivery-4---forecasts--international-comparisons)
- [Development & Extension](#development--extension)
- [Troubleshooting](#troubleshooting)

---

## What This Project Does

- **Collects** real-time and historical electricity generation data from NOGA (Israel's Independent System Operator)
- **Processes** high-frequency (5-minute interval) raw measurements into hourly averages
- **Aggregates** energy sources into hierarchical, human-readable categories (fossil, renewable, other)
- **Calculates** key metrics: renewable percentage, total generation, pricing, market trends, CO2 emissions
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
✅ **CO2 Emissions Insights** — Savings, ratio, mix, and emissions over time  
✅ **Forecasts & Comparisons** — Israel renewable trajectory and international target benchmarking  
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
      co2_emission_savings.py
      co2_emissions_mix.py
      co2_emissions_over_time.py
      co2_emissions_ratio.py
      co2_total_production.py
      co2_total_vs_ratio.py
      heat_load_vs_generation.py
      delivery4_forecasts.py          # Delivery 4 — Diagram 1 + Diagram 2
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
      response_capacity.py
      installed_capacity.py
      smp.py
      smp_production_vs_marginal_price.py
      switching_requests.py
  config.py
  main.py
  security.py
  services/
    data_file_manager.py
    connected_facilities_service.py
    distributor_responses_service.py
    delivery4_forecasts_service.py    # Delivery 4 service (CSV parsing + payload builders)
    demand_service.py
    co2_emission_savings_processor.py
    co2_emission_savings_service_.py
    heat_load_vs_generation_service.py
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
  tasks/
    file_expiry_notifier.py
  utils/
    __init__.py
    date_utils.py
    emailer.py
    enums.py
    response_formatter.py
data_extractor.py
data_files/
  diagram_sheet_1.csv                 # Delivery 4 Diagram 1 source
  diagram_sheet_2.csv                 # Delivery 4 Diagram 2 source
  Files_Netunei_hashmal_mp_niyud_*.csv
  Files_Netunei_hashmal_mp_tzarchan_*.csv
  Files_Netunei_hashmal_my_mehubarim.csv
  Files_Netunei_hashmal_my_teshuvotmehalek.csv
Delivery 2 Sources/
  Files_Netunei_hashmal_my_mehubarim.csv
  Files_Netunei_hashmal_my_teshuvotmehalek.csv
postman/
  Delivery_4_Endpoints.postman_collection.json
docker-compose.yml
Dockerfile
README.md
requirements.txt
```

Delivery 2-specific datasets are tracked in `Delivery 2 Sources/` (raw snapshots) and copied into `data_files/` before the application starts; `app/services/data_file_manager.py` tags each cache entry so `connected_facilities_service` and `distributor_responses_service` can build the Excel exports and REST responses.

Delivery 4 source CSVs (`diagram_sheet_1.csv`, `diagram_sheet_2.csv`) live directly in `data_files/` and are read at request time by `delivery4_forecasts_service.py`. Override paths with env vars `DELIVERY4_DIAGRAM1_CSV_PATH` and `DELIVERY4_DIAGRAM2_CSV_PATH` if needed.

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
CO2_TOKEN
SMP_TOKEN
INTERNAL_API_KEY
PROXY_URL
DELIVERY4_DIAGRAM1_CSV_PATH    # optional — override diagram_sheet_1.csv location
DELIVERY4_DIAGRAM2_CSV_PATH    # optional — override diagram_sheet_2.csv location
```

**Using with Docker:**

```powershell
docker run -d -p 8000:8000 -e NOGA_API_TOKEN="token" -e CO2_TOKEN="token" open-energy-be
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
│  ├─ co2_emission_savings.py                          │
│  ├─ co2_emissions_mix.py                             │
│  ├─ smp.py                                           │
│  ├─ private_suppliers.py                             │
│  ├─ switching_requests.py                            │
│  └─ delivery4_forecasts.py                           │
|           │
│           │                                          │
│           ▼                                          │
│  Services Layer (app/services/)                      │
│  ├─ noga_service.py (fetch data)                     │
│  ├─ co2_emission_savings_service_.py (fetch CO2)      │
│  ├─ co2_emission_savings_processor.py (parse/agg)     │
│  ├─ energy_mix_processor.py (process)                │
│  ├─ smp_processor.py (calculate)                     │
│  ├─ delivery4_forecasts_service.py (CSV → payload)   │
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
│  ├─ NOGA API (production mix, pricing, CO2)          │
│  ├─ CSV Files (private suppliers, switching)         │
│  ├─ CSV Files (Delivery 4 diagram sheets)            │
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
 9. **Delivery 2 CSV Ingestion** — Recharge the connected-facilities and distributor-responses snapshots that power the renewable infrastructure endpoints via `data_file_manager`.
10. **Delivery 2 Aggregation & Export** — `connected_facilities_service` and `distributor_responses_service` build the series/exports that mirror the PRD tables.
11. **Delivery 4 CSV Read** — `delivery4_forecasts_service` reads `diagram_sheet_1.csv` and `diagram_sheet_2.csv` at request time, parses header/label/data rows, and builds the forecast and comparison payloads.



---

## Delivery 1 - Core Energy & Market Endpoints

This section documents the Delivery 1 APIs that power the core generation mix, market pricing, SMP, private supplier, and switching-request insights.

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
  "start_date": "2025-02-19",
  "end_date": "2026-02-19",
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
  "start_date": "2025-02-19",
  "end_date": "2026-02-19",
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
      "period": "2025-02",
      "label": "Feb 2025",
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
      "period": "2026-02-18",
      "price_with_constraints": 166.88145833333334,
      "price_without_constraints": 125.8285416666667,
      "net_demand": 9285.825833333332
    }
  ],
  "monthly_average": [
    {
      "period": "2026-02",
      "price_with_constraints": 159.22885416666665,
      "price_without_constraints": 121.94937500000007,
      "net_demand": 9126.247708333334
    }
  ],
  "chart_without_constraints": [
    {
      "timestamp": "2026-02-18T00:00:00",
      "price": 181.89
    }
  ],
  "chart_with_constraints": [
    {
      "timestamp": "2026-02-18T00:00:00",
      "price": 181.89
    }
  ],
  "correlation_view": [
    {
      "timestamp": "2026-02-18T00:00:00",
      "net_demand": 8905.19,
      "price": 181.89
    }
  ],
  "samples": [
    {
      "timestamp": "2026-02-18T00:00:00",
      "price_with_constraints": 181.89,
      "price_without_constraints": 181.89,
      "net_demand": 8905.19,
      "date": "18-02-2026"
    }
  ],
  "view": "day",
  "start_date": "2026-02-18",
  "end_date": "2026-02-19"
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
  "start_date": "2026-02-18",
  "end_date": "2026-02-19",
  "view": "day",
  "smp_series": [
    {
      "timestamp": "2026-02-18T00:00:00",
      "smp": 181.89,
      "price_with_constraints": 181.89,
      "price_without_constraints": 181.89
    }
  ],
  "net_demand_series": [
    {
      "timestamp": "2026-02-18T00:00:00",
      "net_demand": 8905.19
    }
  ],
  "combined_series": [
    {
      "timestamp": "2026-02-18T00:00:00",
      "smp": 181.89,
      "price_with_constraints": 181.89,
      "price_without_constraints": 181.89,
      "net_demand": 8905.19
    }
  ],
  "correlation": [
    {
      "timestamp": "2026-02-18T00:00:00",
      "price_with_constraints": 181.89,
      "price_without_constraints": 181.89,
      "net_demand": 8905.19
    }
  ],
  "correlation_by_view": {
    "day": [
      {
        "timestamp": "2026-02-18T00:00:00",
        "price_with_constraints": 181.89,
        "price_without_constraints": 181.89,
        "net_demand": 8905.19
      }
    ],
    "month": [
      {
        "period": "2026-02",
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
      "period": "2026-02-18",
      "avg_smp": 166.88145833333334,
      "price_with_constraints": 166.88145833333334,
      "price_without_constraints": 125.8285416666667,
      "net_demand": 9285.825833333332
    }
  ],
  "daily_smp": [
    {
      "date": "2026-02-18",
      "daily_smp_avg": 166.88145833333334,
      "daily_smp_avg_with_constraints": 166.88145833333334,
      "daily_smp_avg_without_constraints": 125.8285416666667
    }
  ],
  "monthly_average": [
    {
      "period": "2026-02",
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
  "start_date": "2026-02-01",
  "end_date": "2026-02-01",
  "unit": "count",
  "labels": {
    "month": "Month",
    "total_consumers": "Total Consumers",
    "new_additions": "New Additions"
  },
  "data": [
    {
      "month": "2026-02",
      "total_consumers": 316929.0,
      "new_additions": 316929.0
    }
  ],
  "segments": {
    "regulation_type": [
      {
        "month": "2026-02",
        "regulation_type": "competitive_supply",
        "total_consumers": 106501.0,
        "new_additions": 106501.0
      }
    ],
    "sector": [
      {
        "month": "2026-02",
        "sector": "non_residential",
        "total_consumers": 25383.0,
        "new_additions": 25383.0
      }
    ],
    "meter_type": [
      {
        "month": "2026-02",
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

## Delivery 2 - Renewable Infrastructure & Response Capacity

Implemented: 9 | Skipped: 3 (client decisions) | Blocked: 2 (missing upstream data).

### Status at a Glance

| # | Endpoint | Status | Source |
|---|---|---|---|
| 1 | Renewable Energy Production Mix | Implemented | NOGA API |
| 2 | Transition to Renewable Energies in Israel | Implemented | NOGA API |
| 3 | Renewable Energy Production Potential by Industry Type | Implemented | NOGA API |
| 4 | Renewable Energy Usage (Solar) | Skipped (client) | Electricity Authority BI |
| 5 | Locality Status | Skipped (client) | Electricity Authority BI |
| 6 | Renewable Energy Production Potential by District | Skipped (client) | Ministry of Energy Power BI |
| 7 | Production Potential Comparison - Nearby Localities | Blocked (missing geo data) | Ministry of Energy Power BI |
| 8 | Production Potential Comparison - Similar-Sized Localities | Blocked (missing population data) | Ministry of Energy Power BI |
| 9 | Installed Capacity (Cumulative) | Implemented | Electricity Authority CSV |
| 10 | Installed Capacity - Growth Rate | Implemented | Electricity Authority CSV |
| 11 | Facility Capacity Connected Over Time by Facility Size | Implemented | Electricity Authority CSV |
| 12 | Response Capacity Divided by Period | Implemented | Electricity Authority CSV |
| 13 | Response Capacity Divided by Facility Size (kW) | Implemented | Electricity Authority CSV |
| 14 | Response Capacity Divided by District | Implemented | Electricity Authority CSV |

#### Endpoints 1–3: Renewable Energy Mix & Transition (NOGA API)

These routes call the NOGA API, divide each 5-minute sample by 12 to convert into hourly equivalents, then aggregate into daily/monthly series.

##### GET /api/v1/renewables/production-mix

- **Router:** `app/api/v1/renewable_mix.py`
- **Service:** `app/services/renewable_mix_service.py`
- **Data Source:** NOGA API (5-minute measurements converted to hourly aggregates)
- **Export:** `GET /api/v1/renewables/production-mix/export`

**Description:** Returns the renewable portion of the production mix with breakdowns for solar, wind, and other sources.

**Query Parameters:**
- `start_date` (optional, YYYY-MM-DD)
- `end_date` (optional, YYYY-MM-DD)
- `category` (optional, `solar`, `wind`, `other`)

**Response (200 OK):**
```json
{
  "start_date": "2026-01-01",
  "end_date": "2026-01-31",
  "view": "month",
  "total_renewable_mw": 124500.4,
  "breakdown": [
    {
      "type": "photovoltaic",
      "value": 101750.2,
      "share_percent": 81.8
    },
    {
      "type": "wind",
      "value": 15000.6,
      "share_percent": 12.1
    },
    {
      "type": "other",
      "value": 8000.4,
      "share_percent": 6.1
    }
  ],
  "series": [
    {
      "period": "2026-01-01",
      "solar_mw": 4200.5,
      "wind_mw": 520.0,
      "other_mw": 230.1
    }
  ]
}
```

**Export:** `GET /api/v1/renewables/production-mix/export` returns an Excel workbook with summary and detailed sheets.

##### GET /api/v1/renewables/transition

- **Router:** `app/api/v1/renewable_transition.py`
- **Service:** `app/services/renewable_transition_service.py`
- **Data Source:** NOGA API
- **Export:** `GET /api/v1/renewables/transition/export`

**Description:** Shows the national transition to renewables month by month.

**Query Parameters:**
- `year` (optional, 4-digit year; defaults to the current year)

**Response (200 OK):**
```json
{
  "year": "2025",
  "renewable_share_percent": 16.2,
  "monthly_totals": [
    {
      "month": "2025-01",
      "renewable_mw": 4880.0,
      "total_mw": 28500.0,
      "renewable_share_percent": 17.1
    }
  ],
  "notes": "Share is calculated with 5-minute samples divided by 12 and grouped by month."
}
```

**Export:** `GET /api/v1/renewables/transition/export`

##### GET /api/v1/renewables/potential-by-industry

- **Router:** `app/api/v1/renewable_potential_industry.py`
- **Service:** `app/services/renewable_potential_industry_service.py`
- **Data Source:** NOGA API
- **Export:** `GET /api/v1/renewables/potential-by-industry/export`

**Description:** Estimates renewable production potential per industry vertical.

**Query Parameters:**
- `year` (optional, 4-digit year; defaults to the current year)

**Response (200 OK):**
```json
{
  "year": "2025",
  "total_potential_mw": 3865.3,
  "industry_breakdown": [
    {
      "industry_type": "industrial",
      "renewable_potential_mw": 1670.2,
      "solar_share_percent": 48.6
    }
  ],
  "notes": "Industry names follow the Electricity Authority classification."
}
```

**Export:** `GET /api/v1/renewables/potential-by-industry/export`

#### Endpoints 9–11: Installed Capacity (Connected Facilities CSV)

These endpoints ingest `Files_Netunei_hashmal_my_mehubarim.csv` (63,687 records, cp1255 encoding) that is kept under `data_files/` and mirrored in `Delivery 2 Sources/` for safekeeping. `connected_facilities_service.py` reads the file via `data_file_manager`, applies the `DataFileSource.CONNECTED_FACILITIES` enum, and feeds the three APIs below. Filters include `year`, `district`, and `technology`.

##### GET /api/v1/renewables/installed-capacity/cumulative

- **Router:** `app/api/v1/installed_capacity.py`
- **Service:** `app/services/connected_facilities_service.py`
- **Data Source:** `Files_Netunei_hashmal_my_mehubarim.csv` → `DataFileSource.CONNECTED_FACILITIES`
- **Export:** `GET /api/v1/renewables/installed-capacity/cumulative/export`

**Description:** Returns the cumulative installed capacity time series with technology and district breakdowns.

**Query Parameters:**
- `year` (optional, int)
- `district` (optional, Jerusalem|North|South|Haifa|Center|Tel Aviv|Judea & Samaria|Other)
- `technology` (optional, Photovoltaic|Wind|Solar Thermal|Other)

**Response (200 OK):**
```json
{
  "title": "Installed Capacity (Cumulative) of Renewable Energy Facilities",
  "total_installed_mw": 7756.107,
  "total_facilities": 63687,
  "series": [
    {
      "period": "2012-01",
      "added_mw": 0.123,
      "cumulative_mw": 0.123
    }
  ],
  "technology_breakdown": {
    "Photovoltaic": 7200.0,
    "Wind": 300.0,
    "Solar Thermal": 150.0,
    "Other": 106.107
  },
  "district_breakdown": {
    "South": 3000.0,
    "North": 1500.0
  }
}
```

**Export:** `GET /api/v1/renewables/installed-capacity/cumulative/export`

##### GET /api/v1/renewables/installed-capacity/growth

- **Router/Service:** `app/api/v1/installed_capacity.py` / `app/services/connected_facilities_service.py`
- **Data Source:** `Files_Netunei_hashmal_my_mehubarim.csv`
- **Export:** `GET /api/v1/renewables/installed-capacity/growth/export`

**Description:** Reports yearly additions plus percentage growth on the cumulative series.

**Query Parameters:**
- `district` (optional)
- `technology` (optional)

**Response (200 OK):**
```json
{
  "title": "Installed Capacity — Growth Rate",
  "series": [
    {
      "year": 2024,
      "added_mw": 420.0,
      "cumulative_mw": 7200.0,
      "growth_rate_percent": 6.2
    }
  ],
  "filters_applied": {
    "district": null,
    "technology": "Photovoltaic"
  }
}
```

**Export:** `GET /api/v1/renewables/installed-capacity/growth/export`

##### GET /api/v1/renewables/installed-capacity/by-facility-size

- **Router/Service:** `app/api/v1/installed_capacity.py` / `app/services/connected_facilities_service.py`
- **Data Source:** `Files_Netunei_hashmal_my_mehubarim.csv`
- **Export:** `GET /api/v1/renewables/installed-capacity/by-facility-size/export`

**Description:** Breaks the cumulative series by seven facility size brackets.

**Query Parameters:**
- `year` (optional, int)
- `district` (optional)

**Size Brackets:** Up to 16 kW, 16–50 kW, 50–200 kW, 200 kW–1 MW, 1–5 MW, 5–50 MW, 50+ MW.

**Response (200 OK):**
```json
{
  "series": [
    {
      "year": 2024,
      "size_brackets": {
        "Up to 16 kW": 1500.0,
        "16–50 kW": 950.0,
        "50–200 kW": 380.0,
        "200 kW–1 MW": 270.0,
        "1–5 MW": 310.0,
        "5–50 MW": 240.0,
        "50+ MW": 180.0
      }
    }
  ],
  "total_mw": 3830.0
}
```

**Export:** `GET /api/v1/renewables/installed-capacity/by-facility-size/export`

#### Endpoints 12–14: Response Capacity (Distributor Responses CSV)

These endpoints process `Files_Netunei_hashmal_my_teshuvotmehalek.csv` (76,876 records, cp1255 encoding). `distributor_responses_service.py` and `data_file_manager.py` treat cancellations, response types, districts, and technologies to build the requested metrics.

##### GET /api/v1/renewables/response-capacity/by-period

- **Router:** `app/api/v1/renewables/response-capacity/by-period`
- **Service:** `app/services/distributor_responses_service.py`
- **Data Source:** `Files_Netunei_hashmal_my_teshuvotmehalek.csv` → `DataFileSource.DISTRIBUTOR_RESPONSES`
- **Export:** `GET /api/v1/renewables/response-capacity/by-period/export`

**Description:** Aggregated response capacity per time period with breakdowns by response type.

**Query Parameters:**
- `year` (optional, int)
- `district` (optional)
- `technology` (optional, Photovoltaic|Wind|Other)
- `response_type` (optional, Positive|Partial Positive|Limited Positive|Negative)
- `include_cancelled` (optional, bool)

**Response (200 OK):**
```json
{
  "title": "Response Capacity Divided by Period",
  "total_mw": 18214.205,
  "series": [
    {
      "period": "2023-12",
      "total_mw": 320.5,
      "request_count": 820,
      "response_type_breakdown": {
        "Positive": 238.5,
        "Negative": 40.0,
        "Partial Positive": 30.0,
        "Limited Positive": 12.0
      }
    }
  ],
  "response_type_breakdown": {
    "Positive": 15000.0,
    "Negative": 1500.0,
    "Partial Positive": 1000.0,
    "Limited Positive": 714.0
  }
}
```

**Export:** `GET /api/v1/renewables/response-capacity/by-period/export`

##### GET /api/v1/renewables/response-capacity/by-size

- **Router/Service:** `app/api/v1/renewables/response-capacity/by-size` / `app/services/distributor_responses_service.py`
- **Data Source:** `Files_Netunei_hashmal_my_teshuvotmehalek.csv`
- **Export:** `GET /api/v1/renewables/response-capacity/by-size/export`

**Description:** Shows response MW split by the same seven size brackets plus yearly totals.

**Query Parameters:**
- `year` (optional)
- `district` (optional)
- `include_cancelled` (optional, bool)

**Response (200 OK):**
```json
{
  "title": "Response Capacity by Facility Size",
  "series": [
    {
      "year": 2024,
      "size_bracket": "1–5 MW",
      "total_mw": 1240.0,
      "request_count": 220
    }
  ],
  "size_brackets": [
    "Up to 16 kW",
    "16–50 kW",
    "50–200 kW",
    "200 kW–1 MW",
    "1–5 MW",
    "5–50 MW",
    "50+ MW"
  ]
}
```

**Export:** `GET /api/v1/renewables/response-capacity/by-size/export`

##### GET /api/v1/renewables/response-capacity/by-district

- **Router/Service:** `app/api/v1/renewables/response-capacity/by-district` / `app/services/distributor_responses_service.py`
- **Data Source:** `Files_Netunei_hashmal_my_teshuvotmehalek.csv`
- **Export:** `GET /api/v1/renewables/response-capacity/by-district/export`

**Description:** Aggregates response capacity per district with a technology breakdown.

**Query Parameters:**
- `year` (optional)
- `technology` (optional)
- `include_cancelled` (optional, bool)

**Response (200 OK):**
```json
{
  "title": "Response Capacity Divided by District",
  "series": [
    {
      "district": "South",
      "total_mw": 7200.0,
      "request_count": 2100,
      "technology_breakdown": {
        "Photovoltaic": 6800.0,
        "Wind": 400.0
      }
    }
  ],
  "district_technology_breakdown": {
    "South": {
      "Photovoltaic": 6800.0,
      "Wind": 400.0
    }
  }
}
```

**Export:** `GET /api/v1/renewables/response-capacity/by-district/export`


### Data Sources

#### Source 1: NOGA API (Endpoints 1-3)

| Property | Details |
|---|---|
| **Base URL** | `https://apim-api.noga-iso.co.il/` |
| **Path** | `PRODUCTIONMIX/PRODMIXAPI/v1` |
| **Method** | POST |
| **Authentication** | `Ocp-Apim-Subscription-Key` header (env var: `NOGA_API_TOKEN`) |
| **Request Payload** | `{ "fromDate": "dd-mm-yyyy", "toDate": "dd-mm-yyyy" }` |
| **Energy Conversion** | Each sample value (MW) ÷ 12 = MWh |
| **Service** | `app/services/noga_service.py` |

#### Source 2: Electricity Authority CSV - Connected Facilities (Endpoints 9-11)

| Property | Details |
|---|---|
| **File** | `Files_Netunei_hashmal_my_mehubarim.csv` |
| **Encoding** | `cp1255` |
| **Records** | 63,687 rows |
| **Key Columns** | District, Municipal Status, Council/City, Locality, Technology, Classification, Regulation, Date, Capacity (MW) |
| **Service** | `app/services/connected_facilities_service.py` |
| **Enum** | `DataFileSource.CONNECTED_FACILITIES` |

#### Source 3: Electricity Authority CSV - Distributor Responses (Endpoints 12-14)

| Property | Details |
|---|---|
| **File** | `Files_Netunei_hashmal_my_teshuvotmehalek.csv` |
| **Encoding** | `cp1255` |
| **Records** | 76,876 rows |
| **Key Columns** | District, Municipal Status, Locality, Technology, Classification, Response Type, Regulation, Date, Capacity (MW), Cancellation Flag |
| **Service** | `app/services/distributor_responses_service.py` |
| **Enum** | `DataFileSource.DISTRIBUTOR_RESPONSES` |

### Postman & Verification

A dedicated Postman collection (`delivery-2.postman_collection.json`) covers all Delivery 2 endpoints. Use the collection variables `base_url` (`http://localhost:8010` by default) and `api_key` (set it to your `INTERNAL_API_KEY`).

Verified test results:

```
PASS  EP 9  - Installed Capacity (Cumulative)     series: 154 points
PASS  EP 9  - Filtered by South district           series: 134 points
PASS  EP 10 - Installed Capacity (Growth)          series: 17 points
PASS  EP 10 - Filtered by Photovoltaic             series: 17 points
PASS  EP 11 - Capacity by Facility Size            series: 17 points
PASS  EP 11 - Filtered up to 2023                  series: 15 points
PASS  EP 12 - Response Capacity by Period          series: 71 points
PASS  EP 12 - Filtered to 2024                     series: 12 points
PASS  EP 13 - Response Capacity by Size            series: 6 brackets
PASS  EP 14 - Response Capacity by District        series: 8 districts
PASS  EP 14 - Filtered by Photovoltaic             series: 8 districts
PASS  EP 9  Export                                 9.7 KB Excel
PASS  EP 10 Export                                 5.4 KB Excel
PASS  EP 11 Export                                 7.8 KB Excel
PASS  EP 12 Export                                 7.0 KB Excel
PASS  EP 13 Export                                 6.5 KB Excel
PASS  EP 14 Export                                 5.9 KB Excel
```


## Delivery 3 - CO2 Emissions Endpoints

#### `GET /api/v1/co2/emissions-savings`

**Description:** Total CO2 emissions (coal + natural gas + diesel) for the selected period

**Query Parameters:**

- `start_date` (optional, YYYY-MM-DD)
- `end_date` (optional, YYYY-MM-DD)

**Response (200 OK):**

```json
{
  "total": 2505223.89,
  "unit": "tons CO2",
  "start_date": "2026-02-01",
  "end_date": "2026-02-18"
}
```

---

#### `GET /api/v1/co2/emissions-ratio`

**Description:** Total CO2 emissions ratio (tons CO2 per MWh) for the selected period

**Query Parameters:**

- `start_date` (optional, YYYY-MM-DD)
- `end_date` (optional, YYYY-MM-DD)

**Response (200 OK):**

```json
{
  "total": 261.1633,
  "unit": "tons CO2/MWh",
  "start_date": "2026-02-01",
  "end_date": "2026-02-18"
}
```

---

#### `GET /api/v1/co2/total-production`

**Description:** Total system generation (MWh) for the selected period

**Query Parameters:**

- `start_date` (optional, YYYY-MM-DD)
- `end_date` (optional, YYYY-MM-DD)

**Response (200 OK):**

```json
{
  "total": 7036671.71,
  "unit": "MWh",
  "start_date": "2026-02-01",
  "end_date": "2026-02-18"
}
```

---

#### `GET /api/v1/co2/emissions-mix`

**Description:** CO2 emissions mix (pie chart + infographics + time series)

**Query Parameters:**

- `start_date` (optional, YYYY-MM-DD)
- `end_date` (optional, YYYY-MM-DD)
- `view` (optional, day | month | year)

**Response (200 OK):**

```json
{
  "view": "month",
  "start_date": "2026-02-01",
  "end_date": "2026-02-18",
  "total_emissions": 2505223.89,
  "total_emissions_unit": "tons CO2",
  "emissions_per_kwh": 0.000356,
  "emissions_per_kwh_unit": "tons CO2/kWh",
  "total_generation_mwh": 7036671.71,
  "pie_chart": {
    "coal": {
      "value": 391019.99,
      "percentage": 15.61,
      "unit": "tons CO2"
    },
    "natural_gas": {
      "value": 2093868.51,
      "percentage": 83.58,
      "unit": "tons CO2"
    },
    "diesel": {
      "value": 20335.38,
      "percentage": 0.81,
      "unit": "tons CO2"
    }
  },
  "infographics": {
    "total_emissions_excluding_renewables": {
      "value": 2505223.89,
      "unit": "tons CO2",
      "description": "Total CO2 emissions from fossil fuels (coal + gas + diesel)"
    },
    "emissions_avoided_through_renewables": {
      "value": 1364945.55,
      "unit": "tons CO2",
      "description": "Estimated CO2 emissions avoided due to renewable energy generation (assuming 0.55t/MWh baseline)"
    }
  },
  "time_series": [
    {
      "period": "2026-02-01",
      "label": "01 Feb",
      "coal": 12431.86,
      "natural_gas": 64471.12,
      "diesel": 39.73,
      "total_emissions": 76942.7,
      "generation_mwh": 218258.07,
      "emissions_per_kwh": 0.000353,
      "unit": "tons CO2"
    }
  ]
}
```

---


---

#### `GET /api/v1/co2/emissions-mix/export`

**Description:** Export CO2 emissions mix to Excel

**Query Parameters:**

- `start_date` (optional, YYYY-MM-DD)
- `end_date` (optional, YYYY-MM-DD)
- `view` (optional, day | month | year)

**Response:** Streamed Excel file (`co2_emissions_mix_STARTDATE_to_ENDDATE.xlsx`)

---
#### `GET /api/v1/co2/emissions-over-time`

**Description:** CO2 emissions over time (chart + infographics)

**Query Parameters:**

- `start_date` (optional, YYYY-MM-DD)
- `end_date` (optional, YYYY-MM-DD)
- `view` (optional, month | year | custom)

**Response (200 OK):**

```json
{
  "view": "month",
  "start_date": "2026-02-01",
  "end_date": "2026-02-18",
  "infographics": {
    "total_emissions_excluding_renewables": {
      "value": 2505223.89,
      "unit": "tons CO2",
      "description": "Total CO2 emissions from fossil fuels (coal + gas + diesel)"
    },
    "emissions_avoided_through_renewables": {
      "value": 1364945.55,
      "unit": "tons CO2",
      "description": "Estimated CO2 emissions avoided due to renewable energy generation"
    }
  },
  "chart_data": [
    {
      "period": "2026-02-01",
      "label": "01 Feb",
      "coal": 12431.86,
      "natural_gas": 64471.12,
      "diesel": 39.73,
      "total_emissions": 76942.7,
      "emissions_per_kwh": 0.000353,
      "unit": "tons CO2"
    }
  ]
}
```

---


---

#### `GET /api/v1/co2/emissions-over-time/export`

**Description:** Export CO2 emissions over time to Excel

**Query Parameters:**

- `start_date` (optional, YYYY-MM-DD)
- `end_date` (optional, YYYY-MM-DD)
- `view` (optional, month | year | custom)

**Response:** Streamed Excel file (`co2_emissions_over_time_STARTDATE_to_ENDDATE.xlsx`)

---
#### `GET /api/v1/co2/total-vs-ratio`

**Description:** Total CO2 emissions vs CO2 emissions ratio (combined chart + infographics)

**Query Parameters:**

- `start_date` (optional, YYYY-MM-DD)
- `end_date` (optional, YYYY-MM-DD)
- `view` (optional, month | year | custom)

**Response (200 OK):**

```json
{
  "view": "month",
  "start_date": "2026-02-01",
  "end_date": "2026-02-18",
  "infographics": {
    "total_emissions_excluding_renewables": {
      "value": 2505223.89,
      "unit": "tons CO2",
      "description": "Total CO2 emissions from fossil fuels (coal + gas + diesel)"
    },
    "emissions_avoided_through_renewables": {
      "value": 1364945.55,
      "unit": "tons CO2",
      "description": "Estimated CO2 emissions avoided due to renewable energy generation"
    }
  },
  "chart_data": [
    {
      "period": "2026-02-01",
      "label": "01 Feb",
      "total_emissions": 76942.7,
      "emissions_ratio": 8.4958,
      "coal": 12431.86,
      "natural_gas": 64471.12,
      "diesel": 39.73,
      "generation_mwh": 218258.07,
      "emissions_per_kwh": 0.000353,
      "unit_emissions": "tons CO2",
      "unit_ratio": "tons CO2/MWh"
    }
  ]
}
```

---

#### `GET /api/v1/co2/total-vs-ratio/export-csv`

**Description:** Export total CO2 emissions vs CO2 emissions ratio to CSV

**Query Parameters:**

- `start_date` (optional, YYYY-MM-DD)
- `end_date` (optional, YYYY-MM-DD)
- `view` (optional, month | year | custom)

**Response:** Streamed CSV file (`co2_total_vs_ratio_STARTDATE_to_ENDDATE.csv`)

---

#### `GET /api/v1/heat-load-vs-generation`

**Description:** Heat load vs electricity generation based on meteorological CSV data and generation data

**Query Parameters:**

- `start_date` (optional, YYYY-MM-DD)
- `end_date` (optional, YYYY-MM-DD)
- `view` (optional, month | year | custom)

**Response (200 OK):**

```json
{
  "view": "year",
  "start_date": "2026-02-01",
  "end_date": "2026-02-18",
  "units": {
    "heat_load": "THI",
    "electricity_generation": "MW"
  },
  "series": [
    {
      "period": "2026-02-16/2026-02-22",
      "label": "16 Feb",
      "heat_load": 11.96,
      "electricity_generation_mw": 8620.43
    }
  ]
}
```

---

#### `GET /api/v1/heat-load-vs-generation/export`

**Description:** Export heat load vs electricity generation to Excel

**Query Parameters:**

- `start_date` (optional, YYYY-MM-DD)
- `end_date` (optional, YYYY-MM-DD)
- `view` (optional, month | year | custom)

**Response:** Streamed Excel file (`heat_load_vs_generation_STARTDATE_to_ENDDATE.xlsx`)

---

### 9. Data Files Endpoints

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


### 10. API Catalog Endpoint


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
      "start_date": "2025-02-19",
      "end_date": "2026-02-19",
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





## Delivery 4 - Forecasts & International Comparisons

Delivery 4 exposes two diagrams from the PRD section "תחזיות והשוואות" (Forecasts & Comparisons). Both endpoints read from dedicated CSV source files in `data_files/`.

### Status at a Glance

| # | Endpoint | Status | Source |
|---|---|---|---|
| 1 | Israel Renewable Forecast Trajectory (Diagram 1) | Implemented | `diagram_sheet_1.csv` |
| 2 | International Renewable Comparison (Diagram 2) | Implemented | `diagram_sheet_2.csv` |

### Route Prefixes

The router is mounted at three prefixes for backwards compatibility:

| Prefix | Schema Visibility |
|---|---|
| `/api/v1/renewables/delivery-4/` | **Primary** (shown in docs) |
| `/api/v1/renewables/` | Alias (hidden from schema) |
| `/api/v1/forecasts/` | Alias (hidden from schema) |

---

#### Diagram 1: Israel Renewable Forecast Trajectory

##### GET /api/v1/renewables/delivery-4/renewable-forecast-israel

- **Router:** `app/api/v1/delivery4_forecasts.py`
- **Service:** `app/services/delivery4_forecasts_service.py`
- **Data Source:** `data_files/diagram_sheet_1.csv` (override with env var `DELIVERY4_DIAGRAM1_CSV_PATH`)
- **Export:** `GET /api/v1/renewables/delivery-4/renewable-forecast-israel/export`

**Description:** Returns the yearly Israel renewable forecast trajectory from 2020 to 2050 with four series: actual renewable rate (column bar), realistic forecast (line), Ministry of Energy target (line), and NZO target (line). Values are fractions 0–1 (multiply by 100 for percent).

**Graph Type:** Column bar chart (renewable rate) + 3 line graphs (realistic forecast, Ministry of Energy target, NZO target).

**Response (200 OK):**

```json
{
    "title": "Renewables forecast trajectory in Israel",
    "title_he": "תחזית שיעור אנרגיות מתחדשות בישראל",
    "value_unit": "fraction",
    "value_unit_description": "All numeric values are fractions in [0, 1]; multiply by 100 for percent.",
    "series_labels": {
        "renewable_rate": "Renewable rate",
        "realistic_forecast": "Realistic forecast",
        "ministry_target": "Ministry of Energy target",
        "nzo_target": "NZO target"
    },
    "data": [
        {
            "year": 2020,
            "renewable_rate": 0.063,
            "realistic_forecast": 0.063,
            "ministry_target": 0.1,
            "nzo_target": 0.275
        },
        {
            "year": 2021,
            "renewable_rate": 0.082,
            "realistic_forecast": 0.082,
            "ministry_target": 0.12,
            "nzo_target": 0.298
        },
        {
            "year": 2024,
            "renewable_rate": 0.146,
            "realistic_forecast": 0.146,
            "ministry_target": 0.18,
            "nzo_target": 0.365
        },
        {
            "year": 2030,
            "renewable_rate": 0.0,
            "realistic_forecast": 0.274,
            "ministry_target": 0.3,
            "nzo_target": 0.5
        },
        {
            "year": 2050,
            "renewable_rate": 0.0,
            "realistic_forecast": 0.7006666667,
            "ministry_target": 0.7,
            "nzo_target": 0.95
        }
    ],
    "metadata": {
        "year_start": 2020,
        "year_end": 2050,
        "realistic_forecast_factor": 0.02133333333
    },
    "source": {
        "csv_path": "/absolute/path/to/data_files/diagram_sheet_1.csv"
    }
}
```

**Notes:**
- `renewable_rate` is 0.0 for future years (2025+) where actuals are not yet available.
- `realistic_forecast` is calculated using the factor shown in `metadata.realistic_forecast_factor`.
- Full response contains 31 data points (2020–2050); sample above is truncated for brevity.

---

##### GET /api/v1/renewables/delivery-4/renewable-forecast-israel/export

**Description:** Export Diagram 1 to Excel

**Response:** Streamed Excel file (`delivery4_diagram1_renewable_forecast_israel.xlsx`) with three sheets:
- **Diagram 1 data** — year, renewable_rate, realistic_forecast, ministry_target, nzo_target
- **Series labels** — human-readable labels for each series key
- **Meta** — diagram ID, titles, value unit, year range, forecast factor, source CSV path

---

#### Diagram 2: International Renewable Comparison

##### GET /api/v1/renewables/delivery-4/international-renewable-comparison

- **Router:** `app/api/v1/delivery4_forecasts.py`
- **Service:** `app/services/delivery4_forecasts_service.py`
- **Data Source:** `data_files/diagram_sheet_2.csv` (override with env var `DELIVERY4_DIAGRAM2_CSV_PATH`)
- **Export:** `GET /api/v1/renewables/delivery-4/international-renewable-comparison/export`

**Description:** Returns a horizontal bar comparison of countries/regions showing 2024 solar share, 2030 renewable target, and 2050 renewable target. Values are fractions 0–1.

**Query Parameters:**

- `include_2050_targets` (optional, bool, default `true`) — Include 2050 renewable target series
- `include_solar_share` (optional, bool, default `true`) — Include 2024 solar share series

**Response (200 OK):**

```json
{
    "diagram_id": "delivery_4_diagram_2",
    "title": "Renewables — targets vs actual (international comparison)",
    "title_he": "אנרגיות מתחדשות יעדים מול ייצור בפועל",
    "value_unit": "fraction",
    "value_unit_description": "All numeric values are fractions in [0, 1]; multiply by 100 for percent.",
    "filters": {
        "include_2030_targets": true,
        "include_2050_targets": true,
        "include_solar_share": true
    },
    "column_labels": {
        "solar_share_2024": {
            "en": "2024 Solar Share",
            "he": "שיעור ייצור סולארי (2024)"
        },
        "renewable_target_2030": {
            "en": "2030 renewable target",
            "he": "יעד אנרגיות מתחדשות 2030"
        },
        "renewable_target_2050": {
            "en": "2050 renewable target",
            "he": "יעד אנרגיות מתחדשות 2050"
        }
    },
    "regions": [
        {
            "region": "Israel",
            "region_he": "ישראל",
            "region_key": "israel",
            "renewable_target_2030": 0.3,
            "solar_share_2024": 0.146,
            "renewable_target_2050": 0.77
        },
        {
            "region": "Germany",
            "region_he": "גרמניה",
            "region_key": "germany",
            "renewable_target_2030": 0.8,
            "solar_share_2024": 0.146,
            "renewable_target_2050": 1.0
        },
        {
            "region": "Spain",
            "region_he": "ספרד",
            "region_key": "spain",
            "renewable_target_2030": 0.81,
            "solar_share_2024": 0.187,
            "renewable_target_2050": 1.0
        },
        {
            "region": "Italy",
            "region_he": "איטליה",
            "region_key": "italy",
            "renewable_target_2030": 0.55,
            "solar_share_2024": 0.133,
            "renewable_target_2050": 1.0
        },
        {
            "region": "Greece",
            "region_he": "יוון",
            "region_key": "greece",
            "renewable_target_2030": 0.75,
            "solar_share_2024": 0.174,
            "renewable_target_2050": 1.0
        },
        {
            "region": "California",
            "region_he": "קליפורניה",
            "region_key": "california",
            "renewable_target_2030": 0.5,
            "solar_share_2024": 0.234,
            "renewable_target_2050": 1.0
        }
    ],
    "regions_without_solar_data": [],
    "validation": [],
    "source": {
        "csv_path": "/absolute/path/to/data_files/diagram_sheet_2.csv",
        "source_notes": [
            "Sources: IEA",
            "Spanish NECP 2021 - 2030",
            "Greek NECP 2021 - 2030",
            "California Energy Commission",
            "Israeli Electricity Authority & Ministry of Energy"
        ]
    },
    "prd_notes": {
        "filter_2030_mandatory": true,
        "solar_not_published": "When the solar filter is on, list `regions_without_solar_data` beside the chart (PRD: countries without solar data)."
    }
}
```

**Notes:**
- 2030 targets are always included (mandatory per PRD); 2050 and solar share are toggleable.
- `regions_without_solar_data` lists regions where solar share is `null` (currently all regions have data).
- `validation` flags rows where solar share exceeds the 2030 renewable target (sanity check).
- `source.source_notes` contains the reference citations from the original data sheet.

---

##### GET /api/v1/renewables/delivery-4/international-renewable-comparison/export

**Description:** Export Diagram 2 to Excel

**Query Parameters:**

- `include_2050_targets` (optional, bool, default `true`)
- `include_solar_share` (optional, bool, default `true`)

**Response:** Streamed Excel file (`delivery4_diagram2_international_renewable_comparison.xlsx`) with up to four sheets:
- **Diagram 2 data** — region, region_key, solar_share_2024, renewable_target_2030, renewable_target_2050
- **Meta** — diagram ID, titles, value unit, filter state, source CSV path
- **Sources** — reference citations from the data sheet
- **No solar data** — regions missing solar data (only present when the solar filter is on and gaps exist)

---

### Data Sources

#### Source 1: Diagram 1 CSV — Israel Forecast Trajectory

| Property | Details |
|---|---|
| **File** | `data_files/diagram_sheet_1.csv` |
| **Encoding** | `utf-8-sig` |
| **Records** | 31 yearly rows (2020–2050) + header/label rows |
| **Key Columns** | Year, שיעור מתחדשות (Renewable rate), צפי ריאלי (Realistic forecast), יעדי משרד האנרגיה (Ministry target), יעדי NZO (NZO target), פקטור צפי ריאלי (Factor) |
| **Service** | `app/services/delivery4_forecasts_service.py` → `get_israel_forecast()` |
| **Env Override** | `DELIVERY4_DIAGRAM1_CSV_PATH` |

#### Source 2: Diagram 2 CSV — International Comparison

| Property | Details |
|---|---|
| **File** | `data_files/diagram_sheet_2.csv` |
| **Encoding** | `utf-8-sig` |
| **Records** | 6 country/region rows + header/label/source rows |
| **Key Columns** | Region (EN), Region (HE), שיעור הייצור הסולארי בשנת 2024 (Solar share 2024), יעד אנרגיה מתחדשת לשנת 2030 (2030 target), יעד אנרגיה מתחדשת לשנת 2050 (2050 target) |
| **Service** | `app/services/delivery4_forecasts_service.py` → `get_international_comparison()` |
| **Env Override** | `DELIVERY4_DIAGRAM2_CSV_PATH` |

### Postman & Verification

A dedicated Postman collection (`postman/Delivery_4_Endpoints.postman_collection.json`) covers all Delivery 4 endpoints. Set the collection variables `baseUrl` (`http://localhost:8002` by default) and `apiKey` (set to your `INTERNAL_API_KEY`). The `X-Api-Key` header is injected automatically via collection-level API Key auth.

Verified test results:

```
PASS  Diagram 1 - Renewable Forecast Israel              data: 31 years (2020–2050)
PASS  Diagram 1 - Export                                  3 Excel sheets
PASS  Diagram 2 - International Comparison (defaults)     regions: 6
PASS  Diagram 2 - International Comparison (2030 only)    regions: 6 (no solar/2050)
PASS  Diagram 2 - Export (defaults)                       4 Excel sheets
PASS  Diagram 2 - Export (2030 only)                      2 Excel sheets
PASS  Compatibility alias /api/v1/renewables/*            matches primary
PASS  Compatibility alias /api/v1/forecasts/*             matches primary
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

- Check `NOGA_API_TOKEN` / `CO2_TOKEN` are set correctly
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

- Set actual `NOGA_API_TOKEN`, `CO2_TOKEN`, `PROXY_URL`, `INTERNAL_API_KEY`, `SMP_TOKEN`

---
