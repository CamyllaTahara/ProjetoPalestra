from flask import Flask
# Importações de views de entidades (instituicao e palestrante)
from views.instituicao_views import instituicao_bp
from views.palestrante_views import palestrante_bp
from views.administrador_views import administrador_bp

# Importações de views de login (usando o nome correto do blueprint)
# O blueprint 'login_administrador_bp' é o que está definido no arquivo 'views.login_administrador_views'
from views.login_administrador_views import login_administrador_bp 
from views.login_instituicao_views import login_instituicao_bp
from views.login_palestrante_views import login_palestrante_bp

from views.gerenciar_instituicao_view import gerenciar_instituicoes_bp
from views.gerenciar_palestrante_views import gerenciar_palestrantes_bp

# Importações dos painéis de controle
from views.painel_administrador_view import painel_administrador_bp
from views.painel_palestrante_view import painel_palestrante_bp
from views.painel_instituicao_view import painel_instituicao_bp

from views.gerenciar_disponibilidades import gerenciar_disponibilidades_bp
from views.gerenciar_solicitacoes import gerenciar_solicitacoes_bp

app = Flask(__name__)
app.secret_key = 'segredo123' 

# -----------------------------------------------------------------
# Registro dos Blueprints
# -----------------------------------------------------------------

# Views principais (CRUDs ou páginas sem login específico)
app.register_blueprint(instituicao_bp)
app.register_blueprint(palestrante_bp)
app.register_blueprint(administrador_bp)
# Views de Autenticação/Login
app.register_blueprint(login_instituicao_bp)
app.register_blueprint(login_palestrante_bp)
app.register_blueprint(login_administrador_bp) # CORRIGIDO: Usa o nome correto

# Views de Painel
app.register_blueprint(painel_instituicao_bp)
app.register_blueprint(painel_palestrante_bp)
app.register_blueprint(painel_administrador_bp)

app.register_blueprint(gerenciar_instituicoes_bp)
app.register_blueprint(gerenciar_palestrantes_bp)

app.register_blueprint(gerenciar_disponibilidades_bp)
app.register_blueprint(gerenciar_solicitacoes_bp)
if __name__ == '__main__':
    app.run(debug=True)
