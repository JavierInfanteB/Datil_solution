import logging
import os

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

from config import Config

log = logging.getLogger(__name__)

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_PATH = os.path.join(_BACKEND, "knowledge_base.md")     # sin sesion: quienes somos
METRICS_PATH = os.path.join(_BACKEND, "metricas.md")      # con sesion: metricas de bonos y acciones

SATURADO = ("Estamos recibiendo un alto volumen de solicitudes. "
            "En un momento le contestamos: intente de nuevo en un minuto.")

_COMUN = (
    "Answer in Spanish, clearly and professionally, in plain text without Markdown (no asterisks, no headings) "
    "and with correct Spanish accents even though the documentation is written without them. "
    "Use exclusively the information provided in the following documentation. "
    "Never give investment advice or recommendations: do not say what to buy, sell or hold, do not predict "
    "prices or returns, and do not compare which instrument is better. If asked for advice, say it naturally "
    "and in first person, along the lines of: \"Yo no puedo dar asesoría financiera; para eso están los "
    "consultores de Datil, con quienes se puede comunicar para ese fin.\" "
    "When a message mixes a request for advice with a question you can answer from the documentation, "
    "answer that question first and then add the note about the consultants. "
    "Mention the consultants only when the user actually asks for advice or a recommendation; otherwise never. "
    "Sound natural and conversational, and tie your answers to how the platform works. "
    "You have no access to the user's account or balances. "
)
_PUBLICO = (
    "You are the official assistant of Datil Solutions for visitors who have not signed in. "
    "Answer only questions about Datil Solutions itself: what it is, its instruments, roles and notifications. "
    + _COMUN +
    "If asked about metrics or how risk is measured, say that the assistant explains them after signing in. "
    "If a question cannot be answered using this context, state that the topic is under technical definition.\n\n"
)
_SESION = (
    "You are the official assistant of Datil Solutions for signed-in users. "
    "Answer only questions about the bond and stock metrics shown on the platform and how they are measured. "
    + _COMUN +
    "Signed-in users write to their consultant from the menu Mi plan, section Notas para mi consultor. "
    "If a question cannot be answered using this context, state that the topic is under technical definition.\n\n"
)


class AgentError(Exception):
    """Falla del agente con un mensaje apto para el usuario; el detalle interno solo va al log."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def get_knowledge_base(en_sesion: bool = False) -> str:
    # Sin documentacion el modelo improvisaria: mejor no contestar.
    path = METRICS_PATH if en_sesion else KB_PATH
    try:
        with open(path, "r", encoding="utf-8") as file:
            return file.read()
    except OSError:
        log.exception("No se pudo leer %s", path)
        raise AgentError(503, "El asistente no esta disponible por ahora.")


def query_agent(prompt: str, history: list = None, en_sesion: bool = False) -> str:
    """Una sola cosa a la vez: sin sesion contesta sobre Datil; con sesion, sobre metricas de bonos y acciones."""
    api_key = Config.GEMINI_API_KEY
    if not api_key:
        log.error("Falta la clave de Gemini (variable de entorno IA_DATIL)")
        raise AgentError(503, "El asistente no esta disponible por ahora.")

    knowledge_base = get_knowledge_base(en_sesion)
    genai.configure(api_key=api_key)

    system_instruction = (_SESION if en_sesion else _PUBLICO) + f"Documentation:\n{knowledge_base}"

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
