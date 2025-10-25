from functools import wraps
from flask import session, redirect, url_for, flash

def login_required(tipo_usuario):
    """
    Decorador que garante que o usuário esteja logado e que o seu tipo 
    (tipo_usuario, ex: 'palestrante', 'administrador') seja o correto para acessar a rota.
    
    Acessa as chaves de sessão 'user_id', 'user_type' e 'logged_in'.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. Verifica se o usuário está logado (checa todas as chaves necessárias)
            if not session.get('logged_in') or 'user_id' not in session or 'user_type' not in session:
                flash("Você precisa estar logado para acessar esta página.", "danger")
                # Redireciona para o login correspondente ao tipo de usuário esperado
                return redirect(url_for(f'login_{tipo_usuario}.login_{tipo_usuario}'))
            
            # 2. Verifica se o tipo de usuário logado corresponde ao tipo de usuário permitido na rota
            if session['user_type'] != tipo_usuario:
                flash("Acesso não autorizado.", "danger")
                
                # Tenta redirecionar para o painel do tipo de usuário que está logado
                try:
                    return redirect(url_for(f'login_{session["user_type"]}.painel_{session["user_type"]}'))
                except:
                    # Fallback seguro se o endpoint do painel for desconhecido
                    return redirect(url_for(f'login_{tipo_usuario}.login_{tipo_usuario}'))

            # 3. Tudo OK, executa a função decorada
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def logout_user():
    """
    Limpa a sessão do usuário.
    """
    session.clear()