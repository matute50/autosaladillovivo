# -*- coding: utf-8 -*-
"""
agents/location_manager.py — Gestor de Locaciones y Fondos de Escenario
======================================================================
Administra la asignación de imágenes de fondo locales para las noticias de Ara
según la categoría temática, implementando fallback hacia 'general/'.
"""

import os
import glob
import random
import logging
from typing import Optional, List

logger = logging.getLogger("LocationManager")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCACIONES_DIR = os.path.join(BASE_DIR, 'assets', 'locaciones')

EXTENSIONES_VALIDAS = ('.jpg', '.jpeg', '.png', '.webp')


class LocationManager:
    """
    Gestor de imágenes de locaciones clasificadas para Google Flow.
    """

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or LOCACIONES_DIR
        os.makedirs(self.base_dir, exist_ok=True)

    def list_categories(self) -> List[str]:
        """Devuelve la lista de categorías existentes en la carpeta de locaciones."""
        if not os.path.exists(self.base_dir):
            return []
        return [
            d for d in os.listdir(self.base_dir)
            if os.path.isdir(os.path.join(self.base_dir, d))
        ]

    def get_images_for_category(self, category: str) -> List[str]:
        """Obtiene todas las rutas de imágenes disponibles para una categoría dada."""
        cat_dir = os.path.join(self.base_dir, category)
        if not os.path.exists(cat_dir):
            return []
        
        images = []
        for f in os.listdir(cat_dir):
            if f.lower().endswith(EXTENSIONES_VALIDAS):
                images.append(os.path.join(cat_dir, f))
        return sorted(images)

    def resolve_location_image(self, category: str, randomize: bool = False) -> Optional[str]:
        """
        Resuelve la imagen de locación adecuada.
        Si la categoría no tiene imágenes, recurre a 'general/' (fallback).
        """
        category_clean = (category or 'general').strip().lower()
        candidates = self.get_images_for_category(category_clean)

        # Si no hay imágenes en la categoría pedida, buscar en fallback 'general'
        if not candidates and category_clean != 'general':
            logger.info(f"[LocationManager] Sin imágenes en '{category_clean}', recurriendo a fallback 'general'.")
            candidates = self.get_images_for_category('general')

        if not candidates:
            logger.warning("[LocationManager] No se encontraron imágenes ni en la categoría ni en 'general/'.")
            return None

        if randomize:
            return random.choice(candidates)
        return candidates[0]


if __name__ == "__main__":
    lm = LocationManager()
    print("Categorías detectadas:", lm.list_categories())
