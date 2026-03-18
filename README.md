---
title: kf-water-wise
emoji: 🚀
colorFrom: green
colorTo: blue
sdk: streamlit
sdk_version: 1.44.1
app_file: app.py
pinned: false
---

# KF-WaterWise

> 天気データとETo計算で水やりを科学的に判定するアプリ。

## The Problem

Agricultural watering based on intuition leads to over- or under-watering, directly impacting crop yields and water waste. This app provides science-based watering decisions.

## How It Works

1. Select a location (city or coordinates) and crop type
2. App fetches weather data from Open-Meteo API (free, no key required)
3. Calculates reference evapotranspiration (ETo) using FAO Penman-Monteith
4. Uses astral to calculate daylight hours
5. Displays today's watering recommendation and weekly forecast

## Libraries Used

- **pyeto** — Reference evapotranspiration (ETo) calculation using FAO Penman-Monteith
- **astral** — Sunrise/sunset and daylight hours calculation
- **requests** — HTTP client for Open-Meteo API (free, no API key required)

## Development

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deployment

Hosted on [Hugging Face Spaces](https://huggingface.co/spaces/mitoi/kf-water-wise).

---

Part of the [KaleidoFuture AI-Driven Development Research](https://kaleidofuture.com) — proving that everyday problems can be solved with existing libraries, no AI model required.
