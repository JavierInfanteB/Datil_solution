from flask import Blueprint, jsonify, request
from utils.agent_engine import query_agent

agent_bp = Blueprint("agent", __name__, url_prefix="/api/agent")

@agent_bp.route("/ask", methods=["POST"])
def ask():
    payload = request.get_json() or {}
    user_prompt = payload.get("prompt", "").strip()

    if not user_prompt:
        return jsonify({"error": "Prompt cannot be empty"}), 400

    reply = query_agent(user_prompt)
    return jsonify({"response": reply}), 200