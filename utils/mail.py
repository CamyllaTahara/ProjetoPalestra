# utils/mail.py - Módulo de utilitário de e-mail (SOLUÇÃO DEFINITIVA)
from flask_mail import Mail, Message
from flask import current_app
# utils/mail.py (Assumindo que está mais ou menos assim)



# Variável global para armazenar a instância do cliente de e-mail do Flask-Mail.
mail_client = Mail() 

def initialize_mail_utility(app):

    """
    Inicializa o módulo de email injetando a instância principal do aplicativo (app)
    e vinculando o cliente Flask-Mail usando init_app.
    """
    global mail_client
    
    print("\n" + "="*60)
    print("🔧 INICIANDO CONFIGURAÇÃO DO MAIL")
    print("="*60)
    
    # Debug: Verificar se as configurações estão presentes
    print(f"📧 MAIL_SERVER: {app.config.get('MAIL_SERVER')}")
    print(f"📧 MAIL_PORT: {app.config.get('MAIL_PORT')}")
    print(f"📧 MAIL_USE_TLS: {app.config.get('MAIL_USE_TLS')}")
    print(f"📧 MAIL_USERNAME: {app.config.get('MAIL_USERNAME')}")
    print(f"📧 MAIL_PASSWORD: {'***' if app.config.get('MAIL_PASSWORD') else 'NÃO CONFIGURADO'}")
    
    try:
        # Vincula o cliente de e-mail do Flask à instância do app
        mail_client.init_app(app)
        
        # CORREÇÃO: Verificar dentro de um contexto de aplicação
        with app.app_context():
            # Agora o mail_client deve estar vinculado
            print(f"✅ Flask-Mail inicializado corretamente")
        
        print("-> Cliente Flask-Mail Inicializado e vinculado com sucesso.")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"❌ ERRO DE INICIALIZAÇÃO DO MAIL: {e}")
        print("="*60 + "\n")
        raise e

# utils/mail.py

# ... (seu código initialize_mail_utility) ...

def send_notification_email(recipient, subject, body, is_html=False): # ⬅️ ADICIONAR is_html=False
    """
    Envia um email de notificação usando Flask-Mail.
    
    Se is_html for True, o 'body' é tratado como corpo HTML.
    """
    global mail_client
    
    print("\n" + "-"*60)
    print("📤 TENTANDO ENVIAR E-MAIL")
    print("-"*60)
    print(f"Para: {recipient}")
    print(f"Assunto: {subject}")

    try:
        sender_email = current_app.config.get('MAIL_USERNAME')
        
        # ... (validações) ...
        
        # Cria a mensagem
        msg = Message(
            subject,
            recipients=[recipient],
            sender=sender_email
        )
        
        # 🟢 CORREÇÃO: Usa 'is_html' para decidir qual campo preencher.
        if is_html:
            msg.html = body # Define o corpo como HTML
        else:
            msg.body = body  # Define o corpo como texto plano
        
        print(f"Tipo de corpo: {'HTML' if is_html else 'TEXTO'}")
        print("📧 Mensagem criada, enviando...")
        
        # Envia a mensagem
        mail_client.send(msg)
        
        # ... (Log de sucesso) ...
        
        return True

    except Exception as e:
        # ... (Log de erro) ...
        return False