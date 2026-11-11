# -*- coding: utf-8 -*-
"""
agents/constants.py — Constantes compartidas entre agentes
===========================================================
Centraliza valores comunes para evitar desincronización entre audio y slide.
"""

# Frases institucionales de cierre elegidas al azar (usadas por AudioGeneratorAgent y SlideGeneratorAgent)
INSTITUTIONAL_CLOSING_PHRASES = [
    "En Saladillo Vivo. Dale play a la noticia.",
    "No lo leas, escuchálo, en Saladillo Vivo.",
    "Saladillo Vivo le pone voz a las noticias.",
    "Escuchá más, en Saladillo Vivo.",
    "Seguí escuchando, en Saladillo Vivo.",
    "La ciudad se escucha, en Saladillo Vivo.",
    "Enteráte escuchando, en Saladillo Vivo.",
    "Más info, en voz alta, en Saladillo Vivo.",
    "Saladillo Vivo. Menos textos, más audios.",
    "Cerrá los ojos, y escuchá Saladillo Vivo.",
    "Pasáte al audio, en Saladillo Vivo.",
    "Saladillo Vivo. Escuchar es la nueva forma de informarte.",
    "Poné play a tu día, en Saladillo Vivo.",
    "Dejános contarte la noticia, solo en Saladillo Vivo.",
    "Escuchálo ahora, en Saladillo Vivo.",
    "Todo suena mejor, en Saladillo Vivo.",
    "Viví la noticia, en Saladillo Vivo.",
    "Sentí Saladillo, en Saladillo Vivo.",
    "Saladillo Vivo. La voz de la ciudad.",
    "Informáte al instante, en Saladillo Vivo.",
    "Saladillo Vivo. Un paso adelante.",
    "Saladillo Vivo. La evolución de la noticia.",
    "Escuchá el futuro, en Saladillo Vivo.",
    "Saladillo Vivo. Innovación en noticias.",
    "Siempre un paso adelante, en Saladillo Vivo.",
    "Los demás leen, nosotros te lo contamos. Solo en Saladillo Vivo.",
    "Adelantáte a todos escuchando en Saladillo Vivo.",
    "La nueva era de la info, en Saladillo Vivo.",
    "Innovamos para que solo escuches. Solo en Saladillo Vivo.",
    "Saladillo Vivo. Un paso más allá de la lectura.",
    "Saladillo Vivo. Un paso más allá que leer las noticias.",
]

# Voces de respaldo Edge TTS (alternancia obligatoria por noticia)
BACKUP_VOICES = ["es-AR-TomasNeural", "es-AR-ElenaNeural"]