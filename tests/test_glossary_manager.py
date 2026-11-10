import unittest
import tempfile
import json
from pathlib import Path

from utils.glossary_manager import GlossaryManager


class GlossaryManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.glossary_path = Path(self.temp_dir.name) / "test_glossary.json"
        initial_data = {
            "redaccion": {
                "Salomon": "Salomón",
                "hcd": "HCD"
            },
            "audio": {
                "CES": "C-E-S",
                "HCD": "Ache-Ce-De"
            },
            "ambos": {
                "saladillo vivo": "Saladillo Vivo"
            }
        }
        with open(self.glossary_path, "w", encoding="utf-8") as f:
            json.dump(initial_data, f, ensure_ascii=False)

        self.manager = GlossaryManager(self.glossary_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_apply_text_glossary(self):
        text = "El intendente Salomon fue al hcd y a saladillo vivo."
        result = self.manager.apply_text_glossary(text)
        self.assertIn("Salomón", result)
        self.assertIn("HCD", result)
        self.assertIn("Saladillo Vivo", result)
        # Asegurarse de que no aplica reglas exclusivas de audio
        self.assertNotIn("Ache-Ce-De", result)

    def test_apply_audio_glossary(self):
        text = "La CES y el HCD firmaron convenio con saladillo vivo."
        result = self.manager.apply_audio_glossary(text)
        self.assertIn("C-E-S", result)
        self.assertIn("Ache-Ce-De", result)
        self.assertIn("Saladillo Vivo", result)

    def test_add_and_remove_term(self):
        self.manager.add_term("nuevoError", "NuevaCorreccion", target="redaccion")
        res = self.manager.apply_text_glossary("Hay un nuevoError aquí.")
        self.assertIn("NuevaCorreccion", res)

        self.manager.remove_term("nuevoError", target="redaccion")
        res2 = self.manager.apply_text_glossary("Hay un nuevoError aquí.")
        self.assertIn("nuevoError", res2)

    def test_word_boundary_safety(self):
        # Asegurar que 'ces' no sustituya dentro de 'incesante'
        self.manager.add_term("ces", "CES", target="redaccion")
        res = self.manager.apply_text_glossary("Un reclamo incesante ante la ces.")
        self.assertIn("incesante", res)
        self.assertIn("la CES", res)


if __name__ == "__main__":
    unittest.main()
