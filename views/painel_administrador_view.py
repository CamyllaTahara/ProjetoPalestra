from flask import Blueprint, render_template, session, redirect, url_for
from utils.security import login_required
painel_administrador_bp = Blueprint("painel_administrador", __name__)

@painel_administrador_bp.route("/painel")
@login_required("administrador")
def painel_administrador():
    usuario = usuario
    return render_template("painel_administrador.html", usuario=usuario)

@painel_administrador_bp.route("/logout/administrador")
def logout_administrador():
    """Rota para fazer logout do administrador."""
    return login_required("login_administrador.html")



