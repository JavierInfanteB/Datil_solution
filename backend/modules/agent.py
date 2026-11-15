import threading
import time
from collections import deque

from flask import Blueprint, jsonify, request

from utils.agent_engine import SATURADO, AgentError, query_agent
from utils.decorators import require_auth

agent_bp = Blueprint("agent", __name__, url_prefix="/api/agent")

# Uso libre, sin sesion: lo unico que protege la cuota de Gemini son estos limites.
MAX_PROMPT = 2000    # caracteres por mensaje
MAX_HISTORY = 20     # mensajes previos de la conversacion
WINDOW = 60          # segundos
MAX_PER_IP = 8       # mensajes por ventana de una misma direccion
MAX_GLOBAL = 6       # por proceso: con los 2 workers de gunicorn son 12 entre todos (el plan gratuito de Gemini da 15 por minuto)

# shortcut: contador en memoria de cada proceso (gunicorn corre 2 workers, por eso los topes van a la mitad);
# si se sube el numero de workers, bajar MAX_GLOBAL o pasar el contador a la base.
_lock = threading.Lock()
_recent = deque()    # (momento, ip) de los mensajes aceptados en la ventana


def _allow(ip: str) -> bool:
    now = time.monotonic()
    with _lock:
        while _recent and now - _recent[0][0] > WINDOW:
            _recent.popleft()
        if len(_recent) >= MAX_GLOBAL or sum(1 for _, other in _recent if other == ip) >= MAX_PER_IP:
            return False
        _recent.append((now, ip))
        return True


@agent_bp.route("/ask", methods=["POST"])
def ask():
    # Una cosa a la vez: sin sesion contesta sobre Datil; con sesion, sobre metricas de bonos y acciones.
    # Un token vencido o invalido da 401, como en el resto de la API.
    if request.headers.get("Authorization"):
        return require_auth(_answer)(True)
    return _answer(False)


def _answer(en_sesion):
    payload = request.get_json() or {}
    prompt = payload.get("prompt") if isinstance(payload, dict) else None
    if not isinstance(prompt, str) or not prompt.strip():
        return jsonify({"error": "Escribe una pregunta"}), 400
    if len(prompt) > MAX_PROMPT:
        return jsonify({"error": f"La pregunta no puede pasar de {MAX_PROMPT} caracteres"}), 413

    history = payload.get("history") or []
    if not isinstance(history, list) or len(history) > MAX_HISTORY:
        return jsonify({"error": "Historial de conversacion no valido"}), 400

    # Detras del tunel de Cloudflare la direccion real del visitante llega en CF-Connecting-IP.
    ip = request.headers.get("CF-Connecting-IP") or request.remote_addr or "?"
    if not _allow(ip):
        response = jsonify({"error": SATURADO})
        response.headers["Retry-After"] = str(WINDOW)
        return response, 429

    try:
        reply = query_agent(prompt.strip(), history, en_sesion)
    except AgentError as e:
        return jsonify({"error": str(e)}), e.status
    return jsonify({"response": reply}), 200
