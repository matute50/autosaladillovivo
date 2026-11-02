import unittest
from agents.ai_rewriter_agent import AiRewriterAgent


class AiRewriterAgentTests(unittest.TestCase):
    def setUp(self):
        self.agent = AiRewriterAgent()

    def test_local_heuristic_fallback_title_has_max_8_words(self):
        title = "Esta es una noticia con un titulo ridículamente largo"
        content = "El municipio de Saladillo anunció obras importantes en el centro de la ciudad para mejorar el tránsito y los accesos."
        
        result = self.agent.local_heuristic_fallback(title, content)
        
        words = result['titulo_optimizado'].split()
        self.assertEqual(8, len(words))
        self.assertTrue(result['titulo_optimizado'].startswith("Esta es una noticia"))

    def test_enforce_max_6_words_on_title(self):
        title_7_words = "Gran festejo por el aniversario de Saladillo"
        title_5_words = "Gran aniversario en Saladillo Norte"

        self.assertEqual(5, len(title_5_words.split()))
        self.assertEqual(7, len(title_7_words.split()))

        trimmed_7 = self.agent._clamp_title_to_max_words(title_7_words, max_words=6)
        trimmed_5 = self.agent._clamp_title_to_max_words(title_5_words, max_words=6)

        self.assertLessEqual(len(trimmed_7.split()), 6)
        self.assertEqual("Gran festejo por el aniversario de", trimmed_7)
        self.assertEqual("Gran aniversario en Saladillo Norte", trimmed_5)


if __name__ == '__main__':
    unittest.main()
