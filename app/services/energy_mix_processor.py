# app/services/energy_mix_processor.py

class EnergyMixProcessor:

    @staticmethod
    def aggregate(raw_data):
        """
        Aggregates energy production data into totals, categories, and percentages.

        Args:
            raw_data (list[dict]): List of energy production records.

        Returns:
            dict: Aggregated data with level1, level2, percentages, and total_production.
        """
        # Define all possible keys for consistency
        fossil_keys = ["coal", "natural_Gas"]
        renewable_keys = ["photoVoltaic", "wind", "bio_Gas", "termo_Soler"]
        other_keys = ["storage", "batteries", "other", "pumpedStorage"]

        # Initialize totals
        totals = {key: 0 for key in fossil_keys + renewable_keys + other_keys}

        # Sum all records safely
        for record in raw_data:
            if not isinstance(record, dict):
                continue  # skip invalid entries
            for key in totals.keys():
                totals[key] += record.get(key, 0)

        # Level 1 totals
        total_fossil = sum(totals[key] for key in fossil_keys)
        total_renewable = sum(totals[key] for key in renewable_keys)
        total_other = sum(totals[key] for key in other_keys)
        total_all = total_fossil + total_renewable + total_other

        # Percentages (safe division)
        percentages = {
            "Fossil energy": total_fossil / total_all * 100 if total_all else 0,
            "Renewable energy": total_renewable / total_all * 100 if total_all else 0,
            "Other": total_other / total_all * 100 if total_all else 0,
        }

        # Level 2 breakdown
        level2 = {
            "Fossil energy": {key: totals[key] for key in fossil_keys},
            "Renewable energy": {key: totals[key] for key in renewable_keys},
            "Other": {key: totals[key] for key in other_keys},
        }

        # Level 1 summary
        level1 = {
            "Fossil energy": total_fossil,
            "Renewable energy": total_renewable,
            "Other": total_other,
        }

        return {
            "level1": level1,
            "level2": level2,
            "percentages": percentages,
            "total_production": total_all
        }
