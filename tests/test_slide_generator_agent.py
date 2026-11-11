import unittest
from unittest.mock import Mock, patch
from agents.slide_generator_agent import SlideGeneratorAgent


class SlideGeneratorAgentTests(unittest.TestCase):
    def setUp(self):
        self.agent = SlideGeneratorAgent()

    def test_slide_contains_ken_burns_single_line_karaoke_and_audio(self):
        title = "Saladillo: Pavimentación y Obras Viales"
        text = "El intendente recorrió las obras de pavimentación con una inversión de 30 millones de pesos."
        audio_url = "https://example.com/audio.mp3"
        images = [{"url": "https://example.com/foto.jpg", "focal_x": 50.0, "focal_y": 40.0, "is_banner": False, "enable_ken_burns": True}]
        
        html = self.agent.create_slide_html(
            article_id=101,
            title=title,
            text=text,
            audio_url=audio_url,
            images=images,
            audio_duration=25.0
        )

        # 1. Animación Ken Burns y foto 100% nítida
        self.assertIn("kenBurnsZoom", html)
        self.assertIn("photo-main", html)
        self.assertNotIn("no-ken-burns", html)

        # 2. Sin Lower Thirds flotantes ni placas invasivas
        self.assertNotIn("floating-lower-third", html)
        self.assertNotIn("central-card", html)
        self.assertNotIn("rack-focus-layer", html)

        # 3. Subtitulado en una sola línea y karaoke dinámico sincronizado
        self.assertIn("subtitle-stage", html)
        self.assertIn("subtitle-single-line", html)
        self.assertIn("word-token", html)
        self.assertIn("timedLines", html)
        self.assertIn("updateSubtitles", html)
        self.assertIn("active-speaking", html)

        # 4. Audio con autoplay y play()
        self.assertIn('id="slideAudio"', html)
        self.assertIn(audio_url, html)
        self.assertIn("autoplay", html)
        self.assertIn("audio.play()", html)

    def test_ken_burns_enabled_always_in_process_images(self):
        images = self.agent.process_images_for_slide(102, [])
        self.assertTrue(images[0]["enable_ken_burns"])

    def test_generate_timed_subtitles_structure(self):
        text = "La Municipalidad comenzó los trabajos en el barrio esperanza."
        lines = self.agent.generate_timed_subtitles(text, 15.0)
        self.assertGreater(len(lines), 0)
        first_line = lines[0]
        self.assertIn("words", first_line)
        self.assertIn("start", first_line)
        self.assertIn("end", first_line)
        self.assertGreater(len(first_line["words"]), 0)
        first_word = first_line["words"][0]
        self.assertEqual(first_word["w"], "La")
        self.assertGreaterEqual(first_word["s"], 0.4)


if __name__ == "__main__":
    unittest.main()
