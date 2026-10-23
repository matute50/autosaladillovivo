# -*- coding: utf-8 -*-
"""
agents/master_orchestrator_agent.py — Agente Orquestador Maestro de Saladillo Vivo
================================================================================
Coordina y supervisa a TODOS los agentes especializados de la plataforma:
1. Ciclo Periodístico y Noticias (Scraper, Storage, AiRewriter, AudioGenerator, SlideGenerator, Publisher, Orchestrator)
2. Televisión y Streaming (StreamMonitor, TvProgramming)
3. Servicios e Interfaz (Weather, BannerAds, FeedSeo)

Ofrece:
- Diagnóstico 360° de todo el ecosistema (Health Check Integral).
- Ejecución periódica coordinada según franjas horarias y prioridades.
- Panel de estado consolidador y catálogo de capacidades.
"""

import os
import sys
import json
import time
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

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

logger = logging.getLogger("MasterOrchestratorAgent")
logger.setLevel(logging.INFO)


class MasterOrchestratorAgent:
    """
    Agente Director y Orquestador Supremo de la arquitectura multi-agente de Saladillo Vivo.
    """
    def __init__(self):
        # 1. Agentes del Subsistema Periodístico
        self.storage_agent = StorageAgent()
        self.scraper_agent = ScraperAgent()
        self.rewriter_agent = AiRewriterAgent()
        self.audio_agent = AudioGeneratorAgent()
        self.slide_agent = SlideGeneratorAgent()
        self.publisher_agent = PublisherAgent(self.storage_agent)
        self.news_orchestrator = OrchestratorAgent()

        # 2. Agentes del Subsistema de Streaming y Televisión
        self.stream_monitor_agent = StreamMonitorAgent()
        self.tv_programming_agent = TvProgrammingAgent()

        # 3. Agentes de Servicios de Contenido e Interfaz
        self.weather_agent = WeatherAgent()
        self.banner_ads_agent = BannerAdsAgent()
        self.feed_seo_agent = FeedSeoAgent()

        self.last_diagnostic: Optional[Dict[str, Any]] = None

    def get_agents_catalog(self) -> List[Dict[str, Any]]:
        """
        Retorna el catálogo completo y estructurado de todos los agentes de Saladillo Vivo.
        """
        return [
            {
                "name": "ScraperAgent",
                "file": "agents/scraper_agent.py",
                "area": "Ciclo Periodístico",
                "role": "Extractor de noticias crudas",
                "description": "Scrapea y extrae noticias en tiempo real desde portales locales (Convergencias, La Síntesis, CN Saladillo, InfoSaladillo), con deduplicación por hash."
            },
            {
                "name": "StorageAgent",
                "file": "agents/storage_agent.py",
                "area": "Persistencia & Datos",
                "role": "Custodio de Base de Datos y Storage",
                "description": "Gestiona la persistencia en Supabase (tabla articles), sanitización de slugs, control de schema-cache y actualización de estados del pipeline."
            },
            {
                "name": "AiRewriterAgent",
                "file": "agents/ai_rewriter_agent.py",
                "area": "Inteligencia Artificial",
                "role": "Editor Periodístico IA Free-First",
                "description": "Reestructura títulos y textos periodísticos, optimiza redacción, genera metadatos SEO y clasifica la jerarquía temática (principal, secundaria, flash)."
            },
            {
                "name": "AudioGeneratorAgent",
                "file": "agents/audio_generator_agent.py",
                "area": "Producción Sonora",
                "role": "Locutor y Productor de Audio",
                "description": "Convierte textos en audio locutado con acento rioplatense (gTTS tld='com.ar'), normaliza decibelios (Pydub/FFmpeg) y aloja MP3 en Supabase Storage (bucket audios)."
            },
            {
                "name": "SlideGeneratorAgent",
                "file": "agents/slide_generator_agent.py",
                "area": "Formatos Interactivos",
                "role": "Generador de Slides TV-Grade",
                "description": "Crea documentos dinámicos .html para cada noticia con fotografías optimizadas (Pillow), diseño cinematográfico y locución rioplatense interactiva en bucket slides."
            },
            {
                "name": "PublisherAgent",
                "file": "agents/publisher_agent.py",
                "area": "Distribución Editorial",
                "role": "Editor de Publicación",
                "description": "Publica oficialmente las noticias en vivo en el portal web (is_published=True), establece timestamps y coordina la visibilidad inmediata."
            },
            {
                "name": "StreamMonitorAgent",
                "file": "agents/stream_monitor_agent.py",
                "area": "Streaming en Vivo",
                "role": "Centinela de Transmisión",
                "description": "Supervisa el estado del streaming (YouTube Live / HLS .m3u8), ejecuta deep-check de señal en vivo y dispara conmutación automática ante caídas."
            },
            {
                "name": "TvProgrammingAgent",
                "file": "agents/tv_programming_agent.py",
                "area": "Programación Televisiva",
                "role": "Director de Programación TV",
                "description": "Administra los Smart Slots temáticos por franja horaria (v18), selecciona intros cinemáticas institucionales y organiza transiciones sin pausas negras (Zero-Black v20)."
            },
            {
                "name": "WeatherAgent",
                "file": "agents/weather_agent.py",
                "area": "Servicios Hiperlocales",
                "role": "Meteorólogo Digital",
                "description": "Consulta y procesa el clima en tiempo real de Saladillo (-34.636, -59.778) vía Open-Meteo, calculando sensación térmica y códigos WMO para widgets y overlays de TV."
            },
            {
                "name": "BannerAdsAgent",
                "file": "agents/banner_ads_agent.py",
                "area": "Monetización & Comercial",
                "role": "Gestor de Publicidad Local",
                "description": "Administra campañas de anunciantes locales, vigencia de banners (BannerCarousel y AdsSection), balanceo de impresiones y rotación comercial."
            },
            {
                "name": "FeedSeoAgent",
                "file": "agents/feed_seo_agent.py",
                "area": "SEO & Sindicación",
                "role": "Auditor de Distribución",
                "description": "Monitorea y valida el feed RSS 2.0 XML, los sitemaps de búsqueda, el generador de OpenGraph dinámico (/api/og) y los endpoints de miniaturas."
            },
            {
                "name": "OrchestratorAgent",
                "file": "agents/orchestrator_agent.py",
                "area": "Orquestación Específica",
                "role": "Orquestador del Ciclo Periodístico",
                "description": "Coordina el ciclo integral de noticias de 7 pasos (Scraping -> Borrador -> IA -> Audio -> Slides -> BD -> Publicación)."
            },
            {
                "name": "MasterOrchestratorAgent",
                "file": "agents/master_orchestrator_agent.py",
                "area": "Gobernanza Suprema",
                "role": "Orquestador Maestro Integral",
                "description": "Supervisa y sincroniza a todos los agentes de noticias, televisión, clima, publicidad y SEO, ejecutando auditorías 360° y schedulers coordinados."
            }
        ]

    def run_full_system_diagnostic(self) -> Dict[str, Any]:
        """
        Ejecuta un diagnóstico integral 360° consultando el estado de todos los subsistemas.
        """
        logger.info("🔎 Iniciando Diagnóstico Maestro 360° de Saladillo Vivo...")
        start_time = datetime.now()

        # 1. Base de datos
        db_ok = self.storage_agent.verify_connection()

        # 2. Clima
        weather_data = self.weather_agent.get_cached_weather()

        # 3. Streaming
        stream_status = self.stream_monitor_agent.check_stream()

        # 4. Programación TV
        tv_lineup = self.tv_programming_agent.generate_tv_lineup_summary()

        # 5. Publicidad
        ads_audit = self.banner_ads_agent.audit_campaigns()

        # 6. SEO / RSS
        rss_status = self.feed_seo_agent.audit_rss_feed()

        duration = (datetime.now() - start_time).total_seconds()

        diagnostic = {
            "status": "operational" if db_ok else "degraded",
            "timestamp": datetime.now().isoformat(),
            "diagnostic_duration_seconds": round(duration, 2),
            "subsystems": {
                "database_supabase": {"connected": db_ok},
                "weather_saladillo": {
                    "temperature": weather_data.get("current", {}).get("temp") if weather_data else None,
                    "condition": weather_data.get("current", {}).get("condition_text") if weather_data else None
                },
                "live_streaming": {
                    "is_live": stream_status.get("is_live", False),
                    "type": stream_status.get("type", "unknown")
                },
                "tv_programming": {
                    "active_slot": tv_lineup.get("active_slot"),
                    "intro": tv_lineup.get("intro_video")
                },
                "advertising": ads_audit,
                "rss_distribution": {
                    "status": rss_status.get("status"),
                    "items": rss_status.get("items_count", 0)
                }
            }
        }

        self.last_diagnostic = diagnostic
        logger.info(f"✅ Diagnóstico Maestro completado en {duration:.2f}s. Estado: {diagnostic['status'].upper()}")
        return diagnostic

    def run_news_cycle(self, limit: int = 10) -> bool:
        """Dispara un ciclo completo del subsistema periodístico."""
        self.news_orchestrator.limit_per_source = limit
        return self.news_orchestrator.run_full_pipeline()
