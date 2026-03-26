from flask import render_template, request, Blueprint, redirect, url_for, flash, current_app, session
from werkzeug.security import generate_password_hash, check_password_hash
import re
from models.instituicao import conectar_bd
import mysql.connector
import os # Para manipulação de arquivos
import secrets # Para gerar tokens seguros
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import urllib.parse # Para codificar o token na URL
from utils.security import login_required
from utils.mail import send_notification_email
#from utils.auth import login_required, logout_user

# Criação do Blueprint para as rotas de login e cadastro de palestrante
login_palestrante_bp = Blueprint('login_palestrante', __name__)


# --- Funções de Validação ---

def cpf_valido(cpf):
    """Verifica se um CPF é válido, incluindo o cálculo dos dígitos verificadores."""
    cpf = ''.join(filter(str.isdigit, cpf))
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    
    # Cálculo do primeiro dígito verificador
    soma = 0
    for i in range(9):
        soma += int(cpf[i]) * (10 - i)
    resto = 11 - (soma % 11)
    digito1_esperado = str(resto) if resto < 10 else '0'
    if cpf[9] != digito1_esperado:
        return False
        
    # Cálculo do segundo dígito verificador
    soma = 0
    for i in range(10):
        soma += int(cpf[i]) * (11 - i)
    resto = 11 - (soma % 11)
    digito2_esperado = str(resto) if resto < 10 else '0'
    
    return cpf[10] == digito2_esperado

def validar_telefone(telefone):
    """Verifica se o telefone tem 10 ou 11 dígitos."""
    telefone = ''.join(filter(str.isdigit, telefone))
    return len(telefone) in (10, 11)

def validar_email(email):
    """Verifica se o e-mail tem um formato básico válido."""
    return '@' in email and '.' in email

def validar_senha(senha):
    """Verifica se a senha atende aos requisitos de segurança."""
    if len(senha) < 8:
        return False, "A senha deve ter pelo menos 8 caracteres."
    elif not any(c in "!@#$%&*" for c in senha):
        return False, "A senha deve conter pelo menos um caractere especial (!@#$%&*)."
    elif not any(c.isupper() for c in senha):
        return False, "A senha deve conter pelo menos uma letra maiúscula."
    elif not any(c.islower() for c in senha):
        return False, "A senha deve conter pelo menos uma letra minúscula."
    elif not any(c.isdigit() for c in senha):
        return False, "A senha deve conter pelo menos um número."
    return True, ""


# --- Funções de Serviço ---

def enviar_email_recuperacao(email, token):
    """Envia um e-mail com o link de recuperação de senha."""
    try:
        # Lendo credenciais das configurações do Flask (MAIL_USERNAME e MAIL_PASSWORD)
        remetente_email = current_app.config.get('MAIL_USERNAME')
        remetente_senha = current_app.config.get('MAIL_PASSWORD')
        
        if not remetente_email or not remetente_senha:
            print("Erro de configuração: Credenciais de e-mail não definidas em current_app.config.")
            return False

        # Criando a mensagem
        mensagem = MIMEMultipart()
        mensagem['From'] = remetente_email
        mensagem['To'] = email
        from email.header import Header
        mensagem['Subject'] =Header ( "Recuperação de Senha - Sistema de Palestras","utf-8")
        
        # Link com o token para redefinir a senha
        link_recuperacao = url_for('login_palestrante.reset_senha_palestrante', 
                                   token=token, 
                                   _external=True)
        
        corpo_email = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4CAF50; color: white; padding: 10px; text-align: center; }}
                .content {{ padding: 20px; }}
                .button {{ background-color: #4CAF50; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px; display: inline-block; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>Recuperação de Senha</h2>
                </div>
                <div class="content">
                    <p>Olá,</p>
                    <p>Recebemos uma solicitacao para redefinir sua senha. Se você não fez esta solicitacao, ignore este e-mail.</p>
                    <p>Para redefinir sua senha, clique no botao abaixo:</p>
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
        
        mensagem.attach(MIMEText(corpo_email, 'html','utf-8'))
        
        # Conectando ao servidor de e-mail (Configuração para Gmail)
        servidor = smtplib.SMTP('smtp.gmail.com', 587)
        servidor.starttls()
        servidor.login(remetente_email, remetente_senha)
        
        # Enviando e-mail
        
        servidor.sendmail(remetente_email, email,  mensagem.as_bytes())
        servidor.quit()
        
        return True
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        return False

# --- Configuração de Upload ---

# Pasta para salvar os currículos
UPLOAD_FOLDER = 'uploads_curriculos'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


# --- Rotas (Views) ---

@login_palestrante_bp.route('/login_palestrante', methods=['GET', 'POST'])
def login_palestrante():
    print(f"🔴🔴🔴 ARQUIVO login_palestrante.py FOI CARREGADO 🔴🔴🔴")
    mensagem_erro = None
    mensagem_sucesso = request.args.get('mensagem_sucesso')
    conexao = None
    
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        
        try:
            conexao = conectar_bd()
            cursor = conexao.cursor(dictionary=True)
            
            # ✅ Adicionado 'status' no SELECT
            cursor.execute("SELECT id, nome_completo, senha, status FROM palestrantes WHERE email = %s", (email,))
            usuario = cursor.fetchone()
            
            if usuario and check_password_hash(usuario['senha'], senha):
                # ✅ Verificar se está suspenso ou banido
                if usuario.get('status') == 'suspenso':
                    mensagem_erro = "Sua conta está suspensa. Entre em contato com a administração."
                elif usuario.get('status') == 'banido':
                    mensagem_erro = "Sua conta foi banida permanentemente da plataforma."
                else:
                    session['logged_in'] = True
                    session['user_id'] = usuario['id']
                    session['user_type'] = "palestrante"
                    print(f"Login de Palestrante BEM-SUCEDIDO para o ID: {usuario['id']}")
                    return redirect(url_for('login_palestrante.painel_palestrante'))
            else:
                mensagem_erro = "E-mail ou senha incorretos."
                print(f"Login de Palestrante FALHOU para o e-mail: {email}")
        
        except Exception as e:
            mensagem_erro = f"Erro ao tentar fazer login: {e}"
            print(f"Erro de exceção no login: {e}")
        finally:
            if 'conexao' in locals() and conexao.is_connected():
                cursor.close()
                conexao.close()
    
    return render_template('login_palestrante.html', 
                           mensagem_erro=mensagem_erro,
                           mensagem_sucesso=mensagem_sucesso)

@login_palestrante_bp.route('/cadastro_palestrante', methods=['GET', 'POST'])
def cadastro_palestrante():
    """Rota para o Cadastro de Palestrantes."""
    mensagem_erro_senha = None
    mensagem_erro_nome = None
    mensagem_erro_email = None
    mensagem_erro_cpf = None
    mensagem_erro_telefone = None
    mensagem_erro_curriculo = None
    dados_form = {}
    conexao = None

    if request.method == 'POST':
        senha = request.form['senha']
        # Captura todos os dados do formulário
        dados_form['nome_completo'] = request.form.get('nome', '')
        dados_form['cpf'] = request.form.get('cpf', '')
        dados_form['email'] = request.form.get('email', '')
        dados_form['telefone'] = request.form.get('telefone', '')
        dados_form['anos_experiencia'] = request.form.get('anos_experiencia', '')
        dados_form['ramo_atividade'] = request.form.get('ramo_atividade', '')
        curriculo = request.files.get('curriculo')

        # --- Etapa 1: Validação de Dados ---
        
        # Validação do nome
        if not dados_form['nome_completo'].strip():
            mensagem_erro_nome = "Erro: O nome completo é obrigatório."

        # Validação da senha
        valida, mensagem = validar_senha(senha)
        if not valida:
            mensagem_erro_senha = f"Erro: {mensagem}"

        # Validação do CPF
        if not cpf_valido(dados_form['cpf']):
            mensagem_erro_cpf = "Erro: CPF inválido."

        # Validação do telefone
        if not validar_telefone(dados_form['telefone']):
            mensagem_erro_telefone = "Erro: Telefone inválido. Deve ter 10 ou 11 dígitos."

        # Validação do e-mail
        if not validar_email(dados_form['email']):
            mensagem_erro_email = "Erro: E-mail inválido."

        # Validação e salvamento do currículo
        curriculo_filename = None
        if curriculo:
            if curriculo.filename == '':
                mensagem_erro_curriculo = "Erro: Nenhum arquivo de currículo selecionado."
            elif not curriculo.filename.lower().endswith('.pdf'):
                mensagem_erro_curriculo = "Erro: Por favor, envie um arquivo PDF."
            else:
                # Salvar o currículo com um nome seguro (usando o CPF limpo)
                filename_base = re.sub(r'\D', '', dados_form['cpf'])
                curriculo_filename = os.path.join(UPLOAD_FOLDER, f"{filename_base}.pdf")
                try:
                    curriculo.save(curriculo_filename)
                except Exception as e:
                    mensagem_erro_curriculo = f"Erro ao salvar o currículo: {e}"
                    curriculo_filename = None # Garante que não tenta salvar no DB se o arquivo falhou
        else:
            mensagem_erro_curriculo = "Erro: O currículo é obrigatório."
            
        
        # Se houver algum erro de validação (de formulário ou arquivo), retorna a página com mensagens
        if (mensagem_erro_senha or mensagem_erro_email or mensagem_erro_cpf or
            mensagem_erro_telefone or mensagem_erro_nome or mensagem_erro_curriculo):
            
            # Remove o arquivo salvo se houve erro de DB na etapa de pré-validação (apenas para o curriculo_filename)
            if curriculo_filename and os.path.exists(curriculo_filename):
                 os.remove(curriculo_filename)
                 
            return render_template('cadastro_palestrante.html',
                                   mensagem_erro_senha=mensagem_erro_senha,
                                   mensagem_erro_email=mensagem_erro_email,
                                   mensagem_erro_cpf=mensagem_erro_cpf,
                                   mensagem_erro_telefone=mensagem_erro_telefone,
                                   mensagem_erro_curriculo=mensagem_erro_curriculo,
                                   dados_form=dados_form)
        
        # --- Etapa 2: Validação de Unicidade no Banco de Dados e Inserção ---
        else:
            try:
                conexao = conectar_bd()
                cursor = conexao.cursor()

                # Verifica unicidade do E-mail
                cursor.execute("SELECT id FROM palestrantes WHERE email = %s", (dados_form['email'],))
                if cursor.fetchone():
                    mensagem_erro_email = "Erro: Este e-mail já está cadastrado."
                    
                # Verifica unicidade do CPF
                cursor.execute("SELECT id FROM palestrantes WHERE cpf = %s", (re.sub(r'\D', '', dados_form['cpf']),))
                if cursor.fetchone():
                    mensagem_erro_cpf = "Erro: Este CPF já está cadastrado."
                
                # Verifica unicidade do Telefone
                cursor.execute("SELECT id FROM palestrantes WHERE telefone = %s", (re.sub(r'\D', '', dados_form['telefone']),))
                if cursor.fetchone():
                    mensagem_erro_telefone = "Erro: Este telefone já está cadastrado."

                # Se houver erros de unicidade, retorna a página com mensagens
                if mensagem_erro_email or mensagem_erro_cpf or mensagem_erro_telefone:
                    
                    # Remove o arquivo salvo, pois o cadastro falhou
                    if curriculo_filename and os.path.exists(curriculo_filename):
                        os.remove(curriculo_filename)
                        
                    return render_template('cadastro_palestrante.html',
                                           mensagem_erro_senha=mensagem_erro_senha,
                                           mensagem_erro_email=mensagem_erro_email,
                                           mensagem_erro_cpf=mensagem_erro_cpf,
                                           mensagem_erro_telefone=mensagem_erro_telefone,
                                           mensagem_erro_curriculo=mensagem_erro_curriculo,
                                           dados_form=dados_form)
                
                # Se tudo estiver ok, cadastra o palestrante
                dados = (
                    dados_form['nome_completo'],
                    re.sub(r'\D', '', dados_form['cpf']), # CPF limpo
                    dados_form['anos_experiencia'],
                    dados_form['ramo_atividade'],
                    curriculo_filename,
                    dados_form['email'],
                    re.sub(r'\D', '', dados_form['telefone']), # Telefone limpo
                    generate_password_hash(senha) # Senha criptografada
                )
                
                sql = """
                    INSERT INTO palestrantes
                    (nome_completo, cpf, anos_experiencia, ramo_atividade, curriculo_pdf, email, telefone, senha)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                cursor.execute(sql, dados)
                conexao.commit()
                return redirect(url_for('login_palestrante.login_palestrante', mensagem_sucesso="Cadastro realizado com sucesso!"))

            except mysql.connector.Error as err:
                print(f"Erro de banco de dados ao cadastrar: {err}")
                return f"Erro de banco de dados: {err}"
            except Exception as e:
                print(f"Erro inesperado ao cadastrar: {e}")
                return f"Erro inesperado: {e}"
            finally:
                if conexao and conexao.is_connected():
                    cursor.close()
                    conexao.close()

    # Rota GET
    return render_template('cadastro_palestrante.html',
                           mensagem_erro_senha=mensagem_erro_senha,
                           mensagem_erro_email=mensagem_erro_email,
                           mensagem_erro_cpf=mensagem_erro_cpf,
                           mensagem_erro_telefone=mensagem_erro_telefone,
                           mensagem_erro_curriculo=mensagem_erro_curriculo,
                           dados_form=dados_form)

@login_palestrante_bp.route('/esqueci_senha', methods=['GET', 'POST'])
def esqueci_senha():
    mensagem_erro = None
    mensagem_sucesso = None
    
    if request.method == 'POST':
        email = request.form.get('email')
        
        if not email:
            mensagem_erro = "Por favor, informe seu e-mail."
            return render_template('esqueci_senha.html', mensagem_erro=mensagem_erro)
            
        try:
            conexao = conectar_bd()
            cursor = conexao.cursor(dictionary=True)
            
            cursor.execute("SELECT id, nome_completo FROM palestrantes WHERE email = %s", (email,))
            usuario = cursor.fetchone()
            
            if usuario:
                token = secrets.token_urlsafe(32)
                expiracao = datetime.now() + timedelta(hours=1)
                
                cursor.execute("""
                    INSERT INTO tokens_recuperacao_palestrantes (palestrante_id, token, data_expiracao)
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
    
    return render_template('esqueci_senha.html', 
                            mensagem_erro=mensagem_erro,
                            mensagem_sucesso=mensagem_sucesso)

@login_palestrante_bp.route('/reset_senha_palestrante/<token>', methods=['GET', 'POST'])
def reset_senha_palestrante(token):
    mensagem_erro = None
    token_valido = False
    
    
    try:
        conexao = conectar_bd()
        cursor = conexao.cursor(dictionary=True)
        
        # Verificar se o token é válido e não expirou
        cursor.execute("""
            SELECT tr.palestrante_id, p.email 
            FROM tokens_recuperacao_palestrantes tr
            JOIN palestrantes p ON tr.palestrante_id = p.id
            WHERE tr.token = %s AND tr.data_expiracao > %s
        """, (token, datetime.now()))
        
        resultado = cursor.fetchone()
    
        if resultado:
            token_valido = True
            palestrante_id = resultado['palestrante_id']
            
            if request.method == 'POST':
                senha = request.form['senha']
                confirmar_senha = request.form['confirmar_senha']
                
                # Verificar se as senhas coincidem
                if senha != confirmar_senha:
                    mensagem_erro = "As senhas não coincidem."
                else:
                    # Validar a nova senha
                    valida, mensagem = validar_senha(senha)
                    if not valida:
                        mensagem_erro = mensagem
                    else:
                        # Atualizar a senha no banco de dados
                        cursor.execute("""
                            UPDATE palestrantes 
                            SET senha = %s 
                            WHERE id = %s
                        """, (generate_password_hash(senha), palestrante_id))
                        
                        # Invalidar/Deletar o token usado
                        cursor.execute("""
                            DELETE FROM tokens_recuperacao_palestrantes
                            WHERE token = %s
                        """, (token,))
                        
                        conexao.commit()
                        
                        # Redirecionar para a página de login com mensagem de sucesso
                        return redirect(url_for('login_palestrante.login_palestrante', mensagem_sucesso="Senha redefinida com sucesso!"))

        else:
            token_valido = False # O token não foi encontrado ou expirou
    
    except Exception as e:
        print(f"Erro ao processar redefinição de senha: {e}")
        mensagem_erro = "Erro ao processar a solicitação. Tente novamente mais tarde."
    finally:
        if conexao and conexao.is_connected():
            cursor.close()
            conexao.close()
    
    return render_template('reset_senha_palestrante.html', 
                           token=token,
                           token_valido=token_valido,
                           mensagem_erro=mensagem_erro)

@login_palestrante_bp.route('/painel_palestrante')
@login_required("palestrante")
def painel_palestrante():
    """Rota do painel de controle do  administrador (requer login)."""
    # Para o painel funcionar, ele precisa da informação do usuário logado
    if 'user_id' in session:
        # Busca os dados completos do usuário
        try:
            conexao = conectar_bd()
            cursor = conexao.cursor(dictionary=True)
            cursor.execute("SELECT nome_completo FROM palestrantes WHERE id = %s", (session['user_id'],))
            usuario = cursor.fetchone()
            
            if usuario:
                return render_template("painel_palestrante.html", usuario=usuario)
            else:
                # Se o ID na sessão for inválido, limpa a sessão e redireciona para o login
                session.clear()
                flash("Sessão inválida. Por favor, faça login novamente.", "erro")
                return redirect(url_for('login_palestrante.login_palestrante'))

        except Exception as e:
            print(f"Erro ao carregar dados do palestrante: {e}")
            flash("Erro ao carregar dados do painel.", "erro")
            # Em caso de erro de DB, apenas retorna o template sem os dados, ou redireciona
            return redirect(url_for('login_palestrante.login_palestrante'))
        finally:
            if 'conexao' in locals() and conexao.is_connected():
                cursor.close()
                conexao.close()
    # Se 'user_id' não estiver na sessão (o que não deve acontecer por causa do @login_required), redireciona.
    return redirect(url_for('login_palestrante.login_palestrante'))


@login_palestrante_bp.route("/logout_palestrante")
def logout_palestrante():
    """Rota para fazer logout do palestrante."""
    from utils.security import logout_user
    
    logout_user()  # Limpa a sessão
    flash('Logout realizado com sucesso.', 'success')
    
    return redirect(url_for('login_palestrante.login_palestrante'))