# -*- coding: utf-8 -*-
"""
agents/flow_workflow_builder.py — Generador de Grafos Workflow JSON para Flow Automation
========================================================================================
Construye la especificación estructurada en formato JSON compatible con el editor
'Workflow' de Flow Automation para Google Flow.

Arquitectura del Grafo:
1. Nodo [Upload image]: Carga la imagen local de la locación temática.
2. Nodo [Enter prompt]: Inyecta el prompt inicial para situar a Ara en el entorno.
3. Nodo [Generate Image]: Crea el fotograma maestro inicial con Ara en la locación.
4. Nodos [Generate Video] Encadenados:
   - Video 1: Toma el fotograma maestro de la imagen generada.
   - Video N: Conecta el puerto 'last frame' del video N-1 a la entrada de video N.
   - Cada nodo de video contiene el prompt del bloque de 8 segundos con la mención a 'Ara'.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("FlowWorkflowBuilder")

CHARACTER_NAME = "Ara"


class FlowWorkflowBuilder:
    """
    Ensamblador de grafos de Workflow JSON para Flow Automation (Google Flow).
    """

    def __init__(self, character_name: str = CHARACTER_NAME):
        self.character_name = character_name

    def build_workflow(
        self,
        article_id: int,
        bloques: List[str],
        location_image_path: Optional[str] = None,
        aspect_ratio: str = "9:16"
    ) -> Dict[str, Any]:
        """
        Construye el grafo JSON del workflow completo con encadenamiento 'last frame'.
        """
        nodes = []
        links = []
        node_id_counter = 1

        # 1. Nodo: Upload image (Locación de fondo)
        upload_node_id = node_id_counter
        node_id_counter += 1
        nodes.append({
            "id": upload_node_id,
            "type": "UploadImage",
            "title": "Locación de Fondo",
            "pos": [100, 200],
            "size": {"width": 260, "height": 180},
            "properties": {
                "image_path": location_image_path or "",
                "description": "Fondo temático local de Saladillo Vivo"
            },
            "outputs": [
                {"name": "image", "type": "image", "links": [1]}
            ]
        })

        # 2. Nodo: Enter prompt (Hero Frame Inicial)
        prompt_image_node_id = node_id_counter
        node_id_counter += 1
        hero_prompt = (
            f"Retrato cinematográfico de {self.character_name}, presentadora de noticias, "
            f"mirando a cámara con postura profesional en este escenario, plano medio vertical, "
            f"iluminación de estudio de televisión, máxima nitidez, 9:16."
        )
        nodes.append({
            "id": prompt_image_node_id,
            "type": "EnterPrompt",
            "title": f"Prompt Fotograma Ara ({self.character_name})",
            "pos": [100, 420],
            "size": {"width": 280, "height": 160},
            "properties": {
                "text": hero_prompt,
                "character": self.character_name
            },
            "outputs": [
                {"name": "prompt", "type": "string", "links": [2]}
            ]
        })

        # 3. Nodo: Generate Image (Combina Ara + Locación)
        gen_image_node_id = node_id_counter
        node_id_counter += 1
        nodes.append({
            "id": gen_image_node_id,
            "type": "GenerateImage",
            "title": f"Generar Fotograma Maestro ({self.character_name})",
            "pos": [450, 300],
            "size": {"width": 280, "height": 220},
            "properties": {
                "character": self.character_name,
                "model": "Nano Banana 2.1",
                "aspect_ratio": aspect_ratio,
                "auto_add_character": True
            },
            "inputs": [
                {"name": "image_input", "type": "image", "link": 1},
                {"name": "prompt_input", "type": "string", "link": 2}
            ],
            "outputs": [
                {"name": "image_output", "type": "image", "links": [3]}
            ]
        })

        links.append({"id": 1, "from_node": upload_node_id, "from_port": "image", "to_node": gen_image_node_id, "to_port": "image_input"})
        links.append({"id": 2, "from_node": prompt_image_node_id, "from_port": "prompt", "to_node": gen_image_node_id, "to_port": "prompt_input"})

        # 4. Nodos Generate Video encadenados vía 'last frame'
        prev_video_node_id = None
        link_id_counter = 4
        x_offset = 800

        for idx, bloque_texto in enumerate(bloques, start=1):
            video_node_id = node_id_counter
            node_id_counter += 1

            video_prompt = (
                f"{self.character_name} hablando a cámara con dicción natural: \"{bloque_texto}\". "
                f"Gesto sobrio y profesional de presentadora de noticias, plano vertical 9:16."
            )

            is_first = (idx == 1)
            video_node = {
                "id": video_node_id,
                "type": "GenerateVideo",
                "title": f"Bloque {idx} (8s) - {self.character_name}",
                "pos": [x_offset + (idx - 1) * 360, 300],
                "size": {"width": 320, "height": 260},
                "properties": {
                    "character": self.character_name,
                    "model": "Veo 3.1",
                    "duration": "8s",
                    "prompt": video_prompt,
                    "auto_add_character": True,
                    "auto_add_voice_by_speaker": True,
                    "save_name": f"{str(idx).zfill(2)}_prompt.mp4"
                },
                "inputs": [],
                "outputs": [
                    {"name": "video_output", "type": "video", "links": []},
                    {"name": "last_frame", "type": "image", "links": []}
                ]
            }

            if is_first:
                # El primer video se alimenta del fotograma maestro de Generate Image
                video_node["inputs"].append({
                    "name": "initial_frame",
                    "type": "image",
                    "link": 3
                })
                links.append({
                    "id": 3,
                    "from_node": gen_image_node_id,
                    "from_port": "image_output",
                    "to_node": video_node_id,
                    "to_port": "initial_frame"
                })
            else:
                # Los videos subsiguientes toman el 'last_frame' del video anterior
                cur_link = link_id_counter
                link_id_counter += 1
                video_node["inputs"].append({
                    "name": "last_frame_input",
                    "type": "image",
                    "link": cur_link
                })
                # Añadir link saliente en el nodo previo
                for out in nodes[-1]["outputs"]:
                    if out["name"] == "last_frame":
                        out["links"].append(cur_link)

                links.append({
                    "id": cur_link,
                    "from_node": prev_video_node_id,
                    "from_port": "last_frame",
                    "to_node": video_node_id,
                    "to_port": "last_frame_input"
                })

            nodes.append(video_node)
            prev_video_node_id = video_node_id

        workflow_data = {
            "metadata": {
                "article_id": article_id,
                "character": self.character_name,
                "aspect_ratio": aspect_ratio,
                "total_blocks": len(bloques),
                "total_duration_sec": len(bloques) * 8,
                "generator": "Saladillo Vivo Video Factory v1.0"
            },
            "workflow": {
                "nodes": nodes,
                "links": links
            }
        }
        return workflow_data

    def export_workflow_json(self, workflow_data: Dict[str, Any], filepath: str) -> str:
        """Exporta el grafo estructurado a un archivo .json."""
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(workflow_data, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ Workflow JSON guardado en: {filepath}")
        return filepath

    def export_concat_txt(self, bloques: List[str], filepath: str) -> str:
        """Exporta el formato alternativo de texto plano para cola rápida (8s concat)."""
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        prompts = []
        for idx, b in enumerate(bloques, start=1):
            prompt = (
                f"{self.character_name} mirando a cámara en estudio de noticias: \"{b}\". "
                f"Gesto natural y sereno, plano medio vertical 9:16."
            )
            prompts.append(prompt)

        contenido = "\n\n".join(prompts)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(contenido)
        logger.info(f"✅ Archivo TXT de prompts guardado en: {filepath}")
        return filepath


if __name__ == "__main__":
    builder = FlowWorkflowBuilder()
    demo_bloques = [
        "Saladillo suma nuevas obras viales con la repavimentación integral de sus accesos principales.",
        "Los trabajos comenzaron esta mañana sobre la avenida Frocham para agilizar el tránsito en la ciudad.",
        "El intendente destacó que la inversión es municipal y beneficiará a cientos de vecinos de la zona."
    ]
    wf = builder.build_workflow(
        article_id=999,
        bloques=demo_bloques,
        location_image_path="assets/locaciones/municipales/foto1.jpg"
    )
    builder.export_workflow_json(wf, "data/demo_workflow.json")
    builder.export_concat_txt(demo_bloques, "data/demo_prompts.txt")
