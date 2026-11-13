# -*- coding: utf-8 -*-
"""
tests/test_ara_script_agent.py — Tests del agente generador de JSON estilo Ara.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.ara_script_agent import AraScriptAgent, TENOR_VALUES, LENGUAJE_CORPORAL_VALUES, RITMO_CAMARA_VALUES


class TestAraPromptBuilder(unittest.TestCase):
    """Pruebas unitarias del constructor de prompts."""

    def setUp(self):
        self.agent = AraScriptAgent()

    def test_build_prompt_contains_article_data(self):
        prompt = self.agent._build_prompt(
            title_radial="Sivero vende vacunos en Saladillo",
            content="Una jornada récord de venta de ganados.",
            tono="NEUTRAL",
        )
        self.assertIn("Sivero vende vacunos en Saladillo", prompt)
        self.assertIn("Una jornada récord de venta de ganados.", prompt)
        self.assertIn("informativo_servicio", prompt)

    def test_build_prompt_tenor_neutral_mapea(self):
        prompt = self.agent._build_prompt("Título", "Contenido", "NEUTRAL")
        self.assertIn("informativo_servicio", prompt)

    def test_build_prompt_tenor_solemn_mapea(self):
        prompt = self.agent._build_prompt("Título", "Contenido", "SOLEMNE")
        self.assertIn("sensible_luto", prompt)

    def test_build_prompt_tenor_alegre_mapea(self):
        prompt = self.agent._build_prompt("Título", "Contenido", "ALEGRE")
        self.assertIn("alegre_cultural", prompt)


class TestAraValidation(unittest.TestCase):
    """Pruebas unitarias del validador de JSON Ara."""

    def setUp(self):
        self.agent = AraScriptAgent()

    def _make_valid_json(self, guion_words=20, tenor="informativo_servicio"):
        """Constructor helper para un JSON Ara válido."""
        guion = " ".join([f"palabra{i}" for i in range(guion_words)]) + "."
        return {
            "version": "1.0",
            "contenido": {
                "guion_ara": guion,
                "volanta_zocalo": "DEPORTES",
                "titulo_zocalo": "Nuevo campeonato local arranca este sábado",
            },
            "meta_ara": {
                "tenor": tenor,
                "permitir_sonrisa": True,
                "tono_vocal": "Varonil media edad, español argentino rioplatense",
                "expresion_inicio": "Mira al lente y asiente",
                "expresion_desarrollo": "Gestos naturales con ambas manos",
                "expresion_cierre": "Asentimiento final sereno",
                "lenguaje_corporal": "postura_firme_contenida",
                "ambiente_sonoro": "Sonido de calle céntrica",
                "ritmo_camara": "plano_fijo_estable",
                "requiere_aprobacion_sensible": False,
            },
        }

    def test_valid_json_passes(self):
        ok, errs = self.agent.validate_ara_json(self._make_valid_json())
        self.assertTrue(ok, f"Errores: {errs}")

    def test_version_required(self):
        data = self._make_valid_json()
        data["version"] = "2.0"
        ok, errs = self.agent.validate_ara_json(data)
        self.assertFalse(ok)
        self.assertTrue(any("version" in e for e in errs))

    def test_guion_too_long(self):
        data = self._make_valid_json(guion_words=30)
        ok, errs = self.agent.validate_ara_json(data)
        self.assertFalse(ok)
        self.assertTrue(any("25 palabras" in e for e in errs))

    def test_guion_empty(self):
        data = self._make_valid_json()
        data["contenido"]["guion_ara"] = ""
        ok, errs = self.agent.validate_ara_json(data)
        self.assertFalse(ok)
        self.assertTrue(any("vacío" in e or "corto" in e for e in errs))

    def test_volanta_exceeds_3_words(self):
        data = self._make_valid_json()
        data["contenido"]["volanta_zocalo"] = "DEPORTES NOTICIAS LOCALES EXTRA"
        ok, errs = self.agent.validate_ara_json(data)
        self.assertFalse(ok)
        self.assertTrue(any("excede 3 palabras" in e for e in errs))

    def test_titulo_exceeds_8_words(self):
        data = self._make_valid_json()
        data["contenido"]["titulo_zocalo"] = "Uno dos tres cuatro cinco seis siete ocho nueve palabras"
        ok, errs = self.agent.validate_ara_json(data)
        self.assertFalse(ok)
        self.assertTrue(any("excede 8 palabras" in e for e in errs))

    def test_invalid_tenor_rejected(self):
        data = self._make_valid_json(tenor="tenor_inventado")
        ok, errs = self.agent.validate_ara_json(data)
        self.assertFalse(ok)
        self.assertTrue(any("inválido" in e for e in errs))

    def test_missing_contenido_block(self):
        data = self._make_valid_json()
        del data["contenido"]
        ok, errs = self.agent.validate_ara_json(data)
        self.assertFalse(ok)
        self.assertTrue(any("'contenido' es requerido" in e for e in errs))

    def test_missing_meta_ara_block(self):
        data = self._make_valid_json()
        del data["meta_ara"]
        ok, errs = self.agent.validate_ara_json(data)
        self.assertFalse(ok)
        self.assertTrue(any("'meta_ara' es requerido" in e for e in errs))

    def test_non_dict_input(self):
        ok, errs = self.agent.validate_ara_json("not a dict")
        self.assertFalse(ok)
        self.assertEqual(errs, ["El resultado no es un objeto JSON"])

    def test_prohibited_words_blocked_when_not_allowed(self):
        """当 permitir_sonrisa=False, palabras como 'sonrisa' deben bloquearse."""
        data = self._make_valid_json()
        data["meta_ara"]["tenor"] = "policial_grave"
        data["meta_ara"]["permitir_sonrisa"] = False
        data["meta_ara"]["expresion_inicio"] = "Sonrisa leve mientras mira al lente"
        ok, errs = self.agent.validate_ara_json(data)
        self.assertFalse(ok)
        self.assertTrue(any("incompatibles" in e for e in errs))

    def test_no_false_positive_on_permitir_sonrisa_true(self):
        """当 permitir_sonrisa=True, 'sonrisa' no debe ser rechazada."""
        data = self._make_valid_json()
        data["meta_ara"]["permitir_sonrisa"] = True
        data["meta_ara"]["expresion_desarrollo"] = "Sonríe moderadamente entre frase y frase"
        ok, errs = self.agent.validate_ara_json(data)
        self.assertTrue(ok, f"Falso positivo: {errs}")


class TestHeuristicFallback(unittest.TestCase):
    """Pruebas del fallback heurístico cuando falla la API de IA."""

    def setUp(self):
        self.agent = AraScriptAgent()

    def test_fallback_returns_valid_structure(self):
        data = self.agent.apply_heuristic_fallback(
            title="Festival de música en Saladillo",
            content="Este fin de semana se realizará el festival anual de música en la plaza principal de Saladillo con artistas locales.",
            tono="ALEGRE",
        )
        ok, errs = self.agent.validate_ara_json(data)
        self.assertTrue(ok, f"Fallback errors: {errs}")
        self.assertEqual(data["version"], "1.0")
        self.assertEqual(data["meta_ara"]["tenor"], "alegre_cultural")

    def test_fallback_sensitive_tone(self):
        data = self.agent.apply_heuristic_fallback(
            title="Falleció vecino de Cazón",
            content="La comunidad de Cazón lamenta el fallecimiento de un residente.",
            tono="SOLEMNE",
        )
        self.assertEqual(data["meta_ara"]["tenor"], "sensible_luto")
        self.assertFalse(data["meta_ara"]["permitir_sonrisa"])
        self.assertTrue(data["meta_ara"]["requiere_aprobacion_sensible"])
        # Debe pasar validación sin errores
        ok, errs = self.agent.validate_ara_json(data)
        self.assertTrue(ok, f"Sensible tone failed validation: {errs}")

    def test_fallback_clamps_volanta_words(self):
        data = self.agent.apply_heuristic_fallback(
            title="Título muy largo con muchas palabras que sobran",
            content="Contenido corto.",
            tono="NEUTRAL",
        )
        volanta = data["contenido"]["volanta_zocalo"]
        self.assertLessEqual(len(volanta.split()), 3)

    def test_fallback_clamps_titulo_words(self):
        data = self.agent.apply_heuristic_fallback(
            title="Test",
            content="Un párrafo bastante extenso que tiene muchísimas palabras y debería ser recortado porque excede el límite permitido por las reglas del sistema editorial de noticias locales.",
            tono="NEUTRAL",
        )
        titulo = data["contenido"]["titulo_zocalo"]
        self.assertLessEqual(len(titulo.split()), 8)

    def test_fallback_short_content_guarantees_18_words(self):
        """Si el contenido es muy corto, el fallback debe expandir con el título hasta 18 palabras."""
        data = self.agent.apply_heuristic_fallback(
            title="Festival de música en Saladillo congrega a vecinos",
            content="Una noticia corta.",
            tono="ALEGRE",
        )
        guion = data["contenido"]["guion_ara"]
        words = len(guion.split())
        self.assertGreaterEqual(words, 18,
                                f"Guion muy corto: {words} palabras — '{guion}'")
        self.assertLessEqual(words, 25,
                             f"Guion excede máximo: {words} palabras")
        ok, errs = self.agent.validate_ara_json(data)
        self.assertTrue(ok, f"Fallo validación: {errs}")


class TestExtractJson(unittest.TestCase):
    """Pruebas de extracción segura de JSON desde texto libre."""

    def test_clean_json_string(self):
        raw = '{"version":"1.0","contenido":{}}'
        result = AraScriptAgent._extract_json(raw)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["version"], "1.0")

    def test_json_with_markdown_wrappers(self):
        raw = "```json\n{'version': '1.0'}\n```"
        result = AraScriptAgent._extract_json(raw)
        if result is not None:
            self.assertIsInstance(result, dict)

    def test_none_on_bare_text(self):
        result = AraScriptAgent._extract_json("esto no es json en absoluto")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
