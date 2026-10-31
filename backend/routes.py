"""Registro central de blueprints. Agregar un modulo nuevo = una linea aqui."""
from modules.admin import admin_bp
from auth.routes import auth_bp
from modules.consultant import consultant_bp
from modules.history import history_bp
from modules.notifications import notifications_bp
from modules.permissions import permissions_bp
from modules.plan import plan_bp
from modules.portfolio import portfolio_bp
from modules.risk import risk_bp
from modules.trading import trading_bp
from modules.users import users_bp


def register_routes(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(portfolio_bp)
    app.register_blueprint(trading_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(risk_bp)
    app.register_blueprint(permissions_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(plan_bp)
    app.register_blueprint(consultant_bp)
    app.register_blueprint(notifications_bp)
