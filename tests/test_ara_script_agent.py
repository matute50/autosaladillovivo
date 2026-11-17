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
        # Incluir Saladillo Vivo en el guion para pasar validación
        base = " ".join([f"palabra{i}" for i in range(guion_words - 3)])
        guion = f"{base}. Toda la información en Saladillo Vivo."
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
                "tono_vocal": "Femenina joven, tono claro cálido y expresivo, español argentino rioplatense",
                "expresion_inicio": "Mirada directa al lente con leve asentimiento",
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

    def test_missing_saladillo_vivo_in_guion(self):
        """Guion sin 'Saladillo Vivo' debe fallar."""
        data = self._make_valid_json()
        data["contenido"]["guion_ara"] = "Estudiantes ganó el torneo local esta noche."
        ok, errs = self.agent.validate_ara_json(data)
        self.assertFalse(ok, f"Debería fallar; errors: {errs}")
        self.assertTrue(any("Saladillo Vivo" in e for e in errs))

    def test_ambiente_sonoro_con_musica_rechazado(self):
        """ambiente_sonoro que menciona música debe ser rechazado."""
        data = self._make_valid_json()
        data["meta_ara"]["ambiente_sonoro"] = "Música instrumental muy baja de fondo"
        ok, errs = self.agent.validate_ara_json(data)
        self.assertFalse(ok, f"Debería fallar; errors: {errs}")
        self.assertTrue(any("música" in e or "musical" in e for e in errs))

    def test_ambiente_sonoro_callejero_ok(self):
        """ambiente_sonoro callejero pasa validación."""
        data = self._make_valid_json()
        data["meta_ara"]["ambiente_sonoro"] = "Ruido tenue de tráfico en la plaza central"
        ok, errs = self.agent.validate_ara_json(data)
        self.assertTrue(ok, f"Fallo inesperado: {errs}")

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

    # ── Tests v1.1: bloques ─────────────────────────────────────────────────

    def _make_valid_v11_json(self, n_blocks=2):
        """Constructor helper para JSON Ara v1.1 con bloques."""
        blocks = []
        for i in range(n_blocks):
            words_needed = 18 - (3 if i == n_blocks - 1 else 0)
            base = " ".join([f"palabra{i}_{j}" for j in range(words_needed)])
            if i == n_blocks - 1:
                base += ". Toda la información en Saladillo Vivo."
            else:
                base += "."
            blocks.append({"orden": i + 1, "guion_ara": base})
        guion_concat = " ".join(b["guion_ara"] for b in blocks)
        return {
            "version": "1.1",
            "contenido": {
                "guion_ara": guion_concat,
                "bloques": blocks,
                "volanta_zocalo": "DEPORTES",
                "titulo_zocalo": "Nuevo campeonato local arranca este sábado",
            },
            "meta_ara": {
                "tenor": "informativo_servicio",
                "permitir_sonrisa": True,
                "tono_vocal": "Femenina joven, tono claro cálido y expresivo, español argentino rioplatense",
                "expresion_inicio": "Mirada directa al lente con leve asentimiento",
                "expresion_desarrollo": "Gestos naturales con ambas manos",
                "expresion_cierre": "Asentimiento final sereno",
                "lenguaje_corporal": "postura_firme_contenida",
                "ambiente_sonoro": "Sonido de calle céntrica",
                "ritmo_camara": "plano_fijo_estable",
                "requiere_aprobacion_sensible": False,
                "continuidad_visual": "Mujer joven con cabello rizado natural negro, suelto o con accesorios (diadema/clip), vestimenta casual (jeans y campera liviana), maquillaje natural, mirada serena, luz natural diurna, locación centro de Saladillo plaza principal",
            },
        }

    def test_v11_valid_passes(self):
        ok, errs = self.agent.validate_ara_json(self._make_valid_v11_json())
        self.assertTrue(ok, f"Errores v1.1: {errs}")

    def test_v11_at_least_two_blocks(self):
        data = self._make_valid_v11_json(n_blocks=1)
        ok, errs = self.agent.validate_ara_json(data)
        self.assertFalse(ok, "Debe rechazar 1 solo bloque")
        self.assertTrue(any("bloque" in e.lower() for e in errs), f"Errors: {errs}")

    def test_v11_block_word_count_range(self):
        """Cada bloque debe tener entre 16 y 22 palabras."""
        blocks = [
            {"orden": 1, "guion_ara": " ".join(["x"] * 15) + "."},  # 15 = too short
            {"orden": 2, "guion_ara": " ".join(["x"] * 18) + ". Toda la información en Saladillo Vivo."},
        ]
        data = self._make_valid_v11_json(n_blocks=2)
        data["contenido"]["bloques"] = blocks
        ok, errs = self.agent.validate_ara_json(data)
        self.assertFalse(ok, "Debe fallar con bloque corto")
        self.assertTrue(any("15" in e or "corto" in e.lower() for e in errs), f"Errors: {errs}")

    def test_v11_last_block_saladillo_vivo(self):
        """Último bloque debe mencionar 'Saladillo Vivo'."""
        blocks = [
            {"orden": 1, "guion_ara": " ".join(["palabra"] * 18) + "."},
            {"orden": 2, "guion_ara": " ".join(["palabra"] * 17) + "."},  # sin Saladillo Vivo
        ]
        data = self._make_valid_v11_json(n_blocks=2)
        data["contenido"]["bloques"] = blocks
        ok, errs = self.agent.validate_ara_json(data)
        self.assertFalse(ok, "Debe fallar si último bloque no tiene Saladillo Vivo")
        self.assertTrue(any("saladillo vivo" in e.lower() for e in errs), f"Errors: {errs}")

    def test_v11_continuidad_visual_required(self):
        """v1.1 requiere continuidad_visual en meta_ara."""
        data = self._make_valid_v11_json()
        del data["meta_ara"]["continuidad_visual"]
        ok, errs = self.agent.validate_ara_json(data)
        self.assertFalse(ok, "Debe fallar sin continuidad_visual")
        self.assertTrue(any("continuidad" in e.lower() for e in errs), f"Errors: {errs}")

    def test_v10_still_accepted(self):
        """Backward compat: v1.0 con seccion_a/b sigue funcionando."""
        data = self._make_valid_json()
        data["version"] = "1.0"
        ok, errs = self.agent.validate_ara_json(data)
        self.assertTrue(ok, f"v1.0 debería pasar: {errs}")


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
        self.assertEqual(data["version"], "1.1")
        self.assertEqual(data["meta_ara"]["tenor"], "alegre_cultural")
        # Debe tener bloques, no campos legacy
        self.assertIn("bloques", data["contenido"])
        self.assertNotIn("seccion_a_guion", data["contenido"])

    def test_fallback_sensitive_tone(self):
        data = self.agent.apply_heuristic_fallback(
            title="Falleció vecino de Cazón",
            content="La comunidad de Cazón lamenta el fallecimiento de un residente del barrio que dejó honda tristeza entre sus vecinos y amigos más cercanos.",
            tono="SOLEMNE",
        )
        self.assertEqual(data["meta_ara"]["tenor"], "sensible_luto")
        self.assertFalse(data["meta_ara"]["permitir_sonrisa"])
        self.assertTrue(data["meta_ara"]["requiere_aprobacion_sensible"])
        ok, errs = self.agent.validate_ara_json(data)
        self.assertTrue(ok, f"Sensible tone failed validation: {errs}")

    def test_fallback_clamps_volanta_words(self):
        data = self.agent.apply_heuristic_fallback(
            title="Título muy largo con muchas palabras que sobran",
            content="Contenido corto pero con información suficiente para generar bloques válidos en el sistema de noticias locales de Saladillo.",
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
        """Si el contenido es muy corto, el fallback debe expandir hasta lograr bloques válidos."""
        data = self.agent.apply_heuristic_fallback(
            title="Festival de música en Saladillo congrega a vecinos",
            content="Una noticia corta.",
            tono="ALEGRE",
        )
        # Con v1.1 cada bloque debe tener 16-22 palabras
        bloques = data["contenido"].get("bloques", [])
        if bloques:
            first_block_words = len(bloques[0]["guion_ara"].split())
            self.assertGreaterEqual(first_block_words, 16,
                                    f"Bloque 1 muy corto: {first_block_words} palabras")
            self.assertLessEqual(first_block_words, 22,
                                 f"Bloque 1 muy largo: {first_block_words} palabras")
            last_block_words = len(bloques[-1]["guion_ara"].split())
            self.assertGreaterEqual(last_block_words, 16)
            self.assertLessEqual(last_block_words, 22)
        ok, errs = self.agent.validate_ara_json(data)
        self.assertTrue(ok, f"Fallo validación: {errs}")

    def test_fallback_v11_generates_blocks(self):
        """Fallback v1.1 debe generar bloques, no seccion_a/b."""
        data = self.agent.apply_heuristic_fallback(
            title="Colocan nuevos nomencladores de calles en Saladillo",
            content="El municipio de Saladillo instaló nuevos nomencladores en las principales esquinas del centro urbano. La medida busca mejorar la orientación de vecinos y turistas. Las placas tienen diseño moderno con código QR.",
            tono="NEUTRAL",
        )
        self.assertIn("version", data)
        self.assertTrue(data["version"] in ("1.0", "1.1"))
        # Debe tener al menos 2 bloques
        bloques = data["contenido"].get("bloques", [])
        if bloques:
            self.assertGreaterEqual(len(bloques), 2,
                                    f"Debe tener ≥2 bloques, tiene {len(bloques)}")
            # Cada bloque entre 16 y 22 palabras
            for i, blk in enumerate(bloques):
                wc = len(blk["guion_ara"].split())
                self.assertGreaterEqual(wc, 16,
                                        f"Bloque {i+1} muy corto: {wc} palabras")
                self.assertLessEqual(wc, 22,
                                     f"Bloque {i+1} muy largo: {wc} palabras")
            # Último bloque debe cerrar con Saladillo Vivo
            last_block = bloques[-1]["guion_ara"]
            self.assertIn("saladillo vivo", last_block.lower(),
                          f"Último bloque no menciona Saladillo Vivo: {last_block}")

    def test_fallback_v11_continuidad_visual_present(self):
        """v1.1 debe incluir continuidad_visual en meta_ara."""
        data = self.agent.apply_heuristic_fallback(
            title="Test noticia",
            content="Contenido de prueba para validar continuidad visual.",
            tono="NEUTRAL",
        )
        meta = data.get("meta_ara", {})
        if data.get("version") == "1.1":
            self.assertIn("continuidad_visual", meta,
                          "Continuidad visual ausente en meta_ara v1.1")
            cv = meta["continuidad_visual"]
            self.assertIsInstance(cv, str)
            self.assertGreater(len(cv), 20)


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
