# -*- coding: utf-8 -*-
"""
agents/orchestrator_agent.py — Agente Maestro de Orquestación Periodística
========================================================================
Coordina de forma autónoma el ciclo completo de 7 pasos requerido para Saladillo Vivo:
  1. Scraping de noticias locales (ScraperAgent)
  2. Guardado en base de datos como borrador/raw (StorageAgent)
  3. Modificación de título y texto con IA (AiRewriterAgent)
  4. Generación y optimización de audio locutado (AudioGeneratorAgent)
  5. Generación de slides interactivos con fotos y voz rioplatense (SlideGeneratorAgent)
  6. Actualización en base de datos con IA, audio_url y url_slide (StorageAgent)
  7. Publicación oficial final en vivo (PublisherAgent)

Características:
- Programación dinámica por franjas horarias (30 min / 1 hora / 3 horas).
- Modo de ejecución inmediata única (--once) y modo continuo (daemon).
- Logging estructurado dual (consola + logs/automation.log).
- Informes de ejecución en data/cycle_summary.json.
"""

import os
import sys
import json
import time
import hashlib
import logging
import threading
from datetime import datetime, timedelta

from .scraper_agent import ScraperAgent, are_articles_duplicate
from .article_ledger import (
    classify_candidates,
    known_source_identities,
    load_article_state,
    retryable_source_identities,
    save_article_state,
)
from .storage_agent import StorageAgent
from .ai_rewriter_agent import AiRewriterAgent
from .audio_generator_agent import AudioGeneratorAgent
from .slide_generator_agent import SlideGeneratorAgent
from .publisher_agent import PublisherAgent
from .qa_agent import QAAuditor, QAConfig

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
LOGS_DIR = os.path.join(BASE_DIR, 'logs')

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

logger = logging.getLogger("SaladilloVivoMultiAgent")
logger.setLevel(logging.INFO)

if not logger.handlers:
    fh = logging.FileHandler(os.path.join(LOGS_DIR, 'automation.log'), encoding='utf-8', mode='a')
    fh.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s'))
    logger.addHandler(fh)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S'))
    logger.addHandler(sh)


class OrchestratorAgent:
    """
    Orquestador multi-agente del ciclo de noticias y streaming de audio.
    """
    def __init__(self, limit_per_source=10, immediate_publish=True, enable_audio=True, enable_slides=True):
        self.limit_per_source = limit_per_source
        self.immediate_publish = immediate_publish
        self.enable_audio = enable_audio
        self.enable_slides = enable_slides
        self.running = False
        self.thread = None
        self.last_execution = None
        self.execution_count = 0
        self._stop_event = threading.Event()

        # Instanciar agentes
        self.scraper_agent = ScraperAgent()
        self.storage_agent = StorageAgent()
        self.rewriter_agent = AiRewriterAgent()
        self.audio_agent = AudioGeneratorAgent()
        self.slide_agent = SlideGeneratorAgent()
        self.publisher_agent = PublisherAgent(self.storage_agent)
        # Agente de auditoría QA
        try:
            self.qa = QAAuditor(QAConfig.from_env())
        except Exception as e:
            logger.warning(f"[QA] Fallo al inicializar: {e}, función de auditoría desactivada")
            self.qa = None

    def get_next_execution_time(self, current_dt=None):
        """
        Calcula la próxima ejecución según la franja horaria:
        - 07:00 a 12:00: cada 30 minutos
        - 12:00 a 22:00: cada 1 hora
        - 22:00 a 07:00: cada 3 horas
        """
        now = current_dt or datetime.now()
        hour = now.hour

        if 7 <= hour < 12:
            target_min = 30 if now.minute < 30 else 0
            if target_min == 0:
                next_time = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            else:
                next_time = now.replace(minute=30, second=0, microsecond=0)
            freq_desc = "30 minutos (07:00 a 12:00)"
        elif 12 <= hour < 22:
            next_time = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            freq_desc = "1 hora (12:00 a 22:00)"
        else:
            next_time = (now + timedelta(hours=3)).replace(minute=0, second=0, microsecond=0)
            freq_desc = "3 horas (22:00 a 07:00)"

        return next_time, freq_desc

    def run_full_pipeline(self):
        """
        Ejecuta el ciclo integral de 6 pasos:
        1. Scraping (ScraperAgent)
        2. Guardar en Base de Datos como Borrador (StorageAgent)
        3. Modificar Título y Texto con IA (AiRewriterAgent)
        4. Generar y optimizar audio locutado (AudioGeneratorAgent)
        5. Guardar en Base de Datos con IA y Audio (StorageAgent)
        6. Publicar Oficialmente en Base de Datos (PublisherAgent)
        """
        start_time = datetime.now()
        logger.info("=================================================================")
        logger.info("🚀 INICIANDO CICLO MULTI-AGENTE DE NOTICIAS Y AUDIO — SALADILLO VIVO")
        logger.info(f"   Hora de inicio: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=================================================================")

        # Verificar conectividad con Supabase
        if not self.storage_agent.verify_connection():
            logger.error("❌ Falló la verificación de conexión con Supabase. Abortando ciclo.")
            return False

        # Estado editorial persistente: distingue publicado/procesado, duplicado y pendiente.
        article_state = load_article_state(DATA_DIR, now_iso=start_time.isoformat())
        known_identities = set(known_source_identities(article_state.values()))
        retryable_identities = set(retryable_source_identities(article_state.values()))

        # Hashes de URLs ya tratadas. Las entradas pendientes/retryables se reintentan.
        existing_hashes = set()
        for record in article_state.values():
            source_url = record.get('source_url') or ''
            source_key = record.get('source_identity') or source_url
            if source_key and source_key.rstrip('/') in retryable_identities:
                continue
            for candidate_url in (source_url, source_url.rstrip('/'), source_key):
                if candidate_url:
                    existing_hashes.add(hashlib.md5(candidate_url.encode('utf-8')).hexdigest())

        try:
            recent_published = self.storage_agent.find_recent_processed_articles(days=3, limit=150)
        except Exception as exc:
            logger.warning(f"  [Deduplicación] No pude leer recientes de Supabase: {exc}")
            recent_published = []

        # ----------------------------------------------------------------------
        # PASO 1: SCRAPING
        # ----------------------------------------------------------------------
        logger.info("📰 [PASO 1/6] ScraperAgent: Extrayendo noticias locales...")
        scraped_articles = self.scraper_agent.scrape_all(
            limit_per_source=self.limit_per_source,
            existing_hashes=existing_hashes
        )

        duplicate_articles = []
        processed_for_state = []

        if not scraped_articles:
            logger.info("ℹ️ No se detectaron noticias nuevas en las portadas.")
            # Verificar si hay borradores previos pendientes de procesar
            pending_db = self.storage_agent.find_pending_ai_articles(limit=5)
            if not pending_db:
                logger.info("✅ No hay tareas pendientes en la base de datos.")
                save_article_state(DATA_DIR, article_state, duplicate_articles=duplicate_articles)
                return True
            logger.info(f"🔁 Se encontraron {len(pending_db)} artículos en borrador para continuar el flujo.")
            articles_to_process = pending_db
        else:
            logger.info(f"✅ [PASO 1/6] Scraping finalizado: {len(scraped_articles)} artículos nuevos extraídos.")

            # ------------------------------------------------------------------
            # PASO 2: GUARDAR EN BASE DE DATOS (BORRADOR) O ACTUALIZAR NOTA EXISTENTE
            # ------------------------------------------------------------------
            logger.info("💾 [PASO 2/6] StorageAgent: Clasificando nuevas, actualizaciones y duplicados...")

            articles_to_process = []
            accepted, duplicate_articles, _ = classify_candidates(
                scraped_articles,
                processed_by_url=article_state,
                recent_published=recent_published,
            )

            for art in accepted:
                if art.get('id'):
                    logger.info(f"  [Deduplicación] Actualizando noticia existente ID {art['id']}: '{art.get('title', '')[:50]}...'")
                    articles_to_process.append(art)
                    processed_for_state.append(art)
                    continue

                draft_record = self.storage_agent.save_draft(art)
                if draft_record and draft_record.get('id'):
                    art['id'] = draft_record['id']
                    art['db_id'] = draft_record['id']
                    art['db_status'] = 'draft'
                    articles_to_process.append(art)
                    processed_for_state.append(art)
                time.sleep(0.5)

            if duplicate_articles:
                logger.info(f"🔁 [PASO 2/6] Descartados como duplicados/ya tratados: {len(duplicate_articles)}.")

            logger.info(f"✅ [PASO 2/6] Artículos listos para procesar: {len(articles_to_process)}.")

            # ── Auditoría QA Paso 2 ── Verificar calidad de imágenes capturadas
            if self.qa:
                qa_results = [self.qa.audit_scraped_article(a) for a in articles_to_process]
                qa_pass = sum(1 for r in qa_results if r.is_ok())
                qa_errors = sum(1 for r in qa_results if r.severity == 'error')
                logger.info(f"  [QA-Paso2] Aprobados: {qa_pass}/{len(articles_to_process)}，errores: {qa_errors}")
                # Reparar automáticamente URLs de imagen problemáticas (buscar mejor imagen en la lista de images)
                for art, qa_res in zip(articles_to_process, qa_results):
                    if qa_res.severity == 'error' and any(i['field'] == 'image_url' for i in qa_res.issues):
                        # Intentar encontrar una buena imagen de la lista art['images']
                        candidate_imgs = art.get('images', [])
                        fixed = False
                        for cand in candidate_imgs:
                            if QAAuditor.is_valid_image_url(cand) and cand != art.get('image_url'):
                                logger.info(f"  [QA-Paso2] Reparación automática article={art.get('id')} imagen → {cand[:70]}")
                                art['image_url'] = cand
                                art['og_image_url'] = cand
                                fixed = True
                                break
                        if not fixed:
                            logger.warning(f"  [QA-Paso2] No se pudo reparar article={art.get('id')} problema de imagen: {[i['message'] for i in qa_res.issues if i['field']=='image_url']}")

        if not articles_to_process:
            if duplicate_articles:
                logger.info("ℹ️ No se publicaron notas nuevas: todas las candidatas ya fueron tratadas o son actualizaciones menores.")
            save_article_state(DATA_DIR, article_state, processed_articles=processed_for_state, duplicate_articles=duplicate_articles)
            logger.warning("⚠️ No se pudieron registrar artículos en la base de datos.")
            return False

        # ----------------------------------------------------------------------
        # PASO 3: MODIFICAR TÍTULO Y TEXTO CON IA
        # ----------------------------------------------------------------------
        logger.info("🤖 [PASO 3/6] AiRewriterAgent: Reestructurando con IA Free-First (GLM/Gemini/OpenAI/Fallback)...")
        modified_list = []
        for art in articles_to_process:
            ai_data = self.rewriter_agent.rewrite_article(art)
            if ai_data.get('es_local_regional') is False or ai_data.get('rejected'):
                logger.info(f"  [Orchestrator] Omitiendo noticia nacional/internacional rechazada: '{art.get('title', '')[:50]}'")
                continue
            art.update(ai_data)
            modified_list.append(art)
            time.sleep(1.0)

        # Guardar en JSON local de respaldo
        with open(os.path.join(DATA_DIR, 'modified_articles.json'), 'w', encoding='utf-8') as f:
            json.dump(modified_list, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ [PASO 3/6] Modificación con IA completada: {len(modified_list)} artículos listos.")

        # ── Auditoría QA Paso 3 ── Verificar resultados de reescritura IA
        if self.qa:
            qa_results_r = [self.qa.audit_rewritten_article(a) for a in modified_list]
            qa_pass = sum(1 for r in qa_results_r if r.is_ok())
            qa_errors = sum(1 for r in qa_results_r if r.severity == 'error')
            qa_warns = sum(1 for r in qa_results_r if r.severity == 'warning')
            logger.info(f"  [QA-Paso3] Aprobados: {qa_pass}/{len(modified_list)}，alertas: {qa_warns}，errores: {qa_errors}")
            for art, qa_res in zip(modified_list, qa_results_r):
                if qa_res.severity in ('error', 'warning'):
                    issues_str = '; '.join(f"{i['field']}:{i['message']}" for i in qa_res.issues)
                    logger.warning(f"  [QA-Paso3] {art.get('titulo_ia','?')[:40]}... → {issues_str}")

        # ----------------------------------------------------------------------
        # PASO 4: GENERACIÓN Y OPTIMIZACIÓN DE AUDIO
        # ----------------------------------------------------------------------
        audios_generated = 0
        if self.enable_audio:
            logger.info("🎙️ [PASO 4/7] AudioGeneratorAgent: Generando locución en audio y subiendo a Storage...")
            for art in modified_list:
                art_id = art.get('id')
                title = art.get('titulo_ia') or art.get('title')
                text = art.get('contenido_ia') or art.get('text')
                desc = art.get('meta_description') or art.get('description') or ''

                audio_url = self.audio_agent.process_article_audio(
                    article_id=art_id,
                    title=title,
                    text=text,
                    description=desc
                )
                if audio_url:
                    art['audio_url'] = audio_url
                    # Duración real del audio final: el slide debe durar exactamente
                    # lo que dura la locución (incluye pausa de 1s + frase institucional)
                    _dur = getattr(self.audio_agent, 'last_audio_duration', None)
                    if _dur:
                        art['audio_duration'] = round(_dur, 1)
                    audios_generated += 1
                time.sleep(1.2)
            logger.info(f"✅ [PASO 4/7] Audios generados y alojados: {audios_generated}/{len(modified_list)} artículos.")
        else:
            logger.info("ℹ️ [PASO 4/7] Generación de audio omitida por configuración.")

        # ----------------------------------------------------------------------
        # PASO 5: GENERACIÓN DE SLIDES CON VOZ RIOPLATENSE
        # ----------------------------------------------------------------------
        slides_generated = 0
        if self.enable_slides:
            logger.info("🎬 [PASO 5/7] SlideGeneratorAgent: Generando slides dinámicos con fotos y voz rioplatense...")
            for art in modified_list:
                art_id = art.get('id')
                title = art.get('titulo_ia') or art.get('title')
                text = art.get('contenido_ia') or art.get('text')
                audio_url = art.get('audio_url') or ''
                image_urls = [art.get('image_url')] if art.get('image_url') else []

                slide_url = self.slide_agent.process_article_slide(
                    article_id=art_id,
                    title=title,
                    text=text,
                    audio_url=audio_url,
                    image_urls=image_urls,
                    audio_duration=art.get('audio_duration')
                )
                if slide_url:
                    art['url_slide'] = slide_url
                    slides_generated += 1
                time.sleep(1.5)
            logger.info(f"✅ [PASO 5/7] Slides generados y subidos: {slides_generated}/{len(modified_list)} artículos.")
        else:
            logger.info("ℹ️ [PASO 5/7] Generación de slides omitida por configuración.")

        # ----------------------------------------------------------------------
        # PASO 6: GUARDAR EN BASE DE DATOS (ACTUALIZAR CON IA, AUDIO Y SLIDE)
        # ----------------------------------------------------------------------
        logger.info("🔄 [PASO 6/7] StorageAgent: Actualizando registros en Supabase con IA, audio y slides...")
        updated_count = 0
        for art in modified_list:
            art_id = art.get('id')
            upd = self.storage_agent.update_with_ai_audio_and_slide(
                article_id=art_id,
                ai_data=art,
                audio_url=art.get('audio_url'),
                slide_url=art.get('url_slide')
            )
            if upd:
                updated_count += 1
            time.sleep(0.5)

        logger.info(f"✅ [PASO 6/7] Base de datos actualizada: {updated_count}/{len(modified_list)} artículos.")

        # ----------------------------------------------------------------------
        # PASO 7: FINALMENTE PUBLICAR
        # ----------------------------------------------------------------------
        logger.info("📢 [PASO 7/7] PublisherAgent: Publicando oficialmente...")
        published_count = 0
        for art in modified_list:
            art_id = art.get('id')
            img = art.get('image_url')
            pub = self.publisher_agent.publish_article(art_id, image_url=img, immediate=self.immediate_publish)
            if pub:
                published_count += 1
            time.sleep(0.5)

        logger.info(f"✅ [PASO 7/7] Publicación completada: {published_count}/{len(modified_list)} noticias en vivo.")

        # ── Auditoría QA Final (Paso 7) ── Verificación post-publicación
        final_qa_report = {'total': 0, 'ok': 0, 'warnings': 0, 'errors': 0, 'error_rate_pct': 0, 'status': 'passed'}
        if self.qa and modified_list:
            try:
                from .storage_agent import StorageAgent as SA
                sa_check = SA()
                recent = sa_check.find_recent_processed_articles(days=1, limit=50)
                qa_final = self.qa.batch_audit_published(recent)
                final_qa_report = self.qa.generate_report(qa_final)
                logger.info(f"  [QA-Final] Último día publicado: total={final_qa_report['total']}, "
                            f"aprobados={final_qa_report['ok']}, alertas={final_qa_report['warnings']}, "
                            f"errores={final_qa_report['errors']}, estado={final_qa_report['status']}")
                if final_qa_report['errors'] > 0:
                    for err_art in final_qa_report.get('error_articles', []):
                        logger.error(f"  [QA-Final ERROR] ID={err_art['article_id']} título={err_art['title'][:50]}: "
                                     f"{[i['message'] for i in err_art['issues']]}")

                # ── Verificación de imágenes duplicadas en TODOS los publicados ──
                try:
                    dup_report = self.qa.detect_and_fix_duplicate_images()
                    if dup_report.get('status') == 'skipped':
                        logger.info(f"  [QA-DupImg] Omiso: {dup_report.get('reason', '')}")
                    elif dup_report.get('status') == 'error':
                        logger.error(f"  [QA-DupImg] Error: {dup_report}")
                    else:
                        logger.info(f"  [QA-DupImg] Artículos: {dup_report['total_articulos']}, "
                                    f"únicas: {dup_report['imagenes_unicas']}, "
                                    f"duplicados: {dup_report['grupos_duplicados']}, "
                                    f"fijados: {dup_report['fijados']}, "
                                    f"no_fijados: {dup_report['no_fijados']}")
                except Exception as e:
                    logger.warning(f"[QA-DupImg] Excepción: {e}")

                # ── Verificación de cron health ──
                try:
                    cron_report = self.qa.check_cron_health()
                    if cron_report.get('status') == 'ok':
                        logger.info(f"  [QA-Cron] ✅ Pipeline cron OK — Último: {cron_report['last_run']}, Próximo: {cron_report['next_run']} ({cron_report['schedule']})")
                    elif cron_report.get('status') == 'warning':
                        logger.warning(f"  [QA-Cron] ⚠️ Cron con advertencias: {cron_report['issues']}")
                    elif cron_report.get('status') == 'missing':
                        logger.error(f"  [QA-Cron] ❌ CRÍTICO: {cron_report['issues']}")
                    else:
                        logger.error(f"  [QA-Cron] ❌ Error: {cron_report['issues']}")

                    # Log de issues de otros jobs
                    for issue in cron_report.get('issues', []):
                        if 'freellmapi' in issue.lower() or 'cron-health' in issue.lower():
                            logger.warning(f"  [QA-Cron] Job auxiliar con issues: {issue}")

                except Exception as e:
                    logger.warning(f"[QA-Cron] Excepción: {e}")
            except Exception as e:
                logger.warning(f"[QA-Final] Excepción en auditoría final: {e}")

        # Generar reporte de ciclo
        duration = datetime.now() - start_time
        cycle_report = {
            'execution_id': self.execution_count + 1,
            'start_time': start_time.isoformat(),
            'end_time': datetime.now().isoformat(),
            'duration_seconds': duration.total_seconds(),
            'scraped_count': len(scraped_articles),
            'drafts_saved_to_db': len(articles_to_process),
            'ai_modified_count': len(modified_list),
            'audios_generated_count': audios_generated,
            'slides_generated_count': slides_generated,
            'db_updated_with_ai_audio_slide': updated_count,
            'published_count': published_count,
            'success_rate': (published_count / len(modified_list) * 100) if modified_list else 100.0,
            'timestamp': datetime.now().isoformat()
        }

        with open(os.path.join(DATA_DIR, 'cycle_summary.json'), 'w', encoding='utf-8') as f:
            json.dump(cycle_report, f, ensure_ascii=False, indent=2)

        self.execution_count += 1
        self.last_execution = datetime.now()

        logger.info(f"🎉 Ciclo completado con éxito en {duration.total_seconds():.1f} segundos.")
        save_article_state(DATA_DIR, article_state, processed_articles=modified_list, duplicate_articles=duplicate_articles, status='published')
        return True

    def start_scheduler(self):
        """Inicia el ciclo automático en un hilo en segundo plano."""
        self.running = True

        def loop():
            while self.running and not self._stop_event.is_set():
                self.run_full_pipeline()
                next_time, desc = self.get_next_execution_time()
                wait_sec = max(10, (next_time - datetime.now()).total_seconds())
                logger.info(f"⏰ Próximo ciclo en {wait_sec/60:.1f} minutos ({next_time.strftime('%H:%M:%S')}) — Franja: {desc}")
                self._stop_event.wait(timeout=wait_sec)

        self.thread = threading.Thread(target=loop, daemon=True)
        self.thread.start()
        logger.info("🟢 Agente Orquestador iniciado en modo continuo.")

    def stop_scheduler(self):
        """Detiene el orquestador de manera limpia."""
        self.running = False
        self._stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("🔴 Agente Orquestador detenido.")
