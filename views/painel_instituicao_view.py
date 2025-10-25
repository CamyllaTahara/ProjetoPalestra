from flask import Blueprint, render_template
from utils.security import login_required
painel_instituicao_bp = Blueprint("painel_instituicao", __name__)

@painel_instituicao_bp.route("/painel")
@login_required("instituicao")
def painel_instituicao():
    usuario = usuario
    return render_template("painel_instituicao.html", usuario=usuario)
