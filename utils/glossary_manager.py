# -*- coding: utf-8 -*-
"""
utils/glossary_manager.py — Gestor Centralizado de Glosario para Texto y Audio
==============================================================================
Permite cargar, gestionar y aplicar reglas de corrección ortotipográfica y fonética:
1. 'redaccion': Correcciones que aplican exclusivamente al texto visible de las noticias
   (título, cuerpo, slides, metadatos).
2. 'audio': Correcciones fonéticas que aplican exclusivamente a la pista de locución TTS
   (para que siglas, nombres propios, topónimos y extranjerismos suenen correctamente).
3. 'ambos': Correcciones que aplican tanto a la redacción de texto como al audio.

El glosario se almacena en 'data/glossary.json' y se recarga automáticamente si el archivo
es modificado en disco, sin requerir reinicios.
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger("GlossaryManager")

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_GLOSSARY_PATH = BASE_DIR / "data" / "glossary.json"


class GlossaryManager:
    _instance: Optional['GlossaryManager'] = None

    def __init__(self, glossary_path: Optional[Path] = None):
        self.glossary_path = Path(glossary_path or DEFAULT_GLOSSARY_PATH)
        self._cache: Dict[str, Dict[str, str]] = {"redaccion": {}, "audio": {}, "ambos": {}}
        self._compiled_regexes: Dict[str, list] = {"redaccion": [], "audio": [], "ambos": []}
        self._last_mtime: float = 0.0
        self.load_glossary()

    @classmethod
    def get_instance(cls, glossary_path: Optional[Path] = None) -> 'GlossaryManager':
        if cls._instance is None:
            cls._instance = GlossaryManager(glossary_path)
        return cls._instance

    def _ensure_default_file(self):
        """Crea el archivo glossary.json con una plantilla inicial si no existe."""
        if not self.glossary_path.exists():
            self.glossary_path.parent.mkdir(parents=True, exist_ok=True)
            default_content = {
                "_descripcion": "Glosario de Saladillo Vivo para redacción de textos y fonética de audios (TTS)",
                "redaccion": {
                    "Salomon": "Salomón",
                    "hcd": "HCD",
                    "ces": "CES",
                    "caps": "CAPS",
                    "udc": "UDC",
                    "curs": "CURS"
                },
                "audio": {
                    "CES": "C-E-S",
                    "C.E.S.": "C-E-S",
                    "HCD": "Ache-Ce-De",
                    "H.C.D.": "Ache-Ce-De",
                    "CURS": "Curs",
                    "CAPS": "Caps",
                    "Cicaré": "Sicaré",
                    "Delía": "De-lía",
                    "WhatsApp": "uatsap",
                    "Facebook": "feisbuc",
                    "Instagram": "instagran",
                    "Twitter": "tuíter",
                    "streaming": "stríming",
                    "online": "onláin"
                },
                "ambos": {
                    "Saladillo vivo": "Saladillo Vivo",
                    "saladillo vivo": "Saladillo Vivo"
                }
            }
            try:
                with open(self.glossary_path, "w", encoding="utf-8") as f:
                    json.dump(default_content, f, ensure_ascii=False, indent=2)
                logger.info(f"Plantilla inicial de glosario creada en {self.glossary_path}")
            except Exception as e:
                logger.warning(f"No se pudo crear plantilla de glosario: {e}")

    def load_glossary(self, force: bool = False) -> bool:
        """Carga el glosario desde el archivo JSON si ha cambiado o se fuerza."""
        self._ensure_default_file()
        if not self.glossary_path.exists():
            return False

        try:
            current_mtime = os.path.getmtime(self.glossary_path)
            if not force and current_mtime <= self._last_mtime:
                return True  # Sin cambios

            with open(self.glossary_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            redaccion = data.get("redaccion", {})
            audio = data.get("audio", {})
            ambos = data.get("ambos", {})

            self._cache = {
                "redaccion": {str(k): str(v) for k, v in redaccion.items() if not str(k).startswith("_")},
                "audio": {str(k): str(v) for k, v in audio.items() if not str(k).startswith("_")},
                "ambos": {str(k): str(v) for k, v in ambos.items() if not str(k).startswith("_")},
            }

            self._compile_rules()
            self._last_mtime = current_mtime
            logger.info(f"Glosario cargado ({len(self._cache['redaccion'])} redacción, "
                        f"{len(self._cache['audio'])} audio, {len(self._cache['ambos'])} ambos)")
            return True
        except Exception as e:
            logger.error(f"Error cargando glosario desde {self.glossary_path}: {e}")
            return False

    def _compile_rules(self):
        """Precompila expresiones regulares con límites de palabra para máxima velocidad."""
        self._compiled_regexes = {"redaccion": [], "audio": [], "ambos": []}

        for category, mapping in self._cache.items():
            compiled_list = []
            # Ordenar por longitud descendente para que palabras más largas tengan precedencia
            sorted_items = sorted(mapping.items(), key=lambda x: len(x[0]), reverse=True)
            for term, replacement in sorted_items:
                term_clean = term.strip()
                if not term_clean:
                    continue

                # Si el término es puramente alfanumérico o tiene puntos/guiones simples, aplicar \b
                # Si contiene caracteres no alfanuméricos especiales, escapar de forma segura
                escaped = re.escape(term_clean)

                # Si empieza y termina con caracteres de palabra, usar \b
                start_boundary = r'\b' if re.match(r'^\w', term_clean) else ''
                end_boundary = r'\b' if re.search(r'\w$', term_clean) else ''
                pattern_str = f"{start_boundary}{escaped}{end_boundary}"

                # Si el término original está en mayúsculas (ej: 'CES'), aplicar coincidencia exacta de mayúsculas;
                # de lo contrario, coincidencia insensible a mayúsculas
                flags = 0 if term_clean.isupper() and len(term_clean) > 1 else re.IGNORECASE
                try:
                    compiled = re.compile(pattern_str, flags)
                    compiled_list.append((compiled, replacement))
                except Exception as ex:
                    logger.warning(f"No se pudo compilar regla para '{term_clean}': {ex}")

            self._compiled_regexes[category] = compiled_list

    def _maybe_reload(self):
        """Verifica mtime de forma liviana antes de aplicar."""
        try:
            if self.glossary_path.exists():
                current_mtime = os.path.getmtime(self.glossary_path)
                if current_mtime > self._last_mtime:
                    self.load_glossary()
        except Exception:
            pass

    def apply_text_glossary(self, text: str) -> str:
        """
        Aplica las correcciones para redacción de textos ('redaccion' + 'ambos').
        Ideal para procesar títulos, artículos, metadatos y slides visibles.
        """
        if not text:
            return ""

        self._maybe_reload()
        result = text

        # 1. Aplicar reglas de 'ambos'
        for pattern, replacement in self._compiled_regexes.get("ambos", []):
            result = pattern.sub(replacement, result)

        # 2. Aplicar reglas específicas de 'redaccion'
        for pattern, replacement in self._compiled_regexes.get("redaccion", []):
            result = pattern.sub(replacement, result)

        return result

    def apply_audio_glossary(self, text: str) -> str:
        """
        Aplica las correcciones fonéticas para audios ('audio' + 'ambos').
        Ideal para procesar el guion antes de enviarlo a síntesis TTS (Voxtral/Edge/gTTS).
        """
        if not text:
            return ""

        self._maybe_reload()
        result = text

        # 1. Aplicar reglas de 'ambos'
        for pattern, replacement in self._compiled_regexes.get("ambos", []):
            result = pattern.sub(replacement, result)

        # 2. Aplicar reglas específicas de 'audio'
        for pattern, replacement in self._compiled_regexes.get("audio", []):
            result = pattern.sub(replacement, result)

        return result

    def add_term(self, term: str, replacement: str, target: str = "audio") -> bool:
        """
        Agrega o actualiza un término en el glosario persistente.
        target: 'redaccion', 'audio' o 'ambos'.
        """
        target = target.lower().strip()
        if target not in ("redaccion", "audio", "ambos"):
            raise ValueError(f"Target inválido: {target}. Debe ser 'redaccion', 'audio' o 'ambos'.")

        self.load_glossary(force=True)

        # Leer archivo completo para preservar comentarios
        data = {}
        if self.glossary_path.exists():
            try:
                with open(self.glossary_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}

        if target not in data:
            data[target] = {}

        data[target][term] = replacement

        try:
            with open(self.glossary_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.load_glossary(force=True)
            logger.info(f"Término agregado a '{target}': '{term}' -> '{replacement}'")
            return True
        except Exception as e:
            logger.error(f"Error guardando término en glosario: {e}")
            return False

    def remove_term(self, term: str, target: Optional[str] = None) -> bool:
        """Elimina un término de una categoría o de todas."""
        self.load_glossary(force=True)

        data = {}
        if self.glossary_path.exists():
            try:
                with open(self.glossary_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                return False

        targets = [target] if target else ["redaccion", "audio", "ambos"]
        removed = False
        for tgt in targets:
            if tgt in data and term in data[tgt]:
                del data[tgt][term]
                removed = True

        if removed:
            try:
                with open(self.glossary_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                self.load_glossary(force=True)
                return True
            except Exception as e:
                logger.error(f"Error eliminando término de glosario: {e}")
                return False
        return False

    def list_terms(self, target: Optional[str] = None) -> Dict[str, Dict[str, str]]:
        """Retorna copia del glosario cargado."""
        self._maybe_reload()
        if target and target in self._cache:
            return {target: dict(self._cache[target])}
        return {k: dict(v) for k, v in self._cache.items()}


# Funciones de conveniencia para acceso directo
def apply_text_glossary(text: str) -> str:
    """Aplica glosario de redacción y términos globales al texto."""
    return GlossaryManager.get_instance().apply_text_glossary(text)


def apply_audio_glossary(text: str) -> str:
    """Aplica glosario fonético y términos globales al texto para TTS."""
    return GlossaryManager.get_instance().apply_audio_glossary(text)
