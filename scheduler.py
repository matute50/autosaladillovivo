#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scheduler.py — Sistema de Programación y Automatización de Scraping
===================================================================
Desarrollado para: Saladillo Vivo (Next.js 15 + Supabase)
Objetivo: Programar ejecuciones periódicas de `simple_scraper.py` adaptando la frecuencia
según la franja horaria del día (biblioteca estándar con time, datetime, threading).

Políticas de Intervalo:
- 07:00 a 12:00: cada 30 minutos (Horas pico de noticias matutinas).
- 12:00 a 22:00: cada 1 hora (Actualizaciones durante la tarde y noche).
- 22:00 a 07:00: cada 3 horas (Período nocturno / guardia pasiva).
"""

import time
import threading
import signal
import sys
from datetime import datetime, timedelta

# Asegurar soporte de encoding en terminales Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Importamos la función de ejecución principal del scraper
try:
    from simple_scraper import run_scraper
except ImportError:
    # Si se ejecuta desde otro directorio, agregamos la ruta local
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from simple_scraper import run_scraper


class NewsScraperScheduler:
    """
    Planificador de tareas de scraping basado en ventanas horarias dinámicas.
    Utiliza únicamente bibliotecas estándar de Python.
    """
    def __init__(self, sync_supabase=False, limit_per_source=15, run_immediately=True):
        self.sync_supabase = sync_supabase
        self.limit_per_source = limit_per_source
        self.run_immediately = run_immediately
        self.running = False
        self.thread = None
        self._stop_event = threading.Event()

    def get_next_scrape_time(self, current_dt=None):
        """
        Calcula la próxima fecha/hora exacta de scraping según la franja horaria local.
        - 07:00 - 12:00: Próxima media hora (:00 o :30)
        - 12:00 - 22:00: Próxima hora en punto (:00)
        - 22:00 - 07:00: Próximo bloque de 3 horas
        """
        now = current_dt or datetime.now()
        hour = now.hour

        if 7 <= hour < 12:
            # Ventana matutina: cada 30 minutos
            target_minute = 30 if now.minute < 30 else 0
            if target_minute == 0:
                next_time = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            else:
                next_time = now.replace(minute=30, second=0, microsecond=0)
            interval_desc = "30 minutos (franja 07:00 - 12:00)"

        elif 12 <= hour < 22:
            # Ventana tarde/noche: cada 1 hora
            next_time = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            interval_desc = "1 hora (franja 12:00 - 22:00)"

        else:
            # Ventana nocturna: cada 3 horas
            # Alineamos con bloques múltiplos de 3 o salto directo de 3 horas
            next_time = (now + timedelta(hours=3)).replace(minute=0, second=0, microsecond=0)
            interval_desc = "3 horas (franja nocturna 22:00 - 07:00)"

        return next_time, interval_desc

    def execute_scrape_cycle(self):
        """Ejecuta una pasada de scraping invocando al módulo simple_scraper."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{now_str}] >>> Iniciando ciclo de scraping programado...")

        try:
            articles = run_scraper(
                limit_per_source=self.limit_per_source,
                sync_supabase=self.sync_supabase
            )
            print(f"[{datetime.now().strftime('%H:%M:%S')}] >>> Ciclo completado: {len(articles)} artículos nuevos procesados.")
        except Exception as e:
            print(f"[!] Error durante el ciclo de scraping: {e}")

    def run_loop(self):
        """Bucle principal de ejecución del planificador."""
        print("=================================================================")
        print(" SALADILLO VIVO — SCHEDULER DE NOTICIAS ACTIVO")
        print(f" Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f" Sincronización Supabase: {'Activada' if self.sync_supabase else 'Desactivada (Solo local JSON)'}")
        print(" Presione Ctrl + C para detener.")
        print("=================================================================")

        if self.run_immediately:
            self.execute_scrape_cycle()

        while self.running and not self._stop_event.is_set():
            next_time, interval_desc = self.get_next_scrape_time()
            now = datetime.now()
            wait_seconds = max(5.0, (next_time - now).total_seconds())

            next_str = next_time.strftime("%H:%M:%S (%d/%m/%Y)")
            print(f"\n[Scheduler] Próximo scraping programado: {next_str}")
            print(f"[Scheduler] Intervalo vigente: {interval_desc} | Esperando {int(wait_seconds)} segundos...\n")

            # Espera fraccionada para responder inmediatamente a señales de interrupción
            if self._stop_event.wait(timeout=wait_seconds):
                break

            if self.running and not self._stop_event.is_set():
                self.execute_scrape_cycle()

        print("[Scheduler] Bucle de ejecución finalizado.")

    def start(self, in_background=False):
        """Inicia el planificador (en segundo plano o bloqueante)."""
        self.running = True
        self._stop_event.clear()

        if in_background:
            self.thread = threading.Thread(target=self.run_loop, daemon=True, name="NewsScraperSchedulerThread")
            self.thread.start()
            print("[Scheduler] Hilo en segundo plano iniciado.")
        else:
            self.run_loop()

    def stop(self):
        """Detiene limpiamente el planificador."""
        print("\n[Scheduler] Deteniendo planificador...")
        self.running = False
        self._stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        print("[Scheduler] Planificador detenido exitosamente.")


def main():
    """Entrada principal con soporte de argumentos y captura de Ctrl+C."""
    import argparse
    parser = argparse.ArgumentParser(description="Planificador de Scraping de Noticias para Saladillo Vivo")
    parser.add_argument('--sync-supabase', action='store_true', help='Sincronizar automáticamente con Supabase')
    parser.add_argument('--limit', type=int, default=15, help='Límite de artículos por portal (default: 15)')
    parser.add_argument('--no-initial-run', action='store_true', help='No ejecutar inmediatamente al iniciar, esperar al primer ciclo')

    args = parser.parse_args()

    scheduler = NewsScraperScheduler(
        sync_supabase=args.sync_supabase,
        limit_per_source=args.limit,
        run_immediately=not args.no_initial_run
    )

    # Captura de señales para cierre limpio (SIGINT / Ctrl+C)
    def handle_signal(sig, frame):
        scheduler.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        scheduler.start(in_background=False)
    except KeyboardInterrupt:
        scheduler.stop()


if __name__ == "__main__":
    main()
