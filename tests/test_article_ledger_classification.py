import unittest

from agents.article_ledger import classify_candidates, retryable_source_identities, legacy_history_to_state


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


class CandidateClassificationTests(unittest.TestCase):
    def test_accepts_new_and_pending_without_repeating_same_event_in_batch(self):
        new_article = article(
            "Nueva obra en la costanera",
            "La Municipalidad comenzó una obra nueva sobre la costanera con iluminación.",
            "https://www.abcsaladillo.com.ar/general/nueva-obra-costanera/",
        )
        pending_article = article(
            "Reunión por Fiestas Patrias",
            "El intendente se reunió con organizadores de la 34 edición de Fiestas Patrias.",
            "https://www.abcsaladillo.com.ar/general/reunion-fiestas-patrias/",
        )
        repeated = article(
            "Inauguran nueva obra en la costanera",
            "La Municipalidad comenzó una obra nueva sobre la costanera con iluminación.",
            "https://ahorasaladillo-diariodigital.com.ar/inauguran-nueva-obra-costanera/",
        )
        legacy_history = legacy_history_to_state(
            [article(
                "Reunión por Fiestas Patrias",
                "El intendente se reunió con organizadores de la 34 edición de Fiestas Patrias.",
                "https://www.abcsaladillo.com.ar/general/reunion-fiestas-patrias/",
                scraped_at="2026-11-02T14:20:00",
            )],
            now_iso="2026-11-02T15:00:00",
        )
        processed_by_url = {
            source: record
            for source, record in legacy_history.items()
            if source not in set(retryable_source_identities(legacy_history.values()))
        }

        accepted, duplicates, results = classify_candidates(
            [new_article, pending_article, repeated],
            processed_by_url=processed_by_url,
            recent_published=[],
        )

        self.assertEqual(2, len(accepted))
        self.assertEqual(
            {
                "https://www.abcsaladillo.com.ar/general/nueva-obra-costanera",
                "https://www.abcsaladillo.com.ar/general/reunion-fiestas-patrias",
            },
            {article_data["source_identity"] for article_data in accepted},
        )
        self.assertEqual(1, len(duplicates))
        self.assertEqual("duplicate", duplicates[0]["dedup_decision"])
        self.assertEqual(3, len(results))

    def test_update_keeps_existing_db_id_in_accepted_article(self):
        old_article = article(
            "Continúan las obras en la plaza",
            "La Municipalidad comenzó una obra nueva en la plaza central de Saladillo.",
            "https://www.abcsaladillo.com.ar/general/obras-plaza/",
            db_id=553,
            db_status="published",
        )
        processed_by_url = {
            "https://www.abcsaladillo.com.ar/general/obras-plaza": {
                "source_identity": "https://www.abcsaladillo.com.ar/general/obras-plaza",
                "content_hash": "hash-anterior",
                "title_norm": "continuan las obras en la plaza",
                "body_length": 75,
                "db_id": 553,
                "status": "published",
                "allow_retry": False,
            }
        }
        updated_article = article(
            "Continúan las obras en la plaza",
            "La Municipalidad comenzó una obra nueva en la plaza central de Saladillo. "
            "Además se instaló iluminación LED, rampas de accesibilidad y un nuevo sector de juegos, "
            "con una inversión provincial y la presencia de vecinos del barrio.",
            "https://www.abcsaladillo.com.ar/general/obras-plaza/",
        )

        accepted, duplicates, _ = classify_candidates([updated_article], processed_by_url, [])

        self.assertEqual([], duplicates)
        self.assertEqual(1, len(accepted))
        self.assertEqual("update", accepted[0]["dedup_decision"])
        self.assertEqual(553, accepted[0]["id"])
        self.assertEqual(553, accepted[0]["db_id"])


if __name__ == "__main__":
    unittest.main()
