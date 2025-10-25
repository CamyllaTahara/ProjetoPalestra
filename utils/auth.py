
from functools import wraps
from flask import session, redirect, url_for, flash

def login_required(tipo_usuario):
    """
    Decorador que garante que o usuário esteja logado e que o seu tipo 
    (tipo_usuario, ex: 'palestrante', 'administrador') seja o correto para acessar a rota.
    
    Acessa as chaves de sessão 'user_id' e 'user_type'.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. Verifica se as chaves da sessão existem
            if 'user_id' not in session or 'user_type' not in session:
                flash("Você precisa estar logado para acessar esta página.", "danger")
                # Redireciona para a rota de login do palestrante
                if tipo_usuario == "palestrante":
                    return redirect(url_for('login_palestrante.login_palestrante'))
                elif tipo_usuario == "instituicao":
                    return redirect(url_for('login_instituicao.login_instituicao'))
                elif tipo_usuario == "administrador":
                    return redirect(url_for('login_administrador.login_administrador'))
                else:
                    return redirect(url_for('login_palestrante.login_palestrante'))
            
            # 2. Verifica se o tipo de usuário logado corresponde ao tipo de usuário permitido na rota
            if session['user_type'] != tipo_usuario:
                flash("Acesso não autorizado. Tipo de usuário incorreto.", "danger")
                
                # Redireciona para o painel do tipo de usuário que está logado
                if session['user_type'] == "palestrante":
                    return redirect(url_for('login_palestrante.painel_palestrante'))
                elif session['user_type'] == "instituicao":
                    return redirect(url_for('login_instituicao.painel_instituicao'))
                elif session['user_type'] == "administrador":
                    return redirect(url_for('login_administrador.painel_administrador'))
                else:
                    return redirect(url_for('login_palestrante.login_palestrante'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def logout_user():
    """
    Limpa a sessão do usuário.
    """
    session.clear()