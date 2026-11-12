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

        # 1. Animación Ken Burns aplicada de forma INLINE vía activatePhoto (no clases CSS)
        self.assertIn("activatePhoto", html)
        self.assertIn("kenBurnsZoomIn", html)
        self.assertIn("photo-main", html)
        self.assertNotIn("no-ken-burns", html)
        # Clases kb-zoomin/kb-zoomout YA NO se inyectan: la dirección la decide el JS

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

    def test_promo_line_has_dedicated_branding_css(self):
        """La clase .is-promo-line debe tener reglas CSS con paleta de marca (celeste/azul)."""
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

        # Debe existir la regla CSS para promo line con paleta marca (no gold)
        self.assertIn(".subtitle-single-line.is-promo-line .word-token.active-speaking", html)
        self.assertIn("color: var(--sv-sky) !important", html)
        # Spoken y futuras también usan tonos celestes de marca
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

        # 3. Tiempo por segmento = duración total / (cantidad_de_fotos + 1).
        #    Se suma +1 porque el orden de rotación es [principal, …, principal]:
        #    N fotos intermedias + retorno final a la imagen principal al cerrar.
        #    CSS: --slide-photo-duration: 7.2s (36/5)
        self.assertIn("--slide-photo-duration: 7.2s", html)
        #    El JS define: rotationOrder = [0,1,2,3,0], nextRotationIndex=1,
        #    photoDurMs = round((baseDuration/segmentCount)*1000), sin usar módulo.
        self.assertIn("rotationOrder.push(0);", html)
        self.assertIn("var segmentCount = slides.length + 1;", html)
        self.assertIn("nextRotationIndex", html)
        self.assertNotIn("% slides.length", html)
        #    Reinicio de Ken Burns al volver a activar cada foto (reflow con offsetHeight)
        self.assertIn("mainImg.offsetHeight", html)
        #    La dirección (zoom in / out) la decide el JS según par/impar del índice, no clases CSS
        self.assertIn("idx % 2 === 0", html)
        self.assertNotIn("kb-zoomin", html)
        self.assertNotIn("kb-zoomout", html)

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
        # Foto única: ciclo completo zoom in → pausa 2s → zoom out vía applySinglePhotoKenBurns
        self.assertIn("activatePhoto", html)
        self.assertIn("applySinglePhotoKenBurns", html)
        self.assertIn("kenBurnsSinglePhoto", html)
        # La pausa de 2s es fija; el resto se reparte mitad zoom in / mitad zoom out
        self.assertIn("var pauseMs = 2000;", html)
        self.assertIn("kbSingleStyle", html)

    def test_timed_subtitles_correct_desfase(self):
        """Los timestamps deben escalar proporcionalmente para igualar body_dur real,
        y la promo debe empezar exactamente 1s después del body escalado."""
        from agents.slide_generator_agent import SlideGeneratorAgent
        agent = SlideGeneratorAgent()
        # Texto con 30 palabras, duración total simulada 17.73s
        lines = agent.generate_timed_subtitles(
            text="La Municipalidad anunció hoy la renovación integral de la plaza central con juegos inclusivos y nueva iluminación LED, además del inicio de las obras de pavimentación en varias calles del centro urbano.",
            total_duration=17.73,
            promo_phrase="Innovamos para que solo escuches. Solo en Saladillo Vivo."
        )
        # Debe haber líneas de cuerpo + 1 de promo
        body_lines = [l for l in lines if not l.get('is_promo')]
        promo_lines = [l for l in lines if l.get('is_promo')]
        self.assertGreater(len(body_lines), 0, "Debe haber al menos una línea de cuerpo")
        self.assertEqual(len(promo_lines), 1, "Debe haber exactamente una línea de promo")

        # El body debe terminar exactamente antes de la promo (+1s de pausa)
        last_body_end = body_lines[-1]["end"]
        promo_start = promo_lines[0]["start"]
        promo_end = promo_lines[0]["end"]
        # Promo debe empezar ~1s después del body
        self.assertAlmostEqual(promo_start - last_body_end, 1.0, delta=0.02,
            msg=f"La promo debe iniciar 1s después del body: body_end={last_body_end}, promo_start={promo_start}")
        # Promo debe terminar exactamente en total_duration
        self.assertAlmostEqual(promo_end, 17.73, delta=0.02,
            msg=f"La promo debe terminar en total_duration=17.73, terminó en {promo_end}")

    def test_estimate_audio_duration_formula_and_clamp(self):
        """La estimación de duración usa la fórmula de palabras/2.08 + buffer, clampada 4-120s."""
        agent = SlideGeneratorAgent()
        # Texto de 20 palabras -> (20/2.08) + 1 + 3 = 9.62 + 4 = 13.62 -> round = 13.6
        self.assertAlmostEqual(agent.estimate_audio_duration(" ".join(["palabra"] * 20)), 13.6, places=1)
        # Texto vacío -> duración mínima 4.0
        self.assertEqual(agent.estimate_audio_duration(""), 4.0)
        # Texto muy largo -> clamp a 120.0
        long_text = " ".join(["palabra"] * 500)
        self.assertLessEqual(agent.estimate_audio_duration(long_text), 120.0)

    def test_retry_constants_defined(self):
        """Las constantes de retry/backoff para uploads deben estar definidas en la clase."""
        agent = SlideGeneratorAgent()
        self.assertGreaterEqual(agent.MAX_UPLOAD_RETRIES, 1)
        self.assertGreater(agent.UPLOAD_BACKOFF_BASE, 1.0)


if __name__ == "__main__":
    unittest.main()
