# -*- coding: utf-8 -*-
"""
Package: agents — Suite Multi-Agente Integral de Saladillo Vivo
==============================================================
Contiene los agentes especializados organizados por áreas de responsabilidad:

1. Subsistema Periodístico:
   - ScraperAgent: Extracción y scraping de noticias locales.
   - StorageAgent: Persistencia, control de esquema y deduplicación en Supabase.
   - AiRewriterAgent: Reescritura, enriquecimiento y priorización con IA Free-First.
   - AudioGeneratorAgent: Generación, normalización y almacenamiento de locución en audio.
   - SlideGeneratorAgent: Generación de slides dinámicos con fotos y voz rioplatense.
   - PublisherAgent: Publicación oficial, visibilidad web y distribución a redes.
   - OrchestratorAgent: Coordinación del pipeline periodístico de 7 pasos.

2. Subsistema de Streaming y Televisión:
   - StreamMonitorAgent: Monitoreo continuo de streaming en vivo y fallback.
   - TvProgrammingAgent: Programación de Smart Slots, intros y transiciones Zero-Black.

3. Subsistema de Servicios e Interfaz:
   - WeatherAgent: Clima hiperlocal de Saladillo en tiempo real (Open-Meteo).
   - BannerAdsAgent: Gestión publicitaria, contratos locales y rotación de banners.
   - FeedSeoAgent: Auditoría y sindicación RSS 2.0, sitemaps y OpenGraph.

4. Gobernanza Global:
   - MasterOrchestratorAgent: Orquestador supremo que supervisa y coordina a todos los agentes.
"""

from .scraper_agent import ScraperAgent
from .storage_agent import StorageAgent
from .ai_rewriter_agent import AiRewriterAgent
from .audio_generator_agent import AudioGeneratorAgent
from .slide_generator_agent import SlideGeneratorAgent
from .publisher_agent import PublisherAgent
from .orchestrator_agent import OrchestratorAgent
from .stream_monitor_agent import StreamMonitorAgent
from .tv_programming_agent import TvProgrammingAgent
from .weather_agent import WeatherAgent
from .banner_ads_agent import BannerAdsAgent
from .feed_seo_agent import FeedSeoAgent
from .master_orchestrator_agent import MasterOrchestratorAgent

__all__ = [
    'ScraperAgent',
    'StorageAgent',
    'AiRewriterAgent',
    'AudioGeneratorAgent',
    'SlideGeneratorAgent',
    'PublisherAgent',
    'OrchestratorAgent',
    'StreamMonitorAgent',
    'TvProgrammingAgent',
    'WeatherAgent',
    'BannerAdsAgent',
    'FeedSeoAgent',
    'MasterOrchestratorAgent'
]
