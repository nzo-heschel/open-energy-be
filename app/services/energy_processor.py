class EnergyProcessor:

    @staticmethod
    def flatten(raw):
        """ Convert raw NOGA days → flat list of rows """
        flat = []
        for day in raw:
            date = day["date"]
            time_items = day[list(day.keys())[1]]
            for item in time_items:
                row = {"date": date}
                row.update(item)
                flat.append(row)
        return flat

    @staticmethod
    def aggregate(flat):
        """Calculate hierarchy 1 + hierarchy 2"""

        # mapping
        groups = {
            "fossil": ["coal", "natural_gas", "diesel"],
            "renewable": ["photoVoltaic", "bio_Gas", "wind", "termo_Soler", "storage"],
            "other": ["other", "pumpedStorage"]
        }

        level1 = {"fossil": 0, "renewable": 0, "other": 0}
        level2 = {"fossil": {}, "renewable": {}, "other": {}}

        for row in flat:
            for main, subs in groups.items():
                for s in subs:
                    if s not in row:
                        continue
                    val = row[s]
                    level1[main] += val
                    level2[main][s] = level2[main].get(s, 0) + val

        total = sum(level1.values())

        percentages = {
            k: round((v / total) * 100, 2) if total > 0 else 0
            for k, v in level1.items()
        }

        return {
            "total": total,
            "level1": level1,
            "level2": level2,
            "percentages": percentages
        }
