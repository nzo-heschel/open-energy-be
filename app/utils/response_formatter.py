from typing import Dict, Iterable, List


# Mapping of categories and their source keys.
CATEGORY_CONFIG = [
    (
        "renewables",
        [
            (["photoVoltaic", "photovoltaic", "photovoltaicIntegrated", "photo_voltaic"], "photo_voltaic"),
            (["bio_Gas", "biogas"], "biogas"),
            (["wind"], "wind"),
            (["termo_Soler", "solar", "solar_thermal"], "solar_thermal"),
            (
                ["pv_storage", "photovoltaic_storage"],
                "pv_storage",
            ),
        ],
    ),
    (
        "non_renewables",
        [
            (["coal"], "coal"),
            (["natural_Gas", "natural_gas"], "natural_gas"),
            (["diesel", "Diesel"], "diesel"),
            (["mazut"], "fuel_oil"),
        ],
    ),
    (
        "other",
        [
            (["other"], "other"),
            (["batteries"], "batteries"),
            (["pumpedStorage", "pumped_storage", "pumpedStorageBattery"], "pumped_storage"),
        ],
    ),
]


def flatten_level2(level2: Dict) -> Dict[str, float]:
    """
    Flatten nested level2 structures into a single dict of sub_category -> value.
    """
    flat: Dict[str, float] = {}
    for category_values in level2.values():
        if not isinstance(category_values, dict):
            continue
        for key, value in category_values.items():
            flat[key] = flat.get(key, 0) + (value or 0)
    return flat


def _sum_keys(values: Dict[str, float], keys: Iterable[str]) -> float:
    return sum(values.get(k, 0) or 0 for k in keys)


def format_categories(sub_totals: Dict[str, float]) -> List[Dict]:
    """
    Convert aggregated subcategory totals into the target categories format.
    """
    categories: List[Dict] = []
    for category_name, sub_mappings in CATEGORY_CONFIG:
        sub_categories = []
        total_value = 0.0
        for sources, dest_name in sub_mappings:
            value = _sum_keys(sub_totals, sources)
            sub_categories.append(
                {
                    "sub_category_name": dest_name,
                    "value": value,
                }
            )
            total_value += value

        categories.append(
            {
                "category_name": category_name,
                "total_value": total_value,
                "sub_categories": sub_categories,
            }
        )

    return categories
