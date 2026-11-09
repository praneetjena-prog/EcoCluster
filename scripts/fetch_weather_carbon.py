import math
import os
import requests
import pandas as pd

COORDINATES = {
    "mumbai": {"lat": 19.0760, "lon": 72.8777, "base_ci": 710.0, "stress": 2.5, "cost": 0.12},
    "rajasthan": {"lat": 26.2389, "lon": 73.0243, "base_ci": 560.0, "stress": 5.0, "cost": 0.06},
    "stockholm": {"lat": 59.3293, "lon": 18.0686, "base_ci": 50.0, "stress": 1.0, "cost": 0.05},
    "oregon": {"lat": 45.7138, "lon": -119.5325, "base_ci": 120.0, "stress": 1.5, "cost": 0.07},
}

def calculate_wet_bulb_stull(temp_c: float, rh_pct: float) -> float:
    """
    Computes ambient wet-bulb temperature using Stull's formula (accurate within 1C).
    T_wb = T * atan(0.151977 * (rh + 8.313659)^0.5) + atan(T + rh) - atan(rh - 1.676331)
           + 0.00391838 * (rh^1.5) * atan(0.023101 * rh) - 4.686035
    """
    t = temp_c
    rh = max(1.0, min(100.0, rh_pct))

    term1 = t * math.atan(0.151977 * math.sqrt(rh + 8.313659))
    term2 = math.atan(t + rh)
    term3 = math.atan(rh - 1.676331)
    term4 = 0.00391838 * (rh ** 1.5) * math.atan(0.023101 * rh)
    term5 = -4.686035

    return round(term1 + term2 - term3 + term4 + term5, 2)

def fetch_regional_weather(region: str, lat: float, lon: float) -> pd.DataFrame:
    """Fetches 7 days of hourly dry-bulb temperature and humidity from Open-Meteo."""
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&hourly=temperature_2m,relative_humidity_2m"
        f"&forecast_days=7"
    )
    res = requests.get(url, timeout=10)
    res.raise_for_status()
    payload = res.json()["hourly"]

    records = []
    for h_idx, (timestamp, temp, rh) in enumerate(zip(payload["time"], payload["temperature_2m"], payload["relative_humidity_2m"])):
        twb = calculate_wet_bulb_stull(temp, rh)
        records.append({
            "hour": h_idx,
            "timestamp": timestamp,
            "dry_bulb_temp_c": temp,
            "relative_humidity_pct": rh,
            "wet_bulb_temp_c": twb,
        })
    return pd.DataFrame(records)

def main():
    os.makedirs("data/weather", exist_ok=True)
    os.makedirs("data/carbon", exist_ok=True)

    print("Fetching 7-day hourly reanalysis from Open-Meteo...")
    for region, meta in COORDINATES.items():
        try:
            df_weather = fetch_regional_weather(region, meta["lat"], meta["lon"])
            weather_path = f"data/weather/{region}.csv"
            df_weather.to_csv(weather_path, index=False)
            print(f"  [Weather] Saved {len(df_weather)} hours for {region:<10} -> {weather_path}")

            # Generate hourly carbon profiles based on diurnal solar/wind variation
            carbon_records = []
            for _, row in df_weather.iterrows():
                h = int(row["hour"])
                phase = (h % 24 / 24.0) * 2 * math.pi
                solar_dip = 500.0 if region == "rajasthan" else 70.0
                wind_dip = 40.0 if region in ["stockholm", "oregon"] else 0.0

                ci = max(10.0, meta["base_ci"] - solar_dip * max(0.0, math.cos(phase)) - wind_dip * max(0.0, -math.cos(phase)))
                carbon_records.append({
                    "hour": h,
                    "carbon_intensity_g_kwh": round(ci, 2),
                    "water_stress_multiplier": meta["stress"],
                    "cost_usd_kwh": meta["cost"],
                })

            df_carbon = pd.DataFrame(carbon_records)
            carbon_path = f"data/carbon/{region}.csv"
            df_carbon.to_csv(carbon_path, index=False)
            print(f"  [Carbon]  Saved {len(df_carbon)} hours for {region:<10} -> {carbon_path}")

        except Exception as e:
            print(f"Failed to fetch data for {region}: {e}")

if __name__ == "__main__":
    main()