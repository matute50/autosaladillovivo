# -*- coding: utf-8 -*-
"""
agents/tv_programming_agent.py — Agente de Programación y Rotación TV-Grade
==========================================================================
Gestiona la parrilla de contenidos temáticos de Saladillo Vivo:
- Smart Slots (v18): Programación horaria de contenidos temáticos.
- Selección y rotación de intros cinemáticas institucionales.
- Cola de reproducción sin cortes negros (Zero-Black Transition v20).
- Curaduría de videos exclusivos, música, noticias y clips locales.
"""

import os
import json
import random
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger("TvProgrammingAgent")
logger.setLevel(logging.INFO)


class TvProgrammingAgent:
    """
    Agente director de programación televisiva para el reproductor de Saladillo Vivo.
    """
    def __init__(self, data_path: str = "data/tv_schedule.json"):
        self.data_path = data_path
        self.default_intros = [
            "/videos_intro/intro_institucional_1.mp4",
            "/videos_intro/intro_institucional_2.mp4",
            "/videos_intro/intro_noticias.mp4"
        ]
        self.categories = [
            "Noticias",
            "Música",
            "Deportes",
            "Interés General",
            "Cultura Saladillense",
            "Documentales",
            "Clásicos"
        ]

    def get_smart_slot_category(self, current_hour: Optional[int] = None) -> str:
        """
        Calcula la categoría temática correspondiente según la hora del día (Smart Slots v18):
        - Mañana (07:00 a 12:00): Noticias y actualidad matutina
        - Almuerzo (12:00 a 14:00): Resumen Informativo e Interés General
        - Tarde (14:00 a 18:00): Música, Cultura y Documentales
        - Atardecer (18:00 a 21:00): Deportes y Central Informativo
        - Noche (21:00 a 01:00): Espectáculos, Música y Clásicos
        - Madrugada (01:00 a 07:00): Música Chillout y Paisajes de Saladillo
        """
        import datetime
        h = current_hour if current_hour is not None else datetime.datetime.now().hour

        if 7 <= h < 12:
            return "Noticias"
        elif 12 <= h < 14:
            return "Interés General"
        elif 14 <= h < 18:
            return "Cultura Saladillense"
        elif 18 <= h < 21:
            return "Deportes"
        elif 21 <= h < 24 or h == 0:
            return "Música"
        else:
            return "Documentales"

    def select_intro_video(self, category: Optional[str] = None) -> str:
        """Selecciona la intro cinemática más apropiada según el bloque o aleatoriamente."""
        if category == "Noticias":
            return "/videos_intro/intro_noticias.mp4"
        return random.choice(self.default_intros)

    def plan_next_video(self, current_playlist: List[Dict[str, Any]], last_played_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Aplica el algoritmo de anti-repetición y selección aleatoria ponderada para evitar fatiga auditiva/visual.
        """
        if not current_playlist:
            return None

        candidates = [v for v in current_playlist if str(v.get('id')) != str(last_played_id)]
        if not candidates:
            candidates = current_playlist

        selected = random.choice(candidates)
        logger.info(f"TvProgrammingAgent: Siguiente video seleccionado -> {selected.get('nombre') or selected.get('title')}")
        return selected

    def generate_tv_lineup_summary(self) -> Dict[str, Any]:
        """Genera un reporte del estado de programación para el dashboard de control."""
        import datetime
        now = datetime.datetime.now()
        current_cat = self.get_smart_slot_category(now.hour)

        return {
            'timestamp': now.isoformat(),
            'current_hour': now.hour,
            'active_slot': current_cat,
            'intro_video': self.select_intro_video(current_cat),
            'available_categories': self.categories
        }
