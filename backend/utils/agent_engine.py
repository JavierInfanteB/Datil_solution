import logging
import os

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

from config import Config

log = logging.getLogger(__name__)

KB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge_base.md")


SATURADO = ("Estamos recibiendo un alto volumen de solicitudes. "
            "En un momento le contestamos: intente de nuevo en un minuto.")


class AgentError(Exception):
    """Falla del agente con un mensaje apto para el usuario; el detalle interno solo va al log."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def get_knowledge_base() -> str:
    # Sin documentacion el modelo improvisaria: mejor no contestar.
    try:
        with open(KB_PATH, "r", encoding="utf-8") as file:
            return file.read()
    except OSError:
        log.exception("No se pudo leer %s", KB_PATH)
        raise AgentError(503, "El asistente no esta disponible por ahora.")


def query_agent(prompt: str, history: list = None) -> str:
    api_key = Config.GEMINI_API_KEY
    if not api_key:
        log.error("Falta la clave de Gemini (variable de entorno IA_DATIL)")
        raise AgentError(503, "El asistente no esta disponible por ahora.")

    knowledge_base = get_knowledge_base()
    genai.configure(api_key=api_key)

    system_instruction = (
        "You are the official corporate and technical assistant for Datil Solutions. "
        "Answer questions in Spanish, clearly and professionally. "
        "Use exclusively the information provided in the following documentation. "
        "If a question cannot be answered using this context, state that the topic "
        "is under technical definition.\n\n"
        f"Documentation:\n{knowledge_base}"
    )

    try:
        model = genai.GenerativeModel(
            model_name="gemini-3.5-flash-lite",
            system_instruction=system_instruction,
            generation_config={
                "temperature": 0.2,
                "max_output_tokens": 800,
            }
        )

        chat = model.start_chat(history=history or [])
        response = chat.send_message(prompt)
        return response.text

    except ResourceExhausted:
        log.exception("Cuota de Gemini agotada")
        raise AgentError(429, SATURADO)
    except Exception:
        # Incluye errores de la API y respuestas bloqueadas (ValueError al leer .text).
        log.exception("Fallo la consulta a Gemini")
        raise AgentError(502, "El asistente no pudo responder. Intenta de nuevo.")
