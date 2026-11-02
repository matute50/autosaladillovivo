import unittest

from agents.article_ledger import (
    DECISION_NEW,
    DECISION_UPDATE,
    DECISION_DUPLICATE,
    classify_candidate,
    legacy_history_to_state,
    retryable_source_identities,
)


def article(title, text, url, **extra):
    data = {
        "title": title,
        "original_title": title,
        "text": text,
        "original_text": text,
        "source_url": url,
    }
    data.update(extra)
    return data


class ArticleLedgerTests(unittest.TestCase):
    def test_new_url_without_records_is_new(self):
        candidate = article(
            "Nueva obra en la plaza",
            "La Municipalidad comenzó una obra nueva en la plaza central de Saladillo.",
            "https://www.abcsaladillo.com.ar/general/nueva-obra-plaza/",
        )

        result = classify_candidate(candidate, {}, [])

        self.assertEqual(DECISION_NEW, result["decision"])
        self.assertIsNone(result["existing_db_id"])

    def test_same_url_unchanged_is_duplicate(self):
        candidate = article(
            "Nueva obra en la plaza",
            "La Municipalidad comenzó una obra nueva en la plaza central de Saladillo.",
            "https://www.abcsaladillo.com.ar/general/nueva-obra-plaza/",
        )

        state = classify_candidate(candidate, {}, [])
        processed = {state["source_identity"]: state["record"]}

        result = classify_candidate(candidate, processed, [])

        self.assertEqual(DECISION_DUPLICATE, result["decision"])
        self.assertEqual("unchanged_source_url", result["reason"])

    def test_same_url_with_substantial_new_body_is_update_and_keeps_db_id(self):
        original = article(
            "Continúan las obras en la plaza",
            "La Municipalidad comenzó una obra nueva en la plaza central de Saladillo.",
            "https://www.abcsaladillo.com.ar/general/obras-plaza/",
        )
        state = classify_candidate(original, {}, [])
        state["record"]["status"] = "published"
        state["record"]["db_id"] = 553
        processed = {state["source_identity"]: state["record"]}

        updated = article(
            "Continúan las obras en la plaza",
            "La Municipalidad comenzó una obra nueva en la plaza central de Saladillo. "
            "Además se instaló iluminación LED, rampas de accesibilidad y un nuevo sector de juegos, "
            "con una inversión provincial y la presencia de vecinos del barrio.",
            "https://www.abcsaladillo.com.ar/general/obras-plaza/",
        )

        result = classify_candidate(updated, processed, [])

        self.assertEqual(DECISION_UPDATE, result["decision"])
        self.assertEqual(553, result["existing_db_id"])
        self.assertEqual("content_changed", result["reason"])

    def test_legacy_unprocessed_history_entry_allows_retry(self):
        legacy_item = article(
            "Reunión por Fiestas Patrias",
            "El intendente se reunió con organizadores de la 34 edición de Fiestas Patrias.",
            "https://www.abcsaladillo.com.ar/general/reunion-fiestas-patrias/",
        )
        legacy_item["scraped_at"] = "2026-11-02T14:20:00"

        state = legacy_history_to_state([legacy_item], now_iso="2026-11-02T15:00:00")
        source_identity = next(iter(state))

        self.assertIn(source_identity, retryable_source_identities(state.values()))

    def test_legacy_processed_history_entry_is_not_retryable(self):
        legacy_item = article(
            "Noticia procesada",
            "El municipio procesó correctamente esta noticia y quedó publicada.",
            "https://www.abcsaladillo.com.ar/general/noticia-procesada/",
        )
        legacy_item["db_id"] = 123
        legacy_item["db_status"] = "published"
        legacy_item["scraped_at"] = "2026-11-01T12:00:00"

        state = legacy_history_to_state([legacy_item], now_iso="2026-11-02T15:00:00")
        source_identity = next(iter(state))

        self.assertNotIn(source_identity, retryable_source_identities(state.values()))

    def test_different_local_titles_with_few_shared_words_are_not_duplicates(self):
        candidate = article(
            "Reunión por seguridad ciudadana",
            "El municipio analizó patrullaje, cámaras y denuncias vecinales en el centro.",
            "https://www.abcsaladillo.com.ar/general/reunion-seguridad/",
        )
        known = article(
            "Feria de emprendedores en Saladillo",
            "Emprendedores locales mostraron productos regionales en la plaza.",
            "https://www.abcsaladillo.com.ar/general/feria-emprendedores/",
            db_id=900,
            status="published",
        )

        result = classify_candidate(candidate, {}, [known])

        self.assertEqual(DECISION_NEW, result["decision"])

    def test_cross_media_same_fact_is_duplicate(self):
        candidate = article(
            "Saladillo inauguró el nuevo salón comunitario del barrio norte",
            "El intendente encabezó la inauguración del nuevo salón comunitario con vecinos, discursos y recorrido por las nuevas instalaciones.",
            "https://www.abcsaladillo.com.ar/general/inauguracion-salon-comunitario/",
        )
        known = article(
            "Inauguraron el nuevo salón comunitario del barrio norte",
            "El intendente encabezó la inauguración del nuevo salón comunitario con vecinos, discursos y recorrido por las nuevas instalaciones.",
            "https://ahorasaladillo-diariodigital.com.ar/inauguran-salon-comunitario/",
            db_id=901,
            status="published",
        )

        result = classify_candidate(candidate, {}, [known])

        self.assertEqual(DECISION_DUPLICATE, result["decision"])


if __name__ == "__main__":
    unittest.main()
