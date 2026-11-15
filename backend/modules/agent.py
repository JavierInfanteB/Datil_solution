from flask import Blueprint, jsonify, request

from utils.agent_engine import AgentError, query_agent
from utils.decorators import require_auth

agent_bp = Blueprint("agent", __name__, url_prefix="/api/agent")

MAX_PROMPT = 2000   # caracteres por mensaje
MAX_HISTORY = 20    # mensajes previos de la conversacion


@agent_bp.route("/ask", methods=["POST"])
@require_auth
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

    try:
        reply = query_agent(prompt.strip(), history)
    except AgentError as e:
        return jsonify({"error": str(e)}), e.status
    return jsonify({"response": reply}), 200
