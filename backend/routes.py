"""Registro central de blueprints. Agregar un modulo nuevo = una linea aqui."""
from auth.routes import auth_bp
from modules.history import history_bp
from modules.permissions import permissions_bp
from modules.portfolio import portfolio_bp
from modules.risk import risk_bp
from modules.trading import trading_bp


def register_routes(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(portfolio_bp)
    app.register_blueprint(trading_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(risk_bp)
    app.register_blueprint(permissions_bp)
