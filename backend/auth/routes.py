"""Rutas de autenticacion: login, logout y verificacion de sesion."""
from flask import Blueprint, g, jsonify, request
from werkzeug.security import check_password_hash

from auth.jwt_handler import create_token, end_session, seconds_until_timeout
from db import accounts as accounts_repo
from utils.decorators import require_auth

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/login", methods=["POST"])
def login():
    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Usuario y contraseña son requeridos"}), 400

    user = accounts_repo.get_user(username=username)
    ip = request.remote_addr

    if user is None or not check_password_hash(user["password_hash"], password):
        accounts_repo.log_login_attempt(username, user["id"] if user else None, False, ip, "credenciales invalidas")
        return jsonify({"error": "Credenciales inválidas"}), 401

    if user.get("disabled"):
        accounts_repo.log_login_attempt(username, user["id"], False, ip, "cuenta suspendida")
        return jsonify({"error": "Cuenta suspendida. Contacta al administrador"}), 403

    token = create_token(user["id"], user["username"], user["role"])
    accounts_repo.log_login_attempt(username, user["id"], True, ip)
    return jsonify({
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "name": user["name"],
            "role": user["role"],
        },
    })


@auth_bp.route("/logout", methods=["POST"])
@require_auth
def logout():
    end_session(g.current_user["jti"])
    return jsonify({"message": "Sesión cerrada"})


@auth_bp.route("/verify", methods=["GET"])
@require_auth
def verify():
    return jsonify({
        "user": g.current_user,
        "seconds_until_timeout": seconds_until_timeout(g.current_user["jti"]),
    })
