"""KF-WaterWise — 天気データとETo計算で水やり判定を行うアプリ。"""

import streamlit as st

st.set_page_config(
    page_title="KF-WaterWise",
    page_icon="🌱",
    layout="centered",
)

from components.header import render_header
from components.footer import render_footer
from components.i18n import t

import requests
import math
from datetime import datetime, date

# --- Header ---
render_header()

# --- Predefined cities ---
CITIES = {
    "tokyo": {"name_ja": "東京", "name_en": "Tokyo", "lat": 35.6762, "lon": 139.6503},
    "osaka": {"name_ja": "大阪", "name_en": "Osaka", "lat": 34.6937, "lon": 135.5023},
    "nagoya": {"name_ja": "名古屋", "name_en": "Nagoya", "lat": 35.1815, "lon": 136.9066},
    "sapporo": {"name_ja": "札幌", "name_en": "Sapporo", "lat": 43.0618, "lon": 141.3545},
    "fukuoka": {"name_ja": "福岡", "name_en": "Fukuoka", "lat": 33.5904, "lon": 130.4017},
    "sendai": {"name_ja": "仙台", "name_en": "Sendai", "lat": 38.2682, "lon": 140.8694},
    "hiroshima": {"name_ja": "広島", "name_en": "Hiroshima", "lat": 34.3853, "lon": 132.4553},
    "naha": {"name_ja": "那覇", "name_en": "Naha", "lat": 26.2124, "lon": 127.6809},
}

# Crop coefficients (Kc) for different growth stages (simplified mid-season values)
CROP_TYPES = {
    "rice": {"kc": 1.20, "emoji": "🌾"},
    "vegetables": {"kc": 1.05, "emoji": "🥬"},
    "fruit_trees": {"kc": 0.85, "emoji": "🍎"},
    "flowers": {"kc": 1.00, "emoji": "🌸"},
    "lawn": {"kc": 0.80, "emoji": "🌿"},
    "tomato": {"kc": 1.15, "emoji": "🍅"},
    "potato": {"kc": 1.10, "emoji": "🥔"},
    "beans": {"kc": 1.05, "emoji": "🫘"},
    "taro": {"kc": 1.10, "emoji": "🟤"},
    "ginger": {"kc": 0.95, "emoji": "🫚"},
    "cucumber": {"kc": 1.00, "emoji": "🥒"},
    "eggplant": {"kc": 1.05, "emoji": "🍆"},
    "watermelon": {"kc": 1.00, "emoji": "🍉"},
    "melon": {"kc": 0.95, "emoji": "🍈"},
    "strawberry": {"kc": 0.85, "emoji": "🍓"},
    "corn": {"kc": 1.15, "emoji": "🌽"},
    "soybean": {"kc": 1.10, "emoji": "🫛"},
    "lettuce": {"kc": 0.95, "emoji": "🥗"},
    "carrot": {"kc": 1.00, "emoji": "🥕"},
    "green_onion": {"kc": 0.90, "emoji": "🧅"},
}


WATERING_CAN_LITERS = 6.0  # Standard watering can size in liters


def mm_to_watering_cans(mm: float, area_m2: float = 1.0) -> float:
    """Convert mm of water to number of watering can fills.

    1mm of water over 1m² = 1 liter.
    So mm * area_m2 = total liters needed.
    """
    total_liters = mm * area_m2
    return total_liters / WATERING_CAN_LITERS


def get_city_display_name(city_key: str) -> str:
    """Get display name for a city based on current language."""
    from components.i18n import get_lang
    lang = get_lang()
    city = CITIES[city_key]
    return city["name_ja"] if lang == "ja" else city["name_en"]


def fetch_weather_data(lat: float, lon: float) -> dict | None:
    """Fetch weather data from Open-Meteo API."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max,relative_humidity_2m_mean,shortwave_radiation_sum,et0_fao_evapotranspiration",
        "current": "temperature_2m,relative_humidity_2m,windspeed_10m,precipitation",
        "timezone": "auto",
        "forecast_days": 7,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"{t('api_error')}: {e}")
        return None


def calculate_eto_penman_monteith(
    t_min: float, t_max: float, rh_mean: float, wind_speed: float,
    radiation_mj: float, lat_rad: float, day_of_year: int, altitude: float = 0
) -> float:
    """Calculate reference evapotranspiration using FAO Penman-Monteith (simplified).

    Uses pyeto-compatible formulas. Returns ETo in mm/day.
    """
    # Mean temperature
    t_mean = (t_min + t_max) / 2.0

    # Saturation vapor pressure
    e_t_min = 0.6108 * math.exp(17.27 * t_min / (t_min + 237.3))
    e_t_max = 0.6108 * math.exp(17.27 * t_max / (t_max + 237.3))
    e_s = (e_t_min + e_t_max) / 2.0

    # Actual vapor pressure from relative humidity
    e_a = e_s * rh_mean / 100.0

    # Slope of saturation vapor pressure curve
    delta = 4098 * (0.6108 * math.exp(17.27 * t_mean / (t_mean + 237.3))) / ((t_mean + 237.3) ** 2)

    # Atmospheric pressure
    P = 101.3 * ((293 - 0.0065 * altitude) / 293) ** 5.26
    # Psychrometric constant
    gamma = 0.000665 * P

    # Net radiation (simplified from solar radiation)
    # Use provided shortwave radiation directly (MJ/m2/day)
    Rns = (1 - 0.23) * radiation_mj  # Net shortwave

    # Net longwave radiation (simplified)
    sigma = 4.903e-9  # Stefan-Boltzmann constant (MJ/m2/day/K4)
    Rnl = sigma * ((t_max + 273.16) ** 4 + (t_min + 273.16) ** 4) / 2 * (0.34 - 0.14 * math.sqrt(max(e_a, 0.01)))

    # Estimate clear-sky radiation for cloud factor
    dr = 1 + 0.033 * math.cos(2 * math.pi / 365 * day_of_year)
    solar_dec = 0.409 * math.sin(2 * math.pi / 365 * day_of_year - 1.39)
    ws = math.acos(max(-1, min(1, -math.tan(lat_rad) * math.tan(solar_dec))))
    Ra = (24 * 60 / math.pi) * 0.0820 * dr * (ws * math.sin(lat_rad) * math.sin(solar_dec) + math.cos(lat_rad) * math.cos(solar_dec) * math.sin(ws))
    Rso = (0.75 + 2e-5 * altitude) * Ra

    if Rso > 0:
        cloud_factor = min(radiation_mj / Rso, 1.0)
    else:
        cloud_factor = 0.5

    Rnl = Rnl * (1.35 * cloud_factor - 0.35)
    Rn = Rns - Rnl

    # Soil heat flux (negligible for daily)
    G = 0

    # FAO Penman-Monteith equation
    numerator = 0.408 * delta * (Rn - G) + gamma * (900 / (t_mean + 273)) * wind_speed * (e_s - e_a)
    denominator = delta + gamma * (1 + 0.34 * wind_speed)

    eto = numerator / denominator if denominator != 0 else 0
    return max(eto, 0)


def calculate_daylight_hours(lat: float, lon: float, target_date: date) -> float:
    """Calculate daylight hours using astronomical formulas."""
    try:
        from astral import LocationInfo
        from astral.sun import sun
        location = LocationInfo("", "", "UTC", lat, lon)
        s = sun(location.observer, date=target_date)
        daylight = (s["sunset"] - s["sunrise"]).total_seconds() / 3600
        return round(daylight, 1)
    except Exception:
        # Fallback simple calculation
        day_of_year = target_date.timetuple().tm_yday
        lat_rad = math.radians(lat)
        solar_dec = 0.409 * math.sin(2 * math.pi / 365 * day_of_year - 1.39)
        ws = math.acos(max(-1, min(1, -math.tan(lat_rad) * math.tan(solar_dec))))
        daylight = 24 / math.pi * ws
        return round(daylight, 1)


def get_watering_recommendation(eto: float, kc: float, precipitation: float, rain_forecast: float) -> dict:
    """Determine watering recommendation based on ETo, crop coefficient, and precipitation."""
    crop_water_need = eto * kc  # mm/day
    effective_rain = precipitation * 0.8  # 80% of rain is effective
    net_need = crop_water_need - effective_rain

    # Factor in upcoming rain
    if rain_forecast > 5:
        net_need *= 0.5  # Reduce if rain expected

    if net_need <= 0.5:
        return {
            "verdict": "no_water",
            "color": "#4CAF50",
            "icon": "✅",
            "amount_mm": 0,
        }
    elif net_need <= 2.0:
        return {
            "verdict": "light_water",
            "color": "#FF9800",
            "icon": "💧",
            "amount_mm": round(net_need, 1),
        }
    else:
        return {
            "verdict": "water_needed",
            "color": "#F44336",
            "icon": "🚿",
            "amount_mm": round(net_need, 1),
        }


def format_watering_can_info(amount_mm: float) -> str:
    """Format watering can equivalent display."""
    if amount_mm <= 0:
        return ""
    cans = mm_to_watering_cans(amount_mm)
    return f"🪣 {t('watering_can_unit')}: {cans:.1f}{t('watering_can_suffix')}"


# --- Main Content ---
st.markdown(f"### {t('setup_title')}")

# Location input
location_mode = st.radio(
    t("location_mode"),
    [t("mode_city"), t("mode_coordinates"), t("mode_gps")],
    horizontal=True,
)

lat, lon = None, None

if location_mode == t("mode_city"):
    city_key = st.selectbox(
        t("select_city"),
        options=list(CITIES.keys()),
        format_func=get_city_display_name,
    )
    lat = CITIES[city_key]["lat"]
    lon = CITIES[city_key]["lon"]
elif location_mode == t("mode_gps"):
    # GPS auto-location using streamlit-js-eval for browser geolocation
    st.info(t("gps_info"))
    try:
        from streamlit_js_eval import get_geolocation
        location_data = get_geolocation()
        if location_data and "coords" in location_data:
            lat = location_data["coords"]["latitude"]
            lon = location_data["coords"]["longitude"]
            st.success(f"{t('gps_success')}: {lat:.4f}, {lon:.4f}")
        else:
            st.warning(t("gps_fallback"))
            col1, col2 = st.columns(2)
            with col1:
                lat = st.number_input(t("latitude"), min_value=-90.0, max_value=90.0, value=35.6762, step=0.01, key="gps_lat")
            with col2:
                lon = st.number_input(t("longitude"), min_value=-180.0, max_value=180.0, value=139.6503, step=0.01, key="gps_lon")
    except ImportError:
        st.warning(t("gps_not_available"))
        col1, col2 = st.columns(2)
        with col1:
            lat = st.number_input(t("latitude"), min_value=-90.0, max_value=90.0, value=35.6762, step=0.01, key="gps_lat2")
        with col2:
            lon = st.number_input(t("longitude"), min_value=-180.0, max_value=180.0, value=139.6503, step=0.01, key="gps_lon2")
else:
    col1, col2 = st.columns(2)
    with col1:
        lat = st.number_input(t("latitude"), min_value=-90.0, max_value=90.0, value=35.6762, step=0.01)
    with col2:
        lon = st.number_input(t("longitude"), min_value=-180.0, max_value=180.0, value=139.6503, step=0.01)

# Crop selection
crop_key = st.selectbox(
    t("select_crop"),
    options=list(CROP_TYPES.keys()),
    format_func=lambda k: f"{CROP_TYPES[k]['emoji']} {t(f'crop_{k}')}",
)

st.markdown("---")

# Fetch and analyze
if st.button(t("analyze_btn"), type="primary", use_container_width=True):
    with st.spinner(t("fetching_weather")):
        weather = fetch_weather_data(lat, lon)

    if weather:
        daily = weather["daily"]
        current = weather.get("current", {})
        crop = CROP_TYPES[crop_key]

        # --- Today's Analysis ---
        st.markdown(f"### {t('today_analysis')}")

        today_idx = 0
        t_max = daily["temperature_2m_max"][today_idx] or 0
        t_min = daily["temperature_2m_min"][today_idx] or 0
        precip = daily["precipitation_sum"][today_idx] or 0
        wind = daily["windspeed_10m_max"][today_idx] or 0
        rh = daily["relative_humidity_2m_mean"][today_idx] or 0
        radiation = daily["shortwave_radiation_sum"][today_idx] or 0
        eto_api = daily["et0_fao_evapotranspiration"][today_idx] or 0

        # Use Open-Meteo's ETo (which is FAO Penman-Monteith)
        eto = eto_api

        # Also calculate our own for comparison/fallback
        today_date = date.today()
        day_of_year = today_date.timetuple().tm_yday
        lat_rad = math.radians(lat)
        eto_calc = calculate_eto_penman_monteith(
            t_min, t_max, rh, wind / 3.6, radiation, lat_rad, day_of_year
        )

        # Daylight hours
        daylight = calculate_daylight_hours(lat, lon, today_date)

        # Tomorrow's rain for forecast factor
        rain_tomorrow = (daily["precipitation_sum"][1] or 0) if len(daily["precipitation_sum"]) > 1 else 0

        # Watering recommendation
        recommendation = get_watering_recommendation(eto, crop["kc"], precip, rain_tomorrow)

        # Display verdict
        verdict_text = t(recommendation["verdict"])
        watering_can_text = format_watering_can_info(recommendation["amount_mm"])
        st.markdown(
            f"""
            <div style="background:{recommendation['color']}22; border-left:4px solid {recommendation['color']};
                        padding:20px; border-radius:8px; margin:16px 0;">
                <span style="font-size:2rem;">{recommendation['icon']}</span>
                <span style="font-size:1.4rem; font-weight:bold; color:{recommendation['color']}; margin-left:12px;">
                    {verdict_text}
                </span>
                {f'<br><span style="color:#666; margin-left:52px;">{t("recommended_amount")}: {recommendation["amount_mm"]} mm</span>' if recommendation["amount_mm"] > 0 else ''}
                {f'<br><span style="color:#666; margin-left:52px;">{watering_can_text}</span>' if watering_can_text else ''}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(t("metric_eto"), f"{eto:.1f} mm")
        with col2:
            st.metric(t("metric_precip"), f"{precip:.1f} mm")
        with col3:
            st.metric(t("metric_daylight"), f"{daylight} h")
        with col4:
            crop_need = eto * crop["kc"]
            st.metric(t("metric_crop_need"), f"{crop_need:.1f} mm")

        # Current conditions
        with st.expander(t("current_conditions")):
            cc1, cc2, cc3 = st.columns(3)
            with cc1:
                st.metric(t("metric_temp"), f"{current.get('temperature_2m', t_max)}°C")
            with cc2:
                st.metric(t("metric_humidity"), f"{current.get('relative_humidity_2m', rh)}%")
            with cc3:
                st.metric(t("metric_wind"), f"{current.get('windspeed_10m', wind)} km/h")

            st.caption(f"ETo (Open-Meteo FAO PM): {eto:.2f} mm/day | Kc ({t(f'crop_{crop_key}')}): {crop['kc']}")

        # --- Weekly Forecast ---
        st.markdown("---")
        st.markdown(f"### {t('weekly_forecast')}")

        # Create forecast table
        forecast_cols = st.columns(7)
        dates = daily.get("time", [])

        for i, col in enumerate(forecast_cols):
            if i >= len(dates):
                break
            with col:
                d = datetime.strptime(dates[i], "%Y-%m-%d")
                day_label = d.strftime("%m/%d")
                weekday = d.strftime("%a")

                eto_day = daily["et0_fao_evapotranspiration"][i] or 0
                precip_day = daily["precipitation_sum"][i] or 0
                temp_max = daily["temperature_2m_max"][i] or 0
                temp_min = daily["temperature_2m_min"][i] or 0

                # Determine day's watering need
                rain_next = (daily["precipitation_sum"][i + 1] or 0) if i + 1 < len(dates) else 0
                rec = get_watering_recommendation(eto_day, crop["kc"], precip_day, rain_next)

                st.markdown(f"**{day_label}**")
                st.caption(weekday)
                st.markdown(f"{rec['icon']}")
                st.caption(f"{temp_min:.0f}-{temp_max:.0f}°C")
                st.caption(f"☔ {precip_day:.1f}mm")
                if rec["amount_mm"] > 0:
                    cans = mm_to_watering_cans(rec["amount_mm"])
                    st.caption(f"🪣 {cans:.1f}{t('watering_can_suffix')}")
                st.caption(f"ETo {eto_day:.1f}")

        # Legend
        st.markdown("---")
        st.caption(
            f"✅ {t('no_water')} | 💧 {t('light_water')} | 🚿 {t('water_needed')}"
        )
        st.caption(
            f"🪣 = {t('watering_can_unit')} ({WATERING_CAN_LITERS:.0f}L) / 1㎡"
        )

# --- Footer ---
render_footer(libraries=[
    "FAO Penman-Monteith — ETo calculation (implemented inline)",
    "astral — sunrise/sunset and daylight hours",
    "requests — Open-Meteo weather API (free, no key required)",
    "streamlit-js-eval — browser geolocation (GPS)",
])
