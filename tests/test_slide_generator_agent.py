import unittest
from unittest.mock import Mock, patch
from agents.slide_generator_agent import SlideGeneratorAgent


class SlideGeneratorAgentTests(unittest.TestCase):
    def setUp(self):
        self.agent = SlideGeneratorAgent()

    def test_slide_contains_ken_burns_lower_third_and_audio(self):
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

        # 1. Animación Ken Burns
        self.assertIn("kenBurnsZoom", html)
        self.assertIn("photo-main", html)
        self.assertNotIn("no-ken-burns", html)

        # 2. Lower Thirds
        self.assertIn("floating-lower-third", html)
        self.assertIn("ltHeadline", html)
        self.assertIn("ltKicker", html)
        self.assertIn("ltProgressBar", html)

        # 3. Placa Central con Rack Focus
        self.assertIn("central-card", html)
        self.assertIn("rack-focus-layer", html)

        # 4. Audio con autoplay y play()
        self.assertIn('id="slideAudio"', html)
        self.assertIn(audio_url, html)
        self.assertIn("autoplay", html)
        self.assertIn("audio.play()", html)

    def test_ken_burns_enabled_always_in_process_images(self):
        images = self.agent.process_images_for_slide(102, [])
        self.assertTrue(images[0]["enable_ken_burns"])

    def test_short_mode_timing(self):
        html = self.agent.create_slide_html(
            article_id=103,
            title="Breve noticia",
            text="Texto muy corto.",
            audio_url="https://example.com/a.mp3",
            images=[{"url": "https://example.com/f.jpg"}],
            audio_duration=6.0
        )
        self.assertIn("isShortMode", html)


if __name__ == "__main__":
    unittest.main()
