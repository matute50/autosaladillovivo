# -*- coding: utf-8 -*-
"""
Tests TDD para reglas fonéticas rioplatenses SOUL.md — TTS pipeline.

Reglas validadas por el usuario (2026-11-11):
  1. S en coda → HS (atenuación, NO desaparición). Ej: bosque→bohsque, estamos→ehstamohs.
  2. Tag tonal AL INICIO con "mild s-aspiration".
  3. Y copulativa/final → vocal "i" (NO "sh"). Ej: "voy y vengo"→"voy i vengo",
     "estoy y me voy"→"ehstoy i me voy".
  4. Y de ataque silábico (ya, yo) → "sh" (yeísmo rehilado).
  5. LL → "sh" (yeísmo rehilado).
  6. S intervocálica se PRESERVA (casa, saber).
  7. S inicial se PRESERVA.
"""
import unittest
from utils.ssml_builder import apply_rioplatense_phonetics as canon_phonetics
from utils.ssml_builder import STYLE_TAG as canon_style_tag


class TestSAspirationRule(unittest.TestCase):
    """CRÍTICA 1: S aspirada es ATENUACIÓN (hs), no desaparición (h)."""

    def test_bosque_hs(self):
        self.assertEqual(canon_phonetics("bosque"), "bohsque")

    def test_estamos_hs(self):
        self.assertEqual(canon_phonetics("estamos"), "ehstamohs")

    def test_despues_hs(self):
        self.assertEqual(canon_phonetics("después"), "dehspuéhs")

    def test_mismo_hs(self):
        self.assertEqual(canon_phonetics("mismo"), "mihsmo")

    def test_s_final_word(self):
        self.assertEqual(canon_phonetics("vas"), "vahs")

    def test_s_after_vowel_before_consonant(self):
        self.assertEqual(canon_phonetics("isla"), "ihsla")

    def test_s_in_bosques_plural(self):
        self.assertEqual(canon_phonetics("bosques"), "bohsquehs")

    def test_sentence_with_final_s(self):
        self.assertEqual(canon_phonetics("los chicos"), "lohs chicohs")


class TestSVowelsPreserved(unittest.TestCase):
    """La S intervocálica se PRESERVA."""

    def test_casa_preserved(self):
        self.assertEqual(canon_phonetics("casa"), "casa")

    def test_saber_preserved(self):
        self.assertEqual(canon_phonetics("saber"), "saber")

    def test_así_preserved(self):
        self.assertEqual(canon_phonetics("así"), "así")

    def test_island_no_change(self):
        self.assertNotIn("hs", canon_phonetics("casa"))

    def test_asier_no_aspiration(self):
        self.assertEqual(canon_phonetics("asier"), "asier")  # s intervocálica


class TestCopulativeYRule(unittest.TestCase):
    """CRÍTICA Y: La Y copulativa/final → vocal 'i', NUNCA 'sh'."""

    def test_ycopulativa_voy_y_vengo(self):
        self.assertEqual(canon_phonetics("voy y vengo"), "voy i vengo")

    def test_ycopulativa_estoy_y_me_voy(self):
        self.assertEqual(canon_phonetics("estoy y me voy"), "ehstoy i me voy")

    def test_ycopulativa_sinple(self):
        self.assertEqual(canon_phonetics("compré pan y leche"), "compré pan i leche")

    def test_ycopulativa_en_medio_oracion(self):
        self.assertEqual(canon_phonetics("hoy y mañana"), "hoy i mañana")

    def test_yfinal_not_sh(self):
        """La 'y' final de 'voy' se conserva como semivocal, NO se convierte en sh."""
        self.assertNotIn("sh", canon_phonetics("voy"))

    def test_endofword_y_preserved(self):
        self.assertEqual(canon_phonetics("estoy"), "ehstoy")


class TestAttackYSheismo(unittest.TestCase):
    """Yeísmo rehilado: Y/LL en ataque silábico → sh."""

    def test_yo_attack(self):
        self.assertEqual(canon_phonetics("yo"), "sho")

    def test_ya_attack(self):
        self.assertEqual(canon_phonetics("ya"), "sha")

    def test_llegar_ll(self):
        self.assertEqual(canon_phonetics("llegó"), "shegó")

    def test_camino_no_change(self):
        self.assertNotIn("sh", canon_phonetics("camino"))


class TestTagPositionAndContent(unittest.TestCase):
    """CRÍTICA 2: Tag al INICIO + mild s-aspiration."""

    def test_canonical_style_tag_includes_mild(self):
        self.assertIn("mild s-aspiration", canon_style_tag)

    def test_canonical_style_tag_at_start(self):
        self.assertTrue(canon_style_tag.startswith("[relaxed"))
        self.assertIn("argentinian rioplatense accent", canon_style_tag)


class TestAgentLocalBuildSsml(unittest.TestCase):
    """Test del build_ssml usado en runtime por AudioGeneratorAgent (Gemini TTS)."""

    def test_build_ssml_tag_position_and_content(self):
        """El build_ssml local de audio_generator_agent debe tener el tag al inicio con mild s-aspiration."""
        from agents.audio_generator_agent import build_ssml
        result = build_ssml("voy y vengo")
        self.assertTrue(result.startswith("[relaxed"))
        self.assertIn("mild s-aspiration", result)
        self.assertIn("voy i vengo", result)

    def test_build_ssml_s_aspiration_hs(self):
        from agents.audio_generator_agent import build_ssml
        result = build_ssml("bosque")
        self.assertIn("bohsque", result)
        self.assertNotIn("bohque", result)

    def test_build_ssml_copulative_y_i(self):
        from agents.audio_generator_agent import build_ssml
        result = build_ssml("voy y vengo")
        # Debe convertir Y copulativa a i, NO a sh
        self.assertIn("voy i vengo", result)
        self.assertNotIn("voy sh vengo", result)

    def test_build_ssml_estoy_rule(self):
        from agents.audio_generator_agent import build_ssml
        result = build_ssml("estoy y me voy")
        self.assertIn("ehstoy i me voy", result)


if __name__ == '__main__':
    unittest.main()
