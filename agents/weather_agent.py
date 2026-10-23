# -*- coding: utf-8 -*-
"""
agents/weather_agent.py — Agente de Monitoreo y Clima Hiperlocal de Saladillo
=============================================================================
Consulta periódicamente la API meteorológica de Open-Meteo para las coordenadas exactas
de Saladillo, BA (-34.636, -59.778). Procesa:
- Temperatura actual y sensación térmica.
- Mapeo de códigos WMO (Despejado, Parcialmente Nublado, Lluvia, Tormenta, etc.).
- Pronóstico extendido para los widgets de UI y WeatherOverlay del reproductor de TV.
- Caché local con persistencia en data/weather_cache.json.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger("WeatherAgent")
logger.setLevel(logging.INFO)

SALADILLO_COORDS = {"lat": -34.636, "lon": -59.778}


class WeatherAgent:
    """
    Agente de servicio meteorológico para Saladillo Vivo.
    """
    def __init__(self, cache_file: str = "data/weather_cache.json"):
        self.cache_file = cache_file
        self.location_name = "Saladillo, Buenos Aires"
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)

    def map_wmo_code(self, code: int) -> Dict[str, Any]:
        """Traduce códigos meteorológicos WMO estándar a texto en español e íconos."""
        mapping = {
            0: {"text": "Cielo despejado", "code": 1000},
            1: {"text": "Mayormente despejado", "code": 1003},
            2: {"text": "Parcialmente nublado", "code": 1003},
            3: {"text": "Nublado", "code": 1006},
            45: {"text": "Niebla", "code": 1030},
            48: {"text": "Niebla con escarcha", "code": 1030},
            51: {"text": "Llovizna leve", "code": 1150},
            53: {"text": "Llovizna moderada", "code": 1153},
            55: {"text": "Llovizna densa", "code": 1153},
            61: {"text": "Lluvia ligera", "code": 1183},
            63: {"text": "Lluvia moderada", "code": 1186},
            65: {"text": "Lluvia fuerte", "code": 1189},
            80: {"text": "Chaparrones leves", "code": 1240},
            81: {"text": "Chaparrones moderados", "code": 1240},
            82: {"text": "Chaparrones intensos", "code": 1240},
            95: {"text": "Tormenta eléctrica", "code": 1087},
            96: {"text": "Tormenta con granizo leve", "code": 1087},
            99: {"text": "Tormenta con granizo severo", "code": 1087}
        }
        return mapping.get(code, {"text": "Nubosidad variable", "code": 1003})

    def fetch_current_weather(self) -> Optional[Dict[str, Any]]:
        """Obtiene las condiciones actuales y el pronóstico desde Open-Meteo."""
        if not requests:
            logger.error("Módulo requests no disponible.")
            return None

        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": SALADILLO_COORDS["lat"],
            "longitude": SALADILLO_COORDS["lon"],
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max,uv_index_max",
            "timezone": "America/Argentina/Buenos_Aires",
            "forecast_days": 3
        }

        try:
            resp = requests.get(url, params=params, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                cur = data.get("current", {})
                wmo_info = self.map_wmo_code(cur.get("weather_code", 0))

                weather_payload = {
                    "location": self.location_name,
                    "updated_at": datetime.now().isoformat(),
                    "current": {
                        "temp": round(cur.get("temperature_2m", 0), 1),
                        "feels_like": round(cur.get("apparent_temperature", 0), 1),
                        "humidity": cur.get("relative_humidity_2m", 0),
                        "wind_speed_kmh": round(cur.get("wind_speed_10m", 0), 1),
                        "is_day": bool(cur.get("is_day", 1)),
                        "condition_text": wmo_info["text"],
                        "condition_code": wmo_info["code"],
                    },
                    "daily": data.get("daily", {})
                }

                # Guardar caché
                with open(self.cache_file, "w", encoding="utf-8") as f:
                    json.dump(weather_payload, f, ensure_ascii=False, indent=2)

                logger.info(f"WeatherAgent: Clima actualizado -> {weather_payload['current']['temp']}°C ({wmo_info['text']})")
                return weather_payload
            else:
                logger.error(f"Error consultando Open-Meteo ({resp.status_code}): {resp.text}")
                return None
        except Exception as e:
            logger.error(f"Excepción en WeatherAgent: {e}")
            return None

    def get_cached_weather(self) -> Optional[Dict[str, Any]]:
        """Retorna la última lectura guardada en caché."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return self.fetch_current_weather()
