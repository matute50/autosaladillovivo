# -*- coding: utf-8 -*-
"""
agents/banner_ads_agent.py — Agente de Gestión Publicitaria y Banners Locales
=============================================================================
Responsable del control, rotación y métricas de pauta publicitaria en Saladillo Vivo:
- Administración de sponsors y comercios locales.
- Validación de vigencia de contratos y fechas de caducidad de campañas.
- Asignación de banners en las secciones: BannerCarousel, AdsSection y zócalo de TV.
- Rotación equitativa ponderada para maximizar el ROI de anunciantes locales.
"""

import os
import json
import logging
from datetime import datetime, date
from typing import Dict, List, Any, Optional

logger = logging.getLogger("BannerAdsAgent")
logger.setLevel(logging.INFO)


class BannerAdsAgent:
    """
    Agente comercial y de banners publicitarios para Saladillo Vivo.
    """
    def __init__(self, data_file: str = "data/banners_campaigns.json"):
        self.data_file = data_file
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        self._ensure_sample_campaigns()

    def _ensure_sample_campaigns(self):
        """Inicializa campañas por defecto si no existen."""
        if not os.path.exists(self.data_file):
            defaults = [
                {
                    "id": "ad-comercio-1",
                    "client_name": "Comercio Saladillense",
                    "image_url": "https://saladillovivo.vercel.app/default-og-image.png",
                    "target_url": "https://saladillovivo.com.ar",
                    "position": "carousel",
                    "is_active": True,
                    "impressions": 0,
                    "expiration_date": "2026-12-31"
                },
                {
                    "id": "ad-institucional-sv",
                    "client_name": "Saladillo Vivo Streaming",
                    "image_url": "https://saladillovivo.vercel.app/default-og-image.png",
                    "target_url": "https://saladillovivo.com.ar",
                    "position": "sidebar",
                    "is_active": True,
                    "impressions": 0,
                    "expiration_date": "2026-12-31"
                }
            ]
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(defaults, f, ensure_ascii=False, indent=2)

    def load_campaigns(self) -> List[Dict[str, Any]]:
        """Carga todas las campañas de publicidad registradas."""
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error cargando campañas: {e}")
            return []

    def save_campaigns(self, campaigns: List[Dict[str, Any]]) -> bool:
        """Persiste las campañas y estadísticas."""
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(campaigns, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error guardando campañas: {e}")
            return False

    def get_active_banners(self, position: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retorna únicamente los banners válidos y no expirados."""
        today_str = date.today().isoformat()
        campaigns = self.load_campaigns()
        valid = []

        for camp in campaigns:
            if not camp.get("is_active", True):
                continue
            exp = camp.get("expiration_date")
            if exp and exp < today_str:
                continue
            if position and camp.get("position") != position:
                continue
            valid.append(camp)

        return valid

    def record_impression(self, banner_id: str):
        """Registra una visualización de un anuncio."""
        campaigns = self.load_campaigns()
        for camp in campaigns:
            if camp.get("id") == banner_id:
                camp["impressions"] = camp.get("impressions", 0) + 1
                break
        self.save_campaigns(campaigns)

    def audit_campaigns(self) -> Dict[str, Any]:
        """Audita el inventario publicitario y alerta sobre campañas por vencer."""
        campaigns = self.load_campaigns()
        active = self.get_active_banners()
        expired = len(campaigns) - len(active)

        return {
            "total_campaigns": len(campaigns),
            "active_campaigns": len(active),
            "expired_campaigns": expired,
            "total_impressions": sum(c.get("impressions", 0) for c in campaigns)
        }
