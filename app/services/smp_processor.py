# app/services/smp_processor.py
from typing import Dict, List
class SMPProcessor:
    @staticmethod
    def process_smp_data(raw_data: List[Dict]) -> Dict:
        """
        Processes the SMP data and returns two separate chart data sets (with constraints, without constraints)
        and a correlation view showing net demand.
        """
        # Normalize payload shape: API returns list of day entries under `energy`.
        energy_data: List[Dict] = []
        if isinstance(raw_data, dict):
            energy_data = raw_data.get("energy", [])
        else:
            energy_data = raw_data or []
        
        return SMPProcessor._process_day_data(energy_data)
    @staticmethod
    def _process_day_data(energy_data: List[Dict]) -> Dict:
        # Logic for daily processing
        # Process data for each day and calculate daily average for each time (24 ticks)
        without_constraints = []
        with_constraints = []
        correlation_data = []
        for day in energy_data:
            date = day.get('date')
            # Use productionMixData if present; fall back to forecastProductionMix.
            production_data = day.get('productionMixData') or day.get('forecastProductionMix') or []
            if not production_data:
                continue
            total_without_constraints = 0.0
            total_with_constraints = 0.0
            total_net_demand = 0.0
            for time_entry in production_data:
                total_without_constraints += time_entry.get('coal', 0)
                total_with_constraints += time_entry.get('natural_Gas', 0)
                total_net_demand += time_entry.get('actual_Demand', 0) - time_entry.get('renewableSum', 0)
            count = len(production_data)
            if count == 0:
                continue
            without_constraints.append({'time': date, 'price': total_without_constraints / count})
            with_constraints.append({'time': date, 'price': total_with_constraints / count})
            correlation_data.append({'time': date, 'net_demand': total_net_demand / count})
        return {
            "chart1": without_constraints,
            "chart2": with_constraints,
            "correlation_view": correlation_data
        }
    @staticmethod
    def _process_month_data(raw_data: List[Dict]) -> Dict:
        # Logic for monthly processing: calculate daily averages, then average those for the month
        pass
    @staticmethod
    def _process_year_data(raw_data: List[Dict]) -> Dict:
        # Logic for yearly processing: calculate monthly averages, then average those for the year
        pass
    @staticmethod
    def _process_between_dates_data(raw_data: List[Dict]) -> Dict:
        # Logic for between dates: handle the provided range and calculate averages
        pass
