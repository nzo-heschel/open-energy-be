from fastapi import APIRouter
from app.services.energy_mix_processor import EnergyMixProcessor
from app.services.noga_service import NogaService
from datetime import timedelta


router = APIRouter()

COLOR_PALETTE = {
    "coal": "#6C4F3D",
    "natural_Gas": "#FFA500",
    "photoVoltaic": "#FFD700",
    "wind": "#00BFFF",
    "bio_Gas": "#32CD32",
    "termo_Soler": "#FF6347",
    "storage": "#8A2BE2",
    "batteries": "#FF69B4",
    "other": "#A9A9A9",
    "pumpedStorage": "#00FF7F",
}

@router.get("/production-mix/ui")
async def get_energy_mix_ui(filter: str = "today"):
    from datetime import datetime

    # Parse dates same as energy.py
    now = datetime.now()
    if filter == "today":
        start = datetime(now.year, now.month, now.day)
        end = start + timedelta(days=1)
    elif filter == "this_year":
        start = datetime(now.year, 1, 1)
        end = datetime(now.year + 1, 1, 1)
    else:
        start = datetime(now.year, now.month, now.day)
        end = start + timedelta(days=1)

    raw = await NogaService.get_production_mix(start, end)
    records = [record for day in raw for record in day["records"]]
    result = EnergyMixProcessor.aggregate(records)

    level2_ui = {}
    for category, sources in result.get("level2", {}).items():
        level2_ui[category] = [
            {"name": sub, "value": value, "color": COLOR_PALETTE.get(sub, "#000000")}
            for sub, value in sources.items()
        ]

    return {
        "level1": result.get("level1", {}),
        "level2": level2_ui,
        "percentages": result.get("percentages", {}),
        "total_production": result.get("total_production", 0)
    }
