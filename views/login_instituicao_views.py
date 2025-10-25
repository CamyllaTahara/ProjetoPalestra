from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import re
# ATENÇÃO: Verifique se 'conectar_bd' está realmente em models.instituicao
from models.instituicao import conectar_bd 
import mysql.connector
import os 
import secrets
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import urllib.parse
from utils.security import  login_required, logout_user
#from utils.auth import login_required, logout_user


# CORREÇÃO CRÍTICA: Removendo o url_prefix que estava causando o erro 404
# A rota agora será acessada diretamente pelo nome.
login_instituicao_bp = Blueprint('login_instituicao', __name__) 

def cnpj_valido(cnpj):
    """Verifica a validade básica do CNPJ (14 dígitos)."""
    cnpj = ''.join(filter(str.isdigit, cnpj))
    # CNPJ tem 14 dígitos.
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    return True

def validar_telefone(telefone):
    telefone = ''.join(filter(str.isdigit, telefone))
    return len(telefone) in (10, 11)

def validar_email(email):
    return '@' in email and '.' in email

def validar_senha(senha):
    """Verifica se a senha atende aos requisitos de segurança."""
    if len(senha) < 8:
        return False, "A senha deve ter pelo menos 8 caracteres."
    if not re.search(r'[!@#$%&*]', senha):
        return False, "A senha deve conter pelo menos um caractere especial (!@#$%&*)."
    if not any(c.isupper() for c in senha):
        return False, "A senha deve conter pelo menos uma letra maiúscula."
    if not any(c.islower() for c in senha):
        return False, "A senha deve conter pelo menos uma letra minúscula."
    if not any(c.isdigit() for c in senha):
        return False, "A senha deve conter pelo menos um número."
    return True, ""

def enviar_email_recuperacao(email, token):
    """Envia um e-mail com o link de recuperação de senha."""
    try:
        remetente_email = "camytahara@gmail.com"
        remetente_senha = "miqr fggg v unn iwnl"
        
        # O link agora usa o endpoint completo: 'login_instituicao.reset_senha'
        link_recuperacao = url_for('login_instituicao.reset_senha', 
                                   token=token, 
                                   _external=True)
        
        # Corpo do email HTML
        corpo_email = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4CAF50; color: white; padding: 10px; text-align: center; }}
                .content {{ padding: 20px; }}
                .button {{ background-color: #4CAF50; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>Recuperação de Senha</h2>
                </div>
                <div class="content">
                    <p>Olá,</p>
                    <p>Recebemos uma solicitação para redefinir sua senha. Se você não fez esta solicitação, ignore este e-mail.</p>
                    <p>Para redefinir sua senha, clique no botão abaixo:</p>
                    <p style="text-align: center;">
                        <a href="{link_recuperacao}" class="button">Redefinir Senha</a>
                    </p>
                    <p>Ou copie e cole o seguinte link no seu navegador:</p>
                    <p>{link_recuperacao}</p>
                    <p>Este link é válido por 1 hora.</p>
                    <p>Atenciosamente,<br>Equipe de Suporte</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        mensagem = MIMEMultipart()
        mensagem['From'] = remetente_email
        mensagem['To'] = email
        mensagem['Subject'] = "Recuperação de Senha - Sistema de Palestras"
        mensagem.attach(MIMEText(corpo_email, 'html'))
        
        servidor = smtplib.SMTP('smtp.gmail.com', 587)
        servidor.starttls()
        servidor.login(remetente_email, remetente_senha)
        
        texto = mensagem.as_string()
        servidor.sendmail(remetente_email, email, texto)
        servidor.quit()
        
        return True
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        return False

# ROTA DE LOGIN
@login_instituicao_bp.route('/login_instituicao', methods=['GET', 'POST'])
def login_instituicao():
    mensagem_erro = None
    mensagem_sucesso = request.args.get('mensagem_sucesso')
    
    if request.method == 'POST':
        # Corrigido: Lendo 'cnpj' do formulário
        cnpj = request.form.get('cnpj') 
        senha = request.form.get('senha')
        
        if not cnpj or not senha:
            mensagem_erro = "Por favor, preencha o CNPJ e a senha."
            return render_template('login_instituicao.html', mensagem_erro=mensagem_erro)

        try:
            conexao = conectar_bd()
            cursor = conexao.cursor(dictionary=True)
            
            # Corrigido: Buscando o usuário pelo CNPJ
            cursor.execute("SELECT id, nome, senha FROM instituicoes WHERE cnpj = %s", (cnpj,))
            usuario = cursor.fetchone()
            
            if usuario and check_password_hash(usuario['senha'], senha):
                # Autenticação bem-sucedida
                session['logged_in'] = True
                session['user_id'] = usuario['id']
                session['user_type'] = "instituicao"
                print(f"Login de Instituição BEM-SUCEDIDO para o ID: {usuario['id']}")
                flash(f"Bem-vindo(a), {usuario['nome']}!", "success")
                
                return redirect(url_for('login_instituicao.painel_instituicao'))
            else:
                mensagem_erro = "CNPJ ou senha incorretos."
        
        except Exception as e:
            mensagem_erro = f"Erro ao tentar fazer login: {e}"
            print(f"Erro no login da instituição: {e}")
        finally:
            if 'conexao' in locals() and conexao.is_connected():
                cursor.close()
                conexao.close()
    
    return render_template('login_instituicao.html', 
                           mensagem_erro=mensagem_erro,
                           mensagem_sucesso=mensagem_sucesso)

# ROTA DE CADASTRO
@login_instituicao_bp.route('/cadastro_instituicao', methods=['GET', 'POST'])
def cadastro_instituicao():
    mensagem_erro_senha = None
    mensagem_erro_nome = None
    mensagem_erro_email = None
    mensagem_erro_cnpj = None
    mensagem_erro_telefone = None
    dados_form = {}

    if request.method == 'POST':
        senha = request.form.get('senha')
        dados_form['nome'] = request.form.get('nome', '')
        dados_form['cnpj'] = request.form.get('cnpj', '')
        dados_form['email'] = request.form.get('email', '')
        dados_form['telefone'] = request.form.get('telefone', '')
        dados_form['endereco'] = request.form.get('endereco', '')

        if not dados_form['nome'].strip():
            mensagem_erro_nome = "Erro: O nome da instituição é obrigatório."

        valida, mensagem = validar_senha(senha)
        if not valida:
            mensagem_erro_senha = f"Erro: {mensagem}"

        # Corrigido: Acessando 'cnpj'
        if not cnpj_valido(dados_form['cnpj']): 
            mensagem_erro_cnpj = "Erro: CNPJ inválido."

        if not validar_telefone(dados_form['telefone']):
            mensagem_erro_telefone = "Erro: Telefone inválido. Deve ter 10 ou 11 dígitos."

        if not validar_email(dados_form['email']):
            mensagem_erro_email = "Erro: E-mail inválido."

      
        if (mensagem_erro_senha or mensagem_erro_email or mensagem_erro_cnpj or
                 mensagem_erro_telefone or mensagem_erro_nome ):
            return render_template('cadastro_instituicao.html',
                                   mensagem_erro_senha=mensagem_erro_senha,
                                   mensagem_erro_email=mensagem_erro_email,
                                   mensagem_erro_cnpj=mensagem_erro_cnpj,
                                   mensagem_erro_telefone=mensagem_erro_telefone,
                                   dados_form=dados_form)
        else:
            try:
                conexao = conectar_bd()
                cursor = conexao.cursor()

                cursor.execute("SELECT id FROM instituicoes WHERE email = %s", (dados_form['email'],))
                if cursor.fetchone():
                    mensagem_erro_email = "Erro: Este e-mail já está cadastrado."
                    return render_template('cadastro_instituicao.html',
                                           mensagem_erro_email=mensagem_erro_email,
                                           dados_form=dados_form)

                cnpj_limpo = re.sub(r'\D', '', dados_form['cnpj'])
                cursor.execute("SELECT id FROM instituicoes WHERE CNPJ = %s", (cnpj_limpo,)) 
                if cursor.fetchone():
                    mensagem_erro_cnpj = "Erro: Este CNPJ já está cadastrado."
                    return render_template('cadastro_instituicao.html',
                                           mensagem_erro_cnpj=mensagem_erro_cnpj,
                                           dados_form=dados_form)

                telefone_limpo = re.sub(r'\D', '', dados_form['telefone'])
                cursor.execute("SELECT id FROM instituicoes WHERE telefone = %s", (telefone_limpo,))
                if cursor.fetchone():
                    mensagem_erro_telefone = "Erro: Este telefone já está cadastrado."
                    return render_template('cadastro_instituicao.html',
                                           mensagem_erro_telefone=mensagem_erro_telefone,
                                           dados_form=dados_form)

                # Cadastro
                dados = (
                    dados_form['nome'],
                    cnpj_limpo, 
                    dados_form['endereco'],
                    dados_form['email'],
                    telefone_limpo, 
                    generate_password_hash(senha)
                )
                
                sql = """
                    INSERT INTO instituicoes
                    (nome, cnpj, endereco, email, telefone, senha)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                
                cursor.execute(sql, dados)
                conexao.commit()
                return redirect(url_for('login_instituicao.login_instituicao', mensagem_sucesso="Cadastro realizado com sucesso!"))

            except mysql.connector.Error as err:
                print(f"Erro de banco de dados ao cadastrar: {err}")
                flash(f"Erro de banco de dados: {err}", "danger")
                return render_template('cadastro_instituicao.html', dados_form=dados_form)
            except Exception as e:
                print(f"Erro inesperado ao cadastrar: {e}")
                flash(f"Erro inesperado: {e}", "danger")
                return render_template('cadastro_instituicao.html', dados_form=dados_form)
            finally:
                if 'conexao' in locals() and conexao.is_connected():
                    cursor.close()
                    conexao.close()

    return render_template('cadastro_instituicao.html',
                            mensagem_erro_senha=mensagem_erro_senha,
                            mensagem_erro_email=mensagem_erro_email,
                            mensagem_erro_cnpj=mensagem_erro_cnpj,
                            mensagem_erro_telefone=mensagem_erro_telefone,
                            dados_form=dados_form)

# ROTA DE ESQUECI SENHA
@login_instituicao_bp.route('/esqueci_senha_instituicao', methods=['GET', 'POST'])
def esqueci_senha_instituicao():
    mensagem_erro = None
    mensagem_sucesso = None
    
    if request.method == 'POST':
        email = request.form.get('email')
        
        if not email:
            mensagem_erro = "Por favor, informe seu e-mail."
            return render_template('esqueci_senha_instituicao.html', mensagem_erro=mensagem_erro)
            
        try:
            conexao = conectar_bd()
            cursor = conexao.cursor(dictionary=True)
            
            cursor.execute("SELECT id, nome FROM instituicoes WHERE email = %s", (email,))
            usuario = cursor.fetchone()
            
            if usuario:
                token = secrets.token_urlsafe(32)
                expiracao = datetime.now() + timedelta(hours=1)
                
                cursor.execute("""
                    INSERT INTO tokens_recuperacao_instituicoes (instituicao_id, token, data_expiracao)
                    VALUES (%s, %s, %s)
                """, (usuario['id'], token, expiracao))
                conexao.commit()
                
                if enviar_email_recuperacao(email, token):
                    mensagem_sucesso = "Um e-mail com instruções para recuperar sua senha foi enviado."
                else:
                    mensagem_erro = "Erro ao enviar e-mail de recuperação. Tente novamente mais tarde."
            else:
                mensagem_sucesso = "Se este e-mail estiver cadastrado, enviaremos instruções para recuperar sua senha."
        
        except Exception as e:
            print(f"Erro ao processar recuperação de senha: {e}")
            mensagem_erro = "Erro ao processar a solicitação. Tente novamente mais tarde."
        finally:
            if 'conexao' in locals() and conexao.is_connected():
                cursor.close()
                conexao.close()
    
    return render_template('esqueci_senha_instituicao.html', 
                            mensagem_erro=mensagem_erro,
                            mensagem_sucesso=mensagem_sucesso)

# ROTA DE RESET DE SENHA
@login_instituicao_bp.route('/reset_senha/<token>', methods=['GET', 'POST'])
def reset_senha(token):
    mensagem_erro = None
    token_valido = False
    
    try:
        conexao = conectar_bd()
        cursor = conexao.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT tr.instituicao_id, p.email 
            FROM tokens_recuperacao_instituicoes tr
            JOIN instituicoes p ON tr.instituicao_id = p.id
            WHERE tr.token = %s AND tr.data_expiracao > %s
        """, (token, datetime.now()))
        
        resultado = cursor.fetchone()
        
        if resultado:
            token_valido = True
            instituicao_id = resultado['instituicao_id']
            
            if request.method == 'POST':
                senha = request.form.get('senha')
                confirmar_senha = request.form.get('confirmar_senha')
                
                if senha != confirmar_senha:
                    mensagem_erro = "As senhas não coincidem."
                else:
                    valida, mensagem = validar_senha(senha)
                    if not valida:
                        mensagem_erro = mensagem
                    else:
                        cursor.execute("""
                            UPDATE instituicoes 
                            SET senha = %s 
                            WHERE id = %s
                        """, (generate_password_hash(senha), instituicao_id))
                        
                        cursor.execute("""
                            DELETE FROM tokens_recuperacao_instituicoes
                            WHERE token = %s
                        """, (token,))
                        
                        conexao.commit()
                        
                        return redirect(url_for('login_instituicao.login_instituicao', mensagem_sucesso="Senha redefinida com sucesso!"))

        else:
            token_valido = False
    
    except Exception as e:
        print(f"Erro ao processar redefinição de senha: {e}")
        mensagem_erro = "Erro ao processar a solicitação. Tente novamente mais tarde."
    finally:
        if 'conexao' in locals() and conexao.is_connected():
            cursor.close()
            conexao.close()
    
    return render_template('reset_senha.html', 
                            token=token,
                            token_valido=token_valido,
                            mensagem_erro=mensagem_erro)

# ROTA DO PAINEL
@login_instituicao_bp.route('/painel_instituicao')
@login_required("instituicao")
def painel_instituicao():
    """Rota do painel de controle da instituição (requer login)."""
    if 'user_id' in session:
        try:
            conexao = conectar_bd()
            cursor = conexao.cursor(dictionary=True)
            cursor.execute("SELECT nome FROM instituicoes WHERE id = %s", (session['user_id'],))
            usuario = cursor.fetchone()
            
            if usuario:
                return render_template("painel_instituicao.html", usuario=usuario)
            else:
                session.clear()
                flash("Sessão inválida. Por favor, faça login novamente.", "erro")
                return redirect(url_for('login_instituicao.login_instituicao'))

        except Exception as e:
            print(f"Erro ao carregar dados da instituição: {e}")
            flash("Erro ao carregar dados do painel.", "erro")
            return redirect(url_for('login_instituicao.login_instituicao')) 
        finally:
            if 'conexao' in locals() and conexao.is_connected():
                cursor.close()
                conexao.close()
    
    return redirect(url_for('login_instituicao.login_instituicao'))

# ROTA DE LOGOUT
@login_instituicao_bp.route("/logout/instituicao")
def logout_instituicao():
    """Rota para fazer logout da instituição."""
    
    logout_user()
    
    flash('Logout da instituição realizado com sucesso.', 'success')
    
    # Redireciona para a rota de login da instituição
    return redirect(url_for('login_instituicao.login_instituicao'))
