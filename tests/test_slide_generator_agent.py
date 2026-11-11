import unittest
from unittest.mock import Mock, patch
from agents.slide_generator_agent import SlideGeneratorAgent


class SlideGeneratorAgentTests(unittest.TestCase):
    def setUp(self):
        self.agent = SlideGeneratorAgent()

    def test_slide_contains_ken_burns_single_line_karaoke_and_no_internal_audio(self):
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

        # 4. NO genera etiqueta <audio> interna — sincronización es centralizada por VideoSection.tsx
        self.assertNotIn('id="slideAudio"', html)
        self.assertNotIn("audio.play()", html)
        self.assertNotIn('<audio ', html)  # No debe haber apertura de tag audio

    def test_slide_uses_relative_fallback_image_url(self):
        """La URL de fallback debe ser relativa, no hardcodeada a dominio externo."""
        title = "Noticia sin imagen"
        text = "Texto de prueba."
        html = self.agent.create_slide_html(
            article_id=999,
            title=title,
            text=text,
            audio_url="",
            images=[],
            audio_duration=10.0
        )
        # Verificar que NO hay URLs hardcodeadas al dominio de Vercel
        self.assertNotIn("saladillovivo.vercel.app", html)
        # Cuando no hay imágenes, el HTML no incluye onerror con fallback;
        # la verificación se hace en process_images_for_slide
        fallback_result = self.agent.process_images_for_slide(999, [])
        self.assertEqual(fallback_result[0]["url"], "/default-og-image.png")

    def test_promo_line_has_dedicated_gold_css(self):
        """La clase .is-promo-line debe tener reglas CSS doradas definidas."""
        title = "Noticia prueba"
        text = "El intendente anunció obras nuevas en Saladillo."
        audio_url = "https://example.com/audio.mp3"
        images = [{"url": "https://example.com/foto.jpg", "focal_x": 50.0, "focal_y": 45.0, "is_banner": False, "enable_ken_burns": True}]

        html = self.agent.create_slide_html(
            article_id=200,
            title=title,
            text=text,
            audio_url=audio_url,
            images=images,
            audio_duration=18.0
        )

        # Debe existir la regla CSS para promo line (palabra activa dorada)
        self.assertIn(".subtitle-single-line.is-promo-line .word-token.active-speaking", html)
        self.assertIn("color: var(--color-speaking-gold)", html)
        # Debe existir también el estilo para palabras spoken y futuras en dorado atenuado
        self.assertIn(".subtitle-single-line.is-promo-line .word-token.spoken", html)
        self.assertIn(".subtitle-single-line.is-promo-line .word-token", html)

    def test_promo_always_included_when_duration_sufficient(self):
        """La frase institucional debe incluirse siempre que la duración total sea >= 5s."""
        text = "El intendente anunció obras nuevas en Saladillo."

        # Con 6 segundos SÍ debe incluir promo (umbral anterior era 8s)
        lines_6s = self.agent.generate_timed_subtitles(text, 6.0)
        self.assertTrue(any(l.get("is_promo") for l in lines_6s),
                        "Debería incluir promo con 6s de duración")

        # Con 10 segundos también debe incluir promo
        lines_10s = self.agent.generate_timed_subtitles(text, 10.0)
        self.assertTrue(any(l.get("is_promo") for l in lines_10s))

        # Con menos de 5s NO debería incluir promo
        lines_4s = self.agent.generate_timed_subtitles(text, 4.0)
        self.assertFalse(any(l.get("is_promo") for l in lines_4s),
                         "No debería incluir promo con solo 4s")

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

    def test_gallery_multiple_photos_renders_all_slides_with_fade_and_proportional_time(self):
        """Con galería de N fotos, el slide debe renderizar N .photo-slide, usar crossfade
        y asignar a cada foto un tiempo = duración_total_audio / cantidad_de_fotos."""
        n_photos = 4
        audio_duration = 36.0
        images = [
            {"url": f"https://example.com/foto{i}.jpg", "focal_x": 50.0, "focal_y": 45.0,
             "is_banner": False, "enable_ken_burns": True}
            for i in range(n_photos)
        ]
        html = self.agent.create_slide_html(
            article_id=500,
            title="Galería múltiple",
            text="Una noticia con varias fotos en su galería.",
            audio_url="https://example.com/audio.mp3",
            images=images,
            audio_duration=audio_duration
        )

        # 1. Se renderizan TODAS las capas .photo-slide (una por foto)
        import re
        self.assertEqual(len(re.findall(r'class="photo-slide', html)), n_photos)
        # Todas las URLs de las fotos están presentes
        for i in range(n_photos):
            self.assertIn(f"https://example.com/foto{i}.jpg", html)

        # 2. Crossfade (fade) entre fotos presente
        self.assertIn("transition: opacity 1.5s ease-in-out", html)
        self.assertIn(".photo-slide.active", html)

        # 3. Tiempo por foto = duración total / cantidad de fotos
        #    En el CSS: --slide-photo-duration: 9.0s (36/4)
        self.assertIn("--slide-photo-duration: 9.0s", html)
        #    En el JS: rotación robusta con tick persistente de 100ms que mide el
        #    tiempo real transcurrido (photoDurMs = round(photoDur*1000) = 9000),
        #    para que los AUDIO_TIME_UPDATE del padre NO reinicien ni congelen la galería.
        self.assertIn("photoDurMs = Math.round(photoDur * 1000)", html)
        self.assertIn("(currentPhotoIndex + 1) % slides.length", html)
        self.assertIn("}, 100);", html)

    def test_single_photo_uses_full_audio_duration(self):
        """Con una sola foto, el tiempo por foto es la duración completa del audio."""
        html = self.agent.create_slide_html(
            article_id=501,
            title="Foto única",
            text="Noticia con una sola foto.",
            audio_url="https://example.com/audio.mp3",
            images=[{"url": "https://example.com/unica.jpg", "focal_x": 50.0, "focal_y": 45.0,
                     "is_banner": False, "enable_ken_burns": True}],
            audio_duration=20.0
        )
        self.assertIn("--slide-photo-duration: 20.0s", html)
        self.assertIn("kenBurnsZoom", html)


if __name__ == "__main__":
    unittest.main()
