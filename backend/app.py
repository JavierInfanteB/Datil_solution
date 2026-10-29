"""Punto de entrada de la API Datil Solutions."""
from flask import Flask, jsonify, request
from flask_cors import CORS

from config import Config, DEMO_READONLY
from routes import register_routes
from utils.seed import ensure_seed_data


def create_app():
    app = Flask(__name__, static_folder=Config.STATIC_DIR, static_url_path="")
    app.config.from_object(Config)
    CORS(app, origins=Config.CORS_ORIGINS, supports_credentials=True)
    ensure_seed_data()
    register_routes(app)

    if DEMO_READONLY:
        @app.before_request
        def block_writes():
            if request.method not in ("GET", "HEAD", "OPTIONS") and request.path not in ("/api/auth/login", "/api/auth/logout"):
                return jsonify({"error": "Modo de pruebas: solo lectura, no se pueden hacer cambios."}), 403

    # Endpoint raíz para verificar que el servidor está activo
    @app.route("/")
    def health_check():
        if Config.STATIC_DIR:
            return app.send_static_file("index.html")
        return jsonify({"message": "Datil Solutions API running", "status": "ok"}), 200
    
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
