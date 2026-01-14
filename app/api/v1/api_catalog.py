# app/api/v1/api_catalog.py
from typing import Any, Dict, List

from fastapi import APIRouter, Request

router = APIRouter(prefix="/apis", tags=["API Catalog"])

# Only surface public APIs (exclude admin/utility endpoints).
_ALLOWED_ENDPOINTS = {
    "/api/v1/energy/overview",
    "/api/v1/energy/production-mix",
    "/api/v1/energy/smp",
    "/api/v1/energy/smp-production-vs-marginal-price",
    "/api/v1/private-supplier-connected-consumers",
    "/api/v1/switching-requests",
}


def _normalize_path(path: str) -> str:
    if path != "/" and path.endswith("/"):
        return path[:-1]
    return path

# Legacy examples preserved from the previously hardcoded catalog for richer sample payloads.
LEGACY_EXAMPLES: Dict[tuple[str, str], Dict[str, Any]] = {
    ("/api/v1/energy/overview", "GET"): {
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
    ("/api/v1/energy/production-mix", "GET"): {
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
    ("/api/v1/energy/smp", "GET"): {
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
    ("/api/v1/energy/smp-production-vs-marginal-price", "GET"): {
        "sample_response": ["200 OK"],
        "sample_response_body": {
            "start_date": "2023-10-15",
            "end_date": "2023-10-15",
            "view": "day",
            "smp_series": [
                {"timestamp": "2023-10-15T00:00:00", "smp": 420.1},
                {"timestamp": "2023-10-15T01:00:00", "smp": 415.0},
            ],
            "net_demand_series": [
                {"timestamp": "2023-10-15T00:00:00", "net_demand": 4200.5},
                {"timestamp": "2023-10-15T01:00:00", "net_demand": 4150.2},
            ],
            "combined_series": [
                {"timestamp": "2023-10-15T00:00:00", "smp": 420.1, "net_demand": 4200.5},
                {"timestamp": "2023-10-15T01:00:00", "smp": 415.0, "net_demand": 4150.2},
            ],
            "correlation": [
                {"smp": 420.1, "net_demand": 4200.5},
                {"smp": 415.0, "net_demand": 4150.2},
            ],
            "daily_smp": [{"date": "2023-10-15", "daily_smp_avg": 417.55}],
            "daily_average": [{"period": "2023-10-15", "avg_smp": 417.55}],
            "monthly_average": [{"period": "2023-10", "avg_smp": 417.55}],
        },
    },
    ("/api/v1/private-supplier-connected-consumers", "GET"): {
        "sample_response": ["200 OK"],
        "sample_response_body": {
            "start_date": "2024-11-01",
            "end_date": "2025-10-01",
            "unit": "count",
            "labels": {
                "month": "Month",
                "total_consumers": "Total Consumers",
                "new_additions": "New Additions",
            },
            "data": [
                {"month": "2024-11", "total_consumers": 319380.0, "new_additions": 74192.0},
                {"month": "2024-12", "total_consumers": 375904.0, "new_additions": 56524.0},
                {"month": "2025-01", "total_consumers": 422893.0, "new_additions": 46989.0},
                {"month": "2025-02", "total_consumers": 497333.0, "new_additions": 74440.0},
                {"month": "2025-03", "total_consumers": 535441.0, "new_additions": 38108.0},
                {"month": "2025-04", "total_consumers": 576520.0, "new_additions": 41079.0},
            ],
            "segments": {
                "location": [
                    {"month": "2024-11", "location": "existing_regulation", "total_consumers": 139323.0, "new_additions": 19354.0},
                    {"month": "2024-12", "location": "existing_regulation", "total_consumers": 172587.0, "new_additions": 33264.0},
                    {"month": "2025-01", "location": "existing_regulation", "total_consumers": 195807.0, "new_additions": 23220.0},
                    {"month": "2025-02", "location": "existing_regulation", "total_consumers": 238983.0, "new_additions": 43176.0},
                    {"month": "2025-03", "location": "existing_regulation", "total_consumers": 256147.0, "new_additions": 17164.0},
                    {"month": "2025-04", "location": "existing_regulation", "total_consumers": 272176.0, "new_additions": 16029.0},
                ],
                "sector": [
                    {"month": "2024-11", "sector": "residential", "total_consumers": 276402.0, "new_additions": 65514.0},
                    {"month": "2024-12", "sector": "residential", "total_consumers": 328797.0, "new_additions": 52395.0},
                    {"month": "2025-01", "sector": "residential", "total_consumers": 368627.0, "new_additions": 39830.0},
                    {"month": "2025-02", "sector": "residential", "total_consumers": 437162.0, "new_additions": 68535.0},
                    {"month": "2025-03", "sector": "residential", "total_consumers": 471339.0, "new_additions": 34177.0},
                    {"month": "2025-04", "sector": "residential", "total_consumers": 505448.0, "new_additions": 34109.0},
                ],
                "meter_type": [
                    {"month": "2024-11", "meter_type": "virtual_suppliers", "total_consumers": 180057.0, "new_additions": 54838.0},
                    {"month": "2024-12", "meter_type": "virtual_suppliers", "total_consumers": 203317.0, "new_additions": 23260.0},
                    {"month": "2025-01", "meter_type": "virtual_suppliers", "total_consumers": 227086.0, "new_additions": 23769.0},
                    {"month": "2025-02", "meter_type": "virtual_suppliers", "total_consumers": 258350.0, "new_additions": 31264.0},
                    {"month": "2025-03", "meter_type": "virtual_suppliers", "total_consumers": 279294.0, "new_additions": 20944.0},
                    {"month": "2025-04", "meter_type": "virtual_suppliers", "total_consumers": 304344.0, "new_additions": 25050.0},
                ],
            },
            "note": None,
        },
    },
    ("/api/v1/switching-requests", "GET"): {
        "sample_response": ["200 OK"],
        "sample_response_body": [
            {
                "filter": {"customer_type": "all", "year": "all"},
                "unit": "count",
                "available_years": [2021],
                "start_year": 2021,
                "charts": {
                    "requests_by_status": {
                        "label": "Number of requests by status",
                        "data": [
                            {"label": "approved", "count": 611174},
                            {"label": "rejected", "count": 277708},
                        ],
                    },
                    "requests_by_customer_type": {
                        "label": "Number of requests by customer type",
                        "data": [
                            {"label": "residential", "count": 786336},
                            {"label": "non_residential", "count": 102546},
                        ],
                    },
                    "requests_by_regulation_type": {
                        "label": "Number of requests by regulation type",
                        "data": [
                            {"label": "suppliers_with_generation", "count": 472491},
                        ],
                    },
                    "requests_by_competition_type": {
                        "label": "Number of requests by supply competition/existing regulation",
                        "data": [
                            {"label": "existing_regulation", "count": 472491},
                        ],
                    },
                    "requests_by_rejection_reason": {
                        "label": "Number of requests by rejection reason",
                        "data": [
                            {"label": "missing_power_of_attorney", "count": 12457},
                            {"label": "meter_issues", "count": 8921},
                            {"label": "request_form_issues", "count": 10132},
                            {"label": "other", "count": 246198},
                        ],
                    },
                },
                "monthly_requests": [{"month": "2021-09", "requests": 157}],
                "monthly_rejections_by_reason": [
                    {
                        "month": "2021-09",
                        "missing_power_of_attorney": 12,
                        "meter_issues": 3,
                        "request_form_issues": 5,
                        "other": 2,
                        "total_rejections": 22,
                    }
                ],
                "total_requests": 888882,
                "total_rejections": 277708,
            }
        ],
    },
}

DESCRIPTIONS: Dict[str, str] = {
    "/api/v1/energy/overview": (
        "Hierarchical breakdown of generation by source (level1/level2), totals, renewable share, "
        "and inferred period for the requested date window (defaults to last 12 months)."
    ),
    "/api/v1/energy/production-mix": (
        "Aggregated electricity production mix using hourly averages of 5-minute NOGA data with level1/level2 totals, "
        "categories, and renewable share (defaults to the configured rolling window)."
    ),
    "/api/v1/energy/smp": (
        "System Marginal Price (market clearing price) with/without constraints, min/max/avg, and an adaptive view "
        "based on the requested date range."
    ),
    "/api/v1/energy/smp-production-vs-marginal-price": (
        "Correlates SMP prices with net demand and renewables; returns SMP, net demand, combined series, correlation, "
        "and daily/monthly averages for the requested window."
    ),
    "/api/v1/private-supplier-connected-consumers": (
        "Monthly time series of private supplier connected consumers with cumulative totals, new additions, and "
        "segment breakdowns (location, sector, meter type); defaults to the latest 12 months."
    ),
    "/api/v1/switching-requests": (
        "Consumer supplier switching requests split by status, customer type, regulation, competition type, and "
        "rejection reason, plus monthly totals; optional customer_type and year filters."
    ),
}

def _should_include(path: str) -> bool:
    return _normalize_path(path) in _ALLOWED_ENDPOINTS


def _first_example(content: Dict[str, Any]) -> Any:
    """
    Pick the first inline OpenAPI example if present.
    """
    for media in content.values():
        if not isinstance(media, dict):
            continue
        if "example" in media:
            return media["example"]
        examples = media.get("examples")
        if isinstance(examples, dict):
            for sample in examples.values():
                if isinstance(sample, dict) and "value" in sample:
                    return sample["value"]
    return None


def _format_params(operation: Dict[str, Any]) -> List[str]:
    params: List[str] = []
    for param in operation.get("parameters", []):
        schema = param.get("schema") or {}
        param_type = schema.get("type") or schema.get("title") or "any"
        required = "required" if param.get("required") else "optional"
        location = param.get("in", "query")
        default = schema.get("default")
        default_suffix = f", default={default}" if default is not None else ""
        params.append(
            f"{param.get('name')} ({location}, {param_type}, {required}{default_suffix})"
        )
    return params


def _pick_example(responses: Dict[str, Any]) -> Any:
    preferred = ["200", "201", "202"]
    order = preferred + [code for code in responses.keys() if code not in preferred]
    for code in order:
        resp = responses.get(code)
        if not resp:
            continue
        content = resp.get("content") or {}
        example = _first_example(content)
        if example is not None:
            return example
    return None


def _build_catalog(openapi_schema: Dict[str, Any]) -> List[Dict[str, Any]]:
    catalog: List[Dict[str, Any]] = []
    paths = openapi_schema.get("paths", {})

    def _clean_title(raw: str | None, fallback: str) -> str:
        if not raw:
            return fallback
        lower = raw.lower().lstrip()
        for verb in ("get ", "post ", "put ", "delete ", "patch ", "head ", "options "):
            if lower.startswith(verb):
                return raw[len(verb):].lstrip()
        return raw

    for path, methods in paths.items():
        normalized_path = _normalize_path(path)
        if not _should_include(normalized_path):
            continue
        for method, operation in methods.items():
            verb = method.upper()
            if verb in {"HEAD", "OPTIONS"} or not isinstance(operation, dict):
                continue
            responses = operation.get("responses") or {}
            entry = {
                "title": _clean_title(operation.get("summary"), operation.get("operationId") or path),
                "link": normalized_path,
                "method": verb,
                "description": DESCRIPTIONS.get(normalized_path) or operation.get("description"),
                "params": _format_params(operation),
                "sample_response": sorted(responses.keys()),
                "sample_response_body": _pick_example(responses),
            }

            override = LEGACY_EXAMPLES.get((normalized_path, verb))
            if override:
                if "sample_response" in override:
                    entry["sample_response"] = override["sample_response"]
                if "sample_response_body" in override:
                    entry["sample_response_body"] = override["sample_response_body"]

            catalog.append(entry)

    catalog.sort(key=lambda item: (item["link"], item["method"]))
    return catalog


@router.get("/", summary="API catalog", description="All registered /api endpoints.")
async def list_apis(request: Request) -> List[Dict[str, Any]]:
    """
    Build the catalog dynamically from the live OpenAPI schema.
    """
    openapi_schema = request.app.openapi()
    return _build_catalog(openapi_schema)