from functools import wraps
import os

import eventlet
eventlet.monkey_patch()  

from flask import Flask, redirect, request, session, url_for

# ============================================================
# PASSO 1: CRIAR A APLICAÇÃO
# ============================================================
app = Flask(__name__)

# ============================================================
# PASSO 2: CARREGAR CONFIGURAÇÕES (ANTES DE TUDO!)
# ============================================================
# Importante: Isso deve vir ANTES de qualquer inicialização
app.config.from_object('config')

# Verificação das configurações carregadas
print("\n" + "="*60)
print("⚙️  CONFIGURAÇÕES CARREGADAS")
print("="*60)
print(f"SECRET_KEY: {'***' if app.config.get('SECRET_KEY') else '❌ NÃO CONFIGURADO'}")
print(f"MAIL_SERVER: {app.config.get('MAIL_SERVER')}")
print(f"MAIL_PORT: {app.config.get('MAIL_PORT')}")
print(f"MAIL_USE_TLS: {app.config.get('MAIL_USE_TLS')}")
print(f"MAIL_USERNAME: {app.config.get('MAIL_USERNAME')}")
print(f"MAIL_PASSWORD: {'***' if app.config.get('MAIL_PASSWORD') else '❌ NÃO CONFIGURADO'}")
print("="*60 + "\n")

# ============================================================
# PASSO 3: INICIALIZAR MÓDULO DE E-MAIL (APÓS AS CONFIGS!)
# ============================================================
from utils.mail import initialize_mail_utility

# Esta linha é CRÍTICA - sem ela, o mail não funciona
initialize_mail_utility(app)

from flask_socketio import SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# ============================================================
# PASSO 4: IMPORTAR E REGISTRAR BLUEPRINTS
# ============================================================

# Importações de views de entidades
from views.instituicao_views import instituicao_bp
from views.palestrante_views import palestrante_bp
from views.administrador_views import administrador_bp

# Importações de views de login
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
from views.gerenciar_palestras_confirmadas import gerenciar_palestras_bp
from views.chamados_views import chamados_bp
app.register_blueprint(chamados_bp)
from views.chat_views import chat_bp, init_socketio
app.register_blueprint(chat_bp)
init_socketio(socketio) 
# Registro dos Blueprints
print("📦 Registrando Blueprints...")

app.register_blueprint(instituicao_bp)
app.register_blueprint(palestrante_bp)
app.register_blueprint(administrador_bp)

# Views de Autenticação/Login
app.register_blueprint(login_instituicao_bp)
app.register_blueprint(login_palestrante_bp)
app.register_blueprint(login_administrador_bp)

# Views de Painel
app.register_blueprint(painel_instituicao_bp)
app.register_blueprint(painel_palestrante_bp)
app.register_blueprint(painel_administrador_bp)

app.register_blueprint(gerenciar_instituicoes_bp)
app.register_blueprint(gerenciar_palestrantes_bp)

app.register_blueprint(gerenciar_disponibilidades_bp)
app.register_blueprint(gerenciar_solicitacoes_bp)
app.register_blueprint(gerenciar_palestras_bp)

from views.feed_views import feed_bp
app.register_blueprint(feed_bp)

from flask import send_from_directory

@app.route('/uploads_feed/<filename>')
def uploads_feed(filename):
  return send_from_directory(os.path.join(app.root_path, 'uploads_feed'), filename)

from views.feed_views import destacar_mencoes
app.jinja_env.filters['mencoes'] = destacar_mencoes


print("✅ Todos os Blueprints registrados\n")

# ============================================================
# ROTA DE TESTE (OPCIONAL - REMOVA DEPOIS)
# ============================================================
@app.route('/teste-mail-debug')
def teste_mail_debug():
    """Rota para testar se o mail está configurado corretamente"""
    from utils.mail import send_notification_email
    from flask import current_app
    
    html = "<h1>🧪 Debug de Configuração de E-mail</h1>"
    html += "<h2>Configurações do Flask:</h2><ul>"
    html += f"<li><strong>MAIL_SERVER:</strong> {current_app.config.get('MAIL_SERVER')}</li>"
    html += f"<li><strong>MAIL_PORT:</strong> {current_app.config.get('MAIL_PORT')}</li>"
    html += f"<li><strong>MAIL_USE_TLS:</strong> {current_app.config.get('MAIL_USE_TLS')}</li>"
    html += f"<li><strong>MAIL_USERNAME:</strong> {current_app.config.get('MAIL_USERNAME')}</li>"
    html += f"<li><strong>MAIL_PASSWORD:</strong> {'Configurado ✅' if current_app.config.get('MAIL_PASSWORD') else 'NÃO configurado ❌'}</li>"
    html += "</ul>"
    
    # Tentar enviar um e-mail de teste
    html += "<h2>🚀 Teste de Envio Real:</h2>"
    html += "<p><em>Enviando e-mail de teste para o próprio endereço configurado...</em></p>"
    
    try:
        print("\n" + "="*60)
        print("🧪 TESTE DE E-MAIL INICIADO (via rota /teste-mail-debug)")
        print("="*60)
        
        resultado = send_notification_email(
            recipient=current_app.config.get('MAIL_USERNAME'),  # Envia para o próprio e-mail
            subject='🧪 Teste de Configuração - Sistema de Palestras',
            body='''Este é um e-mail de teste do sistema de agendamento de palestras.

Se você recebeu este e-mail, significa que:
✅ As configurações do Flask-Mail estão corretas
✅ O servidor SMTP está acessível
✅ As credenciais estão válidas

Você pode ignorar este e-mail.'''
        )
        
        if resultado:
            html += "<div style='background: #d4edda; border: 1px solid #c3e6cb; padding: 15px; border-radius: 5px;'>"
            html += "<h3 style='color: #155724; margin: 0;'>✅ E-mail enviado com sucesso!</h3>"
            html += "<p style='color: #155724;'>Verifique sua caixa de entrada (ou spam) em: <strong>" + current_app.config.get('MAIL_USERNAME') + "</strong></p>"
            html += "</div>"
        else:
            html += "<div style='background: #f8d7da; border: 1px solid #f5c6cb; padding: 15px; border-radius: 5px;'>"
            html += "<h3 style='color: #721c24; margin: 0;'>❌ Falha ao enviar e-mail</h3>"
            html += "<p style='color: #721c24;'>Verifique os logs no terminal para mais detalhes.</p>"
            html += "</div>"
            
    except Exception as e:
        html += "<div style='background: #f8d7da; border: 1px solid #f5c6cb; padding: 15px; border-radius: 5px;'>"
        html += f"<h3 style='color: #721c24; margin: 0;'>❌ Erro ao enviar: {e}</h3>"
        html += f"<p style='color: #721c24;'>Tipo: {type(e).__name__}</p>"
        html += "</div>"
    
    html += "<hr><p><a href='/'>← Voltar</a></p>"
    
    return html

# ============================================================
# INICIAR APLICAÇÃO
# ============================================================
if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 INICIANDO SERVIDOR FLASK")
    print("="*60)
    print("Acesse: http://127.0.0.1:5000")
    print("Teste de mail: http://127.0.0.1:5000/teste-mail-debug")
    print("="*60 + "\n")
    
    app.run(debug=True)

def login_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # --- PRINTS DE DEBUG ---
            print("\n--- TESTE DE ACESSO ---")
            print(f"Rota acessada: {request.path}")
            print(f"Role exigida pela rota: {role}")
            print(f"O que tem na session['user_id']: {session.get('user_id')}")
            print(f"O que tem na session['user_type']: {session.get('user_type')}")
            
            if 'user_id' not in session:
                print("RESULTADO: Bloqueado (Usuário não logado)")
                return redirect(url_for('auth.login'))
            
            if session.get('user_type') != role:
                print(f"RESULTADO: Bloqueado (Tipo {session.get('user_type')} tentou entrar em rota de {role})")
                return redirect(url_for('feed.meu_perfil_pal')) 
            
            print("RESULTADO: Acesso Permitido!")
            return f(*args, **kwargs)
        return decorated_function
    return decorator