# -*- coding: utf-8 -*-
"""
agents/storage_agent.py — Agente de Base de Datos y Persistencia (Supabase)
========================================================================
Responsable de la persistencia de dos fases críticas en Supabase:
- Fase 1 (Paso 2): Ingesta inicial de noticias como borrador sin publicar ('draft', is_published=False).
- Fase 2 (Paso 4): Actualización del artículo con los textos, títulos y metadatos optimizados por IA.

Garantiza:
- Deduplicación robusta de slugs con verificación en tiempo real.
- Compatibilidad total con el esquema de Supabase (`articles`).
- Reintentos automáticos y fallback ante variaciones de schema cache.
"""

import os
import sys
import json
import time
import re
import unicodedata
from datetime import datetime

try:
    import requests
except ImportError:
    print("[StorageAgent] Error: Se requiere 'requests'. Ejecute: pip install requests")
    sys.exit(1)


def load_env_credentials():
    """Lee variables desde el entorno y desde .env.local / .env."""
    env = {}
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    for filename in ['.env.local', '.env']:
        filepath = os.path.join(base_dir, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            k, v = line.split('=', 1)
                            k, v = k.strip(), v.strip().strip("'\"")
                            if k not in env:
                                env[k] = v
            except Exception:
                pass

    for k, v in os.environ.items():
        env[k] = v

    supabase_url = env.get('NEXT_PUBLIC_SUPABASE_URL', 'https://otwvfihzaznyjvjtkvvd.supabase.co').rstrip('/')
    supabase_key = (
        env.get('SUPABASE_KEY') or
        env.get('SUPABASE_SERVICE_ROLE_KEY') or
        env.get('NEXT_PUBLIC_SUPABASE_ANON_KEY')
    )
    return supabase_url, supabase_key


class StorageAgent:
    """
    Agente de persistencia en Supabase (tabla 'articles').
    """
    def __init__(self, table='articles'):
        self.url, self.key = load_env_credentials()
        self.table = table
        self.base_rest_url = f"{self.url}/rest/v1/{self.table}"

    def get_headers(self, return_representation=True):
        """Genera cabeceras de autorización de PostgREST."""
        headers = {
            'Authorization': f'Bearer {self.key}',
            'Content-Type': 'application/json',
            'apikey': self.key,
        }
        if return_representation:
            headers['Prefer'] = 'return=representation'
        else:
            headers['Prefer'] = 'return=minimal'
        return headers

    def verify_connection(self):
        """Verifica que Supabase responda correctamente."""
        try:
            resp = requests.get(
                self.base_rest_url,
                params={'select': 'id', 'limit': 1},
                headers=self.get_headers(False),
                timeout=15
            )
            return resp.status_code == 200
        except Exception as e:
            print(f"  [StorageAgent] Error verificando conexión con Supabase: {e}")
            return False

    def slugify(self, text):
        """Genera un slug limpio y URL-friendly."""
        if not text:
            return f"noticia-{int(time.time())}"
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
        text = re.sub(r'[^\w\s-]', '', text).strip().lower()
        clean_slug = re.sub(r'[-\s]+', '-', text)
        return clean_slug[:90].rstrip('-')

    def check_slug_exists(self, slug):
        """Verifica si un slug ya existe en Supabase."""
        try:
            resp = requests.get(
                self.base_rest_url,
                params={'select': 'slug', 'slug': f'eq.{slug}', 'limit': 1},
                headers=self.get_headers(False),
                timeout=15
            )
            if resp.status_code == 200:
                data = resp.json()
                return len(data) > 0
            return False
        except Exception:
            return False

    def generate_unique_slug(self, base_title):
        """Genera un slug único sin colisiones."""
        base_slug = self.slugify(base_title)
        if not self.check_slug_exists(base_slug):
            return base_slug

        counter = 1
        new_slug = f"{base_slug}-{counter}"
        while self.check_slug_exists(new_slug):
            counter += 1
            new_slug = f"{base_slug}-{counter}"
        return new_slug

    # --------------------------------------------------------------------------
    # PASO 2: GUARDAR EN BASE DE DATOS COMO BORRADOR (INGESTA RAW)
    # --------------------------------------------------------------------------
    def save_draft(self, article_data):
        """
        Inserta un artículo scrapeado en la tabla 'articles' en estado 'draft',
        con is_published=False, reservando el slug y devolviendo el ID asignado.
        """
        raw_title = article_data.get('original_title') or article_data.get('title') or 'Noticia sin título'
        raw_text = article_data.get('original_text') or article_data.get('text') or ''
        raw_desc = article_data.get('original_description') or article_data.get('description') or raw_text[:200]
        image_url = article_data.get('image_url') or 'https://saladillovivo.vercel.app/default-og-image.png'

        unique_slug = self.generate_unique_slug(raw_title)
        now_iso = datetime.now().isoformat()

        payload = {
            'title': raw_title,
            'text': raw_text,
            'description': raw_desc[:300],
            'slug': unique_slug,
            'image_url': image_url,
            'og_image_url': image_url,
            'thumbnail_url': image_url,
            'featureStatus': 'secondary',
            'status': 'draft',
            'is_published': False,
            'created_at': article_data.get('created_at') or now_iso,
            'updatedAt': now_iso
        }

        current_payload = dict(payload)
        headers = self.get_headers(return_representation=True)

        for _ in range(5):
            resp = requests.post(self.base_rest_url, headers=headers, json=current_payload, timeout=25)
            if resp.status_code in (200, 201):
                res_data = resp.json()
                if isinstance(res_data, list) and len(res_data) > 0:
                    created = res_data[0]
                    created_id = created.get('id')
                    print(f"  [StorageAgent] [Paso 2: Guardado Borrador] ID: {created_id} | Slug: {unique_slug}")
                    article_data['id'] = created_id
                    article_data['slug'] = unique_slug
                    article_data['db_saved'] = True
                    return created
            elif resp.status_code == 400 and 'in the schema cache' in resp.text:
                m = re.search(r"'(\w+)' column", resp.text)
                if m:
                    missing_col = m.group(1)
                    if missing_col in current_payload:
                        del current_payload[missing_col]
                        continue
            print(f"  [StorageAgent] Error al guardar borrador ({resp.status_code}): {resp.text}")
            break

        return None

    # --------------------------------------------------------------------------
    # PASO 5: OTRA VEZ GUARDAR EN BASE DE DATOS (ACTUALIZAR CON IA Y AUDIO)
    # --------------------------------------------------------------------------
    def update_with_ai(self, article_id, ai_data, audio_url=None):
        """
        Actualiza el registro existente en Supabase con los datos reestructurados por la IA
        y la URL de audio si fue generada.
        Actualiza title, text, description, metadatos SEO, keywords, featureStatus y audio_url.
        """
        if not article_id:
            print("  [StorageAgent] Error: Se requiere article_id para actualizar.")
            return None

        now_iso = datetime.now().isoformat()
        title = ai_data.get('titulo_ia') or ai_data.get('title')
        content = ai_data.get('contenido_ia') or ai_data.get('text')
        description = ai_data.get('meta_description') or ai_data.get('description')
        feature_status = ai_data.get('featureStatus') or 'secondary'
        final_audio_url = audio_url or ai_data.get('audio_url')

        raw_keywords = ai_data.get('meta_keywords') or ai_data.get('palabras_clave') or []
        keywords_str = ', '.join(raw_keywords) if isinstance(raw_keywords, list) else str(raw_keywords)

        patch_payload = {
            'title': title,
            'text': content,
            'description': description[:300] if description else '',
            'meta_title': title,
            'meta_description': description[:160] if description else '',
            'meta_keywords': keywords_str,
            'featureStatus': feature_status,
            'status': 'ai_processed',
            'updatedAt': now_iso
        }

        if final_audio_url:
            patch_payload['audio_url'] = final_audio_url

        current_payload = dict(patch_payload)
        headers = self.get_headers(return_representation=True)

        for _ in range(5):
            resp = requests.patch(
                self.base_rest_url,
                params={'id': f'eq.{article_id}'},
                headers=headers,
                json=current_payload,
                timeout=25
            )
            if resp.status_code in (200, 204):
                audio_tag = f" | Audio: [OK]" if final_audio_url else ""
                print(f"  [StorageAgent] [Paso 5: Actualizado en BD con IA{audio_tag}] ID: {article_id} | Titulo: \"{title[:40]}...\"")
                try:
                    res_json = resp.json()
                    return res_json[0] if (isinstance(res_json, list) and len(res_json) > 0) else current_payload
                except Exception:
                    return current_payload
            elif resp.status_code == 400 and 'in the schema cache' in resp.text:
                m = re.search(r"'(\w+)' column", resp.text)
                if m:
                    missing_col = m.group(1)
                    if missing_col in current_payload:
                        del current_payload[missing_col]
                        continue
            print(f"  [StorageAgent] Error al actualizar con IA ({resp.status_code}): {resp.text}")
            break

        return None

    def update_with_ai_and_audio(self, article_id, ai_data, audio_url=None):
        """Alias explícito para actualizar con IA y Audio."""
        return self.update_with_ai(article_id, ai_data, audio_url=audio_url)

    def find_pending_ai_articles(self, limit=20):
        """Busca artículos en la base de datos que estén en estado 'draft' y no procesados por IA."""
        try:
            resp = requests.get(
                self.base_rest_url,
                params={
                    'select': 'id,title,text,description,image_url,slug,status,created_at',
                    'status': 'eq.draft',
                    'is_published': 'eq.false',
                    'order': 'created_at.desc',
                    'limit': limit
                },
                headers=self.get_headers(False),
                timeout=20
            )
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            print(f"  [StorageAgent] Error buscando artículos pendientes: {e}")
            return []
