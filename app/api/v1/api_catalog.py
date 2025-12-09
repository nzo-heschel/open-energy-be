# app/api/v1/api_catalog.py
from fastapi import APIRouter

router = APIRouter(prefix="/apis", tags=["API Catalog"])

# Catalog_built from README (1).md and inline endpoint docs.
API_CATALOG = [
    {
        "title": "Energy Overview",
        "link": "/api/v1/energy/overview",
        "method": "GET",
        "description": "Hierarchical_breakdown of energy sources with totals and renewable share percentages.",
        "params": [
            "start_date (optional, YYYY-MM-DD)",
            "end_date (optional, YYYY-MM-DD)",
        ],
        "sample_response": ["200 OK"],
        "sample_response_body": [
            {
                "start_date": "2024-12-05",
                "end_date": "2025-12-05",
                "filter": "year",
                "categories": [
                    {
                        "category_name": "renewables",
                        "total_value": 12193200.523333317,
                        "sub_categories": [
                            {"sub_category_name": "photo_voltaic", "value": 10518690.135},
                            {"sub_category_name": "biogas", "value": 83390.60166666686},
                            {"sub_category_name": "wind", "value": 840861.7166666664},
                            {"sub_category_name": "solar_thermal", "value": 750258.0699999835},
                            {"sub_category_name": "pv_storage", "value": 0},
                        ],
                    },
                    {
                        "category_name": "non_renewables",
                        "total_value": 66691009.1500001,
                        "sub_categories": [
                            {"sub_category_name": "coal", "value": 8057076.353333344},
                            {"sub_category_name": "natural_gas", "value": 58628439.924166754},
                            {"sub_category_name": "diesel", "value": 5492.8725},
                        ],
                    },
                    {
                        "category_name": "other",
                        "total_value": 1570473.8825000045,
                        "sub_categories": [
                            {"sub_category_name": "other", "value": 265147.95249999943},
                            {"sub_category_name": "pumped_storage", "value": 1305325.930000005},
                        ],
                    },
                ],
                "category_percentages": {
                    "renewables": 15.16,
                    "non_renewables": 82.89,
                    "other": 1.95,
                },
                "tooltip": (
                    "The chart shows Israel's electricity generation mix and illustrates the different energy sources: "
                    "fossil (coal, natural gas, diesel) and renewables (PV,_biogas, wind, solar). Data updated hourly "
                    "from NOGA."
                ),
                "total": 80454683.55583341,
                "level1": {
                    "fossil_energy": 66691009.150000095,
                    "renewable_energy": 12193200.523333317,
                    "other": 1570473.8825000045,
                },
                "level2": {
                    "fossil_energy": {
                        "coal": 8057076.353333344,
                        "natural_gas": 58628439.924166754,
                        "diesel": 5492.8725,
                    },
                    "renewable_energy": {
                        "photovoltaic": 10518690.135,
                        "biogas": 83390.60166666686,
                        "wind": 840861.7166666664,
                        "solar": 750258.0699999835,
                    },
                    "other": {
                        "other": 265147.95249999943,
                        "pumped_storage": 1305325.930000005,
                    },
                },
                "renewable_generation": 12193200.523333317,
                "renewable_share_percent": 15.16,
            }
        ],
    },
    {
        "title": "Energy Production Mix",
        "link": "/api/v1/energy/production-mix",
        "method": "GET",
        "description": "Aggregated electricity production mix_by source type (fossil, renewable, other).",
        "params": [
            "start_date (optional, YYYY-MM-DD)",
            "end_date (optional, YYYY-MM-DD)",
        ],
        "sample_response": ["200 OK"],
        "sample_response_body": [
            {
                "start_date": "2025-11-05",
                "end_date": "2025-12-05",
                "filter": "month",
                "level1": {
                    "Non-renewables": 4848764.2775,
                    "Renewables": 746006.005,
                    "Other": 145755.1475,
                },
                "level2": {
                    "Non-renewables": {
                        "coal": 426128.9025,
                        "natural_gas": 4422635.375,
                        "diesel": 0,
                    },
                    "Renewables": {
                        "photoVoltaic": 581749.4041666667,
                        "biogas": 6464.578333333333,
                        "wind": 69364.78416666666,
                        "solar_thermal": 31179.23,
                        "pv_storage": 57248.00833333333,
                    },
                    "Other": {
                        "other": 19267.07,
                        "pumped_storage": 126488.0775,
                    },
                },
                "total_generation": 5740525.43,
                "renewable_share_percent": 13,
                "categories": [
                    {
                        "category_name": "renewables",
                        "total_value": 746006.005,
                        "sub_categories": [
                            {"sub_category_name": "photo_voltaic", "value": 581749.4041666667},
                            {"sub_category_name": "biogas", "value": 6464.578333333333},
                            {"sub_category_name": "wind", "value": 69364.78416666666},
                            {"sub_category_name": "solar_thermal", "value": 31179.23},
                            {"sub_category_name": "pv_storage", "value": 57248.00833333333},
                        ],
                    },
                    {
                        "category_name": "non_renewables",
                        "total_value": 4848764.2775,
                        "sub_categories": [
                            {"sub_category_name": "coal", "value": 426128.9025},
                            {"sub_category_name": "natural_gas", "value": 4422635.375},
                            {"sub_category_name": "diesel", "value": 0},
                        ],
                    },
                    {
                        "category_name": "other",
                        "total_value": 145755.1475,
                        "sub_categories": [
                            {"sub_category_name": "other", "value": 19267.07},
                            {"sub_category_name": "pumped_storage", "value": 126488.0775},
                        ],
                    },
                ],
                "tooltip": (
                    "The pie chart shows Israel's electricity generation mix and illustrates the different energy "
                    "sources: fossil (coal, natural gas, diesel), renewables (photovoltaic,_biogas, wind, "
                    "solar-thermal, photovoltaic with storage), and other (other, pumped storage). Data are updated "
                    "hourly from the NOGA system operator."
                ),
            }
        ],
    },
    {
        "title": "System Marginal Price (SMP)",
        "link": "/api/v1/energy/smp",
        "method": "GET",
        "description": "System Marginal Price (electricity market clearing price) data.",
        "params": [
            "start_date (optional, defaults to last 1 day; YYYY-MM-DD)",
            "end_date (optional, YYYY-MM-DD)",
        ],
        "sample_response": ["200 OK"],
        "sample_response_body": [
            {
                "start_date": "2023-10-15",
                "end_date": "2023-10-15",
                "view": "day",
                "chart_with_constraints": [
                    {"hour": "00:00", "price": 425.5},
                    {"hour": "01:00", "price": 398.2},
                ],
                "chart_without_constraints": [
                    {"hour": "00:00", "price": 420.0}
                ],
                "min_price": 380.5,
                "max_price": 510.3,
                "avg_price": 445.2,
            }
        ],
    },
    {
        "title": "SMP Production vs Marginal Price",
        "link": "/api/v1/energy/smp-production-vs-marginal-price",
        "method": "GET",
        "description": "Correlate electricity production with marginal pricing for market analysis.",
        "params": [
            "start_date (optional, YYYY-MM-DD)",
            "end_date (optional, YYYY-MM-DD)",
        ],
        "sample_response": ["200 OK"],
        "sample_response_body": [
            {
                "start_date": "2023-10-15",
                "end_date": "2023-10-15",
                "view": "day",
                "smp_series": [
                    {"timestamp": "2023-10-15T00:00:00", "smp": 425.5}
                ],
                "net_demand_series": [
                    {"timestamp": "2023-10-15T00:00:00", "net_demand": 3200.1}
                ],
                "combined_series": [
                    {
                        "timestamp": "2023-10-15T00:00:00",
                        "smp": 425.5,
                        "net_demand": 3200.1,
                    }
                ],
                "correlation": [
                    {"smp": 425.5, "net_demand": 3200.1}
                ],
                "daily_smp": [
                    {"date": "2023-10-15", "daily_smp_avg": 440.2}
                ],
                "daily_average": [
                    {"period": "2023-10-15", "avg_smp": 440.2}
                ],
                "monthly_average": [
                    {"period": "2023-10", "avg_smp": 410.0}
                ],
            }
        ],
    },
    {
        "title": "Private Supplier Connected Consumers",
        "link": "/api/v1/private-supplier-connected-consumers",
        "method": "GET",
        "description": "Monthly time series of consumers connected to private electricity suppliers.",
        "params": [
            "start_date (optional, MM-YYYY)",
            "end_date (optional, MM-YYYY)",
        ],
        "sample_response": ["200 OK"],
        "sample_response_body": [
            {
                "start_date": "2024-11-01",
                "end_date": "2025-10-01",
                "unit": "count",
                "labels": {
                    "month": "Month",
                    "total_consumers": "Total Consumers",
                    "new_additions": "New Additions",
                },
                "data": [
                    {"month": "2024-11", "total_consumers": 319380, "new_additions": 74192},
                    {"month": "2024-12", "total_consumers": 375904, "new_additions": 56524},
                    {"month": "2025-01", "total_consumers": 422893, "new_additions": 46989},
                    {"month": "2025-02", "total_consumers": 497333, "new_additions": 74440},
                    {"month": "2025-03", "total_consumers": 535441, "new_additions": 38108},
                    {"month": "2025-04", "total_consumers": 576520, "new_additions": 41079},
                    {"month": "2025-05", "total_consumers": 624441, "new_additions": 47921},
                    {"month": "2025-06", "total_consumers": 685173, "new_additions": 60732},
                    {"month": "2025-07", "total_consumers": 736317, "new_additions": 51144},
                    {"month": "2025-08", "total_consumers": 770677, "new_additions": 34360},
                    {"month": "2025-09", "total_consumers": 801111, "new_additions": 30434},
                    {"month": "2025-10", "total_consumers": 852353, "new_additions": 51242},
                ],
                "segments": {
                    "location": [
                        {
                            "month": "2024-11",
                            "location": "existing_regulation",
                            "total_consumers": 139323,
                            "new_additions": 19354,
                        },
                        {
                            "month": "2024-12",
                            "location": "existing_regulation",
                            "total_consumers": 172587,
                            "new_additions": 33264,
                        },
                        {
                            "month": "2025-01",
                            "location": "existing_regulation",
                            "total_consumers": 195807,
                            "new_additions": 23220,
                        },
                        {
                            "month": "2025-02",
                            "location": "existing_regulation",
                            "total_consumers": 238983,
                            "new_additions": 43176,
                        },
                        {
                            "month": "2025-03",
                            "location": "existing_regulation",
                            "total_consumers": 256147,
                            "new_additions": 17164,
                        },
                        {
                            "month": "2025-04",
                            "location": "existing_regulation",
                            "total_consumers": 272176,
                            "new_additions": 16029,
                        },
                        {
                            "month": "2025-05",
                            "location": "existing_regulation",
                            "total_consumers": 299403,
                            "new_additions": 27227,
                        },
                        {
                            "month": "2025-06",
                            "location": "existing_regulation",
                            "total_consumers": 335425,
                            "new_additions": 36022,
                        },
                        {
                            "month": "2025-07",
                            "location": "existing_regulation",
                            "total_consumers": 375110,
                            "new_additions": 39685,
                        },
                        {
                            "month": "2025-08",
                            "location": "existing_regulation",
                            "total_consumers": 392534,
                            "new_additions": 17424,
                        },
                        {
                            "month": "2025-09",
                            "location": "existing_regulation",
                            "total_consumers": 413457,
                            "new_additions": 20923,
                        },
                        {
                            "month": "2025-10",
                            "location": "existing_regulation",
                            "total_consumers": 445538,
                            "new_additions": 32081,
                        },
                        {
                            "month": "2024-11",
                            "location": "competitive_supply",
                            "total_consumers": 180057,
                            "new_additions": 54838,
                        },
                        {
                            "month": "2024-12",
                            "location": "competitive_supply",
                            "total_consumers": 203317,
                            "new_additions": 23260,
                        },
                        {
                            "month": "2025-01",
                            "location": "competitive_supply",
                            "total_consumers": 227086,
                            "new_additions": 23769,
                        },
                        {
                            "month": "2025-02",
                            "location": "competitive_supply",
                            "total_consumers": 258350,
                            "new_additions": 31264,
                        },
                        {
                            "month": "2025-03",
                            "location": "competitive_supply",
                            "total_consumers": 279294,
                            "new_additions": 20944,
                        },
                        {
                            "month": "2025-04",
                            "location": "competitive_supply",
                            "total_consumers": 304344,
                            "new_additions": 25050,
                        },
                        {
                            "month": "2025-05",
                            "location": "competitive_supply",
                            "total_consumers": 325038,
                            "new_additions": 20694,
                        },
                        {
                            "month": "2025-06",
                            "location": "competitive_supply",
                            "total_consumers": 349748,
                            "new_additions": 24710,
                        },
                        {
                            "month": "2025-07",
                            "location": "competitive_supply",
                            "total_consumers": 361207,
                            "new_additions": 11459,
                        },
                        {
                            "month": "2025-08",
                            "location": "competitive_supply",
                            "total_consumers": 378143,
                            "new_additions": 16936,
                        },
                        {
                            "month": "2025-09",
                            "location": "competitive_supply",
                            "total_consumers": 387654,
                            "new_additions": 9511,
                        },
                        {
                            "month": "2025-10",
                            "location": "competitive_supply",
                            "total_consumers": 406815,
                            "new_additions": 19161,
                        },
                    ],
                    "sector": [
                        {
                            "month": "2024-11",
                            "sector": "residential",
                            "total_consumers": 276402,
                            "new_additions": 65514,
                        },
                        {
                            "month": "2024-12",
                            "sector": "residential",
                            "total_consumers": 328797,
                            "new_additions": 52395,
                        },
                        {
                            "month": "2025-01",
                            "sector": "residential",
                            "total_consumers": 368627,
                            "new_additions": 39830,
                        },
                        {
                            "month": "2025-02",
                            "sector": "residential",
                            "total_consumers": 437162,
                            "new_additions": 68535,
                        },
                        {
                            "month": "2025-03",
                            "sector": "residential",
                            "total_consumers": 471339,
                            "new_additions": 34177,
                        },
                        {
                            "month": "2025-04",
                            "sector": "residential",
                            "total_consumers": 505448,
                            "new_additions": 34109,
                        },
                        {
                            "month": "2025-05",
                            "sector": "residential",
                            "total_consumers": 549584,
                            "new_additions": 44136,
                        },
                        {
                            "month": "2025-06",
                            "sector": "residential",
                            "total_consumers": 604799,
                            "new_additions": 55215,
                        },
                        {
                            "month": "2025-07",
                            "sector": "residential",
                            "total_consumers": 648980,
                            "new_additions": 44181,
                        },
                        {
                            "month": "2025-08",
                            "sector": "residential",
                            "total_consumers": 680040,
                            "new_additions": 31060,
                        },
                        {
                            "month": "2025-09",
                            "sector": "residential",
                            "total_consumers": 707506,
                            "new_additions": 27466,
                        },
                        {
                            "month": "2025-10",
                            "sector": "residential",
                            "total_consumers": 753549,
                            "new_additions": 46043,
                        },
                        {
                            "month": "2024-11",
                            "sector": "non_residential",
                            "total_consumers": 42978,
                            "new_additions": 8678,
                        },
                        {
                            "month": "2024-12",
                            "sector": "non_residential",
                            "total_consumers": 47107,
                            "new_additions": 4129,
                        },
                        {
                            "month": "2025-01",
                            "sector": "non_residential",
                            "total_consumers": 54266,
                            "new_additions": 7159,
                        },
                        {
                            "month": "2025-02",
                            "sector": "non_residential",
                            "total_consumers": 60171,
                            "new_additions": 5905,
                        },
                        {
                            "month": "2025-03",
                            "sector": "non_residential",
                            "total_consumers": 64102,
                            "new_additions": 3931,
                        },
                        {
                            "month": "2025-04",
                            "sector": "non_residential",
                            "total_consumers": 71072,
                            "new_additions": 6970,
                        },
                        {
                            "month": "2025-05",
                            "sector": "non_residential",
                            "total_consumers": 74857,
                            "new_additions": 3785,
                        },
                        {
                            "month": "2025-06",
                            "sector": "non_residential",
                            "total_consumers": 80374,
                            "new_additions": 5517,
                        },
                        {
                            "month": "2025-07",
                            "sector": "non_residential",
                            "total_consumers": 87337,
                            "new_additions": 6963,
                        },
                        {
                            "month": "2025-08",
                            "sector": "non_residential",
                            "total_consumers": 90637,
                            "new_additions": 3300,
                        },
                        {
                            "month": "2025-09",
                            "sector": "non_residential",
                            "total_consumers": 93605,
                            "new_additions": 2968,
                        },
                        {
                            "month": "2025-10",
                            "sector": "non_residential",
                            "total_consumers": 98804,
                            "new_additions": 5199,
                        },
                    ],
                    "meter_type": [
                        {
                            "month": "2024-11",
                            "meter_type": "virtual_suppliers",
                            "total_consumers": 180057,
                            "new_additions": 54838,
                        },
                        {
                            "month": "2024-12",
                            "meter_type": "virtual_suppliers",
                            "total_consumers": 203317,
                            "new_additions": 23260,
                        },
                        {
                            "month": "2025-01",
                            "meter_type": "virtual_suppliers",
                            "total_consumers": 227086,
                            "new_additions": 23769,
                        },
                        {
                            "month": "2025-02",
                            "meter_type": "virtual_suppliers",
                            "total_consumers": 258350,
                            "new_additions": 31264,
                        },
                        {
                            "month": "2025-03",
                            "meter_type": "virtual_suppliers",
                            "total_consumers": 279294,
                            "new_additions": 20944,
                        },
                        {
                            "month": "2025-04",
                            "meter_type": "virtual_suppliers",
                            "total_consumers": 304344,
                            "new_additions": 25050,
                        },
                        {
                            "month": "2025-05",
                            "meter_type": "virtual_suppliers",
                            "total_consumers": 325038,
                            "new_additions": 20694,
                        },
                        {
                            "month": "2025-06",
                            "meter_type": "virtual_suppliers",
                            "total_consumers": 349748,
                            "new_additions": 24710,
                        },
                        {
                            "month": "2025-07",
                            "meter_type": "virtual_suppliers",
                            "total_consumers": 361207,
                            "new_additions": 11459,
                        },
                        {
                            "month": "2025-08",
                            "meter_type": "virtual_suppliers",
                            "total_consumers": 378143,
                            "new_additions": 16936,
                        },
                        {
                            "month": "2025-09",
                            "meter_type": "virtual_suppliers",
                            "total_consumers": 387654,
                            "new_additions": 9511,
                        },
                        {
                            "month": "2025-10",
                            "meter_type": "virtual_suppliers",
                            "total_consumers": 406815,
                            "new_additions": 19161,
                        },
                        {
                            "month": "2024-11",
                            "meter_type": "suppliers_with_generation",
                            "total_consumers": 139323,
                            "new_additions": 19354,
                        },
                        {
                            "month": "2024-12",
                            "meter_type": "suppliers_with_generation",
                            "total_consumers": 172587,
                            "new_additions": 33264,
                        },
                        {
                            "month": "2025-01",
                            "meter_type": "suppliers_with_generation",
                            "total_consumers": 195807,
                            "new_additions": 23220,
                        },
                        {
                            "month": "2025-02",
                            "meter_type": "suppliers_with_generation",
                            "total_consumers": 238983,
                            "new_additions": 43176,
                        },
                        {
                            "month": "2025-03",
                            "meter_type": "suppliers_with_generation",
                            "total_consumers": 256147,
                            "new_additions": 17164,
                        },
                        {
                            "month": "2025-04",
                            "meter_type": "suppliers_with_generation",
                            "total_consumers": 272176,
                            "new_additions": 16029,
                        },
                        {
                            "month": "2025-05",
                            "meter_type": "suppliers_with_generation",
                            "total_consumers": 299403,
                            "new_additions": 27227,
                        },
                        {
                            "month": "2025-06",
                            "meter_type": "suppliers_with_generation",
                            "total_consumers": 335425,
                            "new_additions": 36022,
                        },
                        {
                            "month": "2025-07",
                            "meter_type": "suppliers_with_generation",
                            "total_consumers": 375110,
                            "new_additions": 39685,
                        },
                        {
                            "month": "2025-08",
                            "meter_type": "suppliers_with_generation",
                            "total_consumers": 392534,
                            "new_additions": 17424,
                        },
                        {
                            "month": "2025-09",
                            "meter_type": "suppliers_with_generation",
                            "total_consumers": 413457,
                            "new_additions": 20923,
                        },
                        {
                            "month": "2025-10",
                            "meter_type": "suppliers_with_generation",
                            "total_consumers": 445538,
                            "new_additions": 32081,
                        },
                    ],
                },
                "note": None,
            }
        ],
    },
    {
        "title": "Switching Requests",
        "link": "/api/v1/switching-requests",
        "method": "GET",
        "description": "Consumer electricity supplier switching request data split_by residential and non_residential.",
        "params": [
            "customer_type (optional, residential | non_residential)",
        ],
        "sample_response": ["200 OK"],
        "sample_response_body": [
            {
                "filter": "all",
                "unit": "count",
                "charts": {
                    "by_customer_type": {
                        "label": "Requests_by customer type",
                        "data": [
                            {"label": "residential", "count": 279230},
                            {"label": "non_residential", "count": 24603},
                        ],
                    },
                    "by_region": {
                        "label": "Requests_by region",
                        "data": [
                            {"label": "central", "count": 104728},
                            {"label": "tel_aviv", "count": 59948},
                            {"label": "south", "count": 39031},
                            {"label": "haifa", "count": 37072},
                            {"label": "jerusalem", "count": 25287},
                            {"label": "north", "count": 19671},
                            {"label": "judea_samaria", "count": 18002},
                            {"label": "other", "count": 94},
                        ],
                    },
                    "by_voltage": {
                        "label": "Requests_by voltage level",
                        "data": [
                            {"label": "low", "count": 301425},
                            {"label": "high", "count": 2367},
                            {"label": "extra_high", "count": 41},
                        ],
                    },
                    "by_meter_type": {
                        "label": "Requests_by meter type",
                        "data": [
                            {"label": "smart", "count": 217218},
                            {"label": "basic", "count": 86615},
                        ],
                    },
                    "by_regulation": {
                        "label": "Requests_by regulation",
                        "data": [
                            {"label": "existing_regulation", "count": 196591},
                            {"label": "competitive_supply", "count": 107242},
                        ],
                    },
                    "by_connection_size": {
                        "label": "Requests_by connection size (GVA)",
                        "data": [
                            {"label": "0-0.05", "count": 292011},
                            {"label": "0.05-0.1", "count": 4323},
                            {"label": "0.1-0.5", "count": 4429},
                            {"label": "0.5-1", "count": 992},
                            {"label": "1-5", "count": 1620},
                            {"label": "5+", "count": 458},
                        ],
                    },
                    "requests_by_status": {"label": "Requests_by status", "data": []},
                    "requests_by_rejection_reason": {
                        "label": "Requests_by rejection reason",
                        "data": [],
                    },
                    "total_requests": {
                        "label": "Total requests",
                        "data": [{"count": 303833}],
                    },
                },
            }
        ],
    },
]


@router.get("/")
async def list_apis():
    """
    Provide a single JSON payload describing the six published APIs.
    """
    return API_CATALOG
