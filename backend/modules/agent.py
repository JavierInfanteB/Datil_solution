import threading
import time
from collections import deque

from flask import Blueprint, jsonify, request

from utils.agent_engine import SATURADO, AgentError, query_agent

agent_bp = Blueprint("agent", __name__, url_prefix="/api/agent")

# Uso libre, sin sesion: lo unico que protege la cuota de Gemini son estos limites.
MAX_PROMPT = 2000    # caracteres por mensaje
MAX_HISTORY = 20     # mensajes previos de la conversacion
WINDOW = 60          # segundos
MAX_PER_IP = 8       # mensajes por ventana de una misma direccion
MAX_GLOBAL = 30      # mensajes por ventana entre todos

# shortcut: contador en memoria, vale con un solo proceso (gunicorn --workers 1); con mas workers pasar a Redis.
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
        reply = query_agent(prompt.strip(), history)
    except AgentError as e:
        return jsonify({"error": str(e)}), e.status
    return jsonify({"response": reply}), 200
