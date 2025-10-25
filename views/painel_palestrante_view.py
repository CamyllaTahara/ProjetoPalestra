from flask import Blueprint, render_template, session, redirect, url_for
from utils.security import login_required
painel_palestrante_bp = Blueprint("painel_palestrante", __name__)

@painel_palestrante_bp.route("/painel")
@login_required("palestrante")
def painel_palestrante():
    usuario = usuario
    return render_template("painel_palestrante.html", usuario=usuario)

@painel_palestrante_bp.route("/logout/palestrante")
def logout_palestrante():
    """Rota para fazer logout do administrador."""
    return login_required("login_palestrante.html")


