"""Punto de entrada de la API Datil Solutions."""
from flask import Flask
from flask_cors import CORS

from config import Config
from routes import register_routes
from utils.seed import ensure_seed_data


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app, origins=Config.CORS_ORIGINS, supports_credentials=True)
    ensure_seed_data()
    register_routes(app)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
