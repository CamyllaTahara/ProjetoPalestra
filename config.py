# config.py
import os
from datetime import timedelta

# Configurações gerais
SECRET_KEY = os.environ.get('SECRET_KEY') or 'segredo123'



DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'palestra'
}

EMAIL_CONFIG = {
    'MAIL_SERVER': 'smtp.gmail.com',
    'MAIL_PORT': 587,
    'MAIL_USE_TLS': True,
    'MAIL_USERNAME': os.environ.get('MAIL_USERNAME') or 'camytahara@gmail.com',  # Substitua com seu e-mail real
    'MAIL_PASSWORD': os.environ.get('MAIL_PASSWORD') or 'miqr fggg v unn iwnl',  # Substitua com sua senha de app
    'MAIL_DEFAULT_SENDER': os.environ.get('MAIL_DEFAULT_SENDER') or 'camytahara@gmail.com'  # Substitua com seu e-mail real
}

# Configurações de segurança
SECURITY_CONFIG = {
    'PASSWORD_SALT': os.environ.get('PASSWORD_SALT') or 'sal_seguro_para_senhas',
    'TOKEN_EXPIRATION': timedelta(hours=1)  # Tokens expiram em 1 hora
}     