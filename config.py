# config.py
import os
from datetime import timedelta
from utils.mail import initialize_mail_utility

# Configurações gerais
SECRET_KEY = os.environ.get('SECRET_KEY') or 'segredo123'
# Corrigido: Usando a chave correta para o Flask (app.secret_key)
# Chave de segurança, não precisa mais do dictionary SECURITY_CONFIG aqui.

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'palestra'
}

# CORRIGIDO: CHAVES DE E-MAIL MOVIDAS PARA O NÍVEL SUPERIOR
# O Flask espera as chaves assim quando usa from_object()
MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'camytahara@gmail.com'  # Substitua com seu e-mail real
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'gdri anzw qppc hzaq'  # Substitua com sua senha de app
MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'camytahara@gmail.com'  # Substitua com seu e-mail real

# Configurações de segurança
PASSWORD_SALT = os.environ.get('PASSWORD_SALT') or 'sal_seguro_para_senhas'
TOKEN_EXPIRATION = timedelta(hours=1) 