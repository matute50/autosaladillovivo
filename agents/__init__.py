# -*- coding: utf-8 -*-
"""
Package: agents
Módulos especializados para la automatización periodística de Saladillo Vivo.

Agentes:
- ScraperAgent: Extracción y scraping de noticias locales.
- StorageAgent: Persistencia, control de esquema y deduplicación en Supabase.
- AiRewriterAgent: Reescritura, enriquecimiento y priorización con IA Free-First.
- AudioGeneratorAgent: Generación, normalización y almacenamiento de locución en audio.
- PublisherAgent: Publicación oficial, visibilidad web y distribución a redes.
- OrchestratorAgent: Coordinación end-to-end del ciclo de 6 pasos y temporización.
"""

from .scraper_agent import ScraperAgent
from .storage_agent import StorageAgent
from .ai_rewriter_agent import AiRewriterAgent
from .audio_generator_agent import AudioGeneratorAgent
from .publisher_agent import PublisherAgent
from .orchestrator_agent import OrchestratorAgent

__all__ = [
    'ScraperAgent',
    'StorageAgent',
    'AiRewriterAgent',
    'AudioGeneratorAgent',
    'PublisherAgent',
    'OrchestratorAgent'
]
