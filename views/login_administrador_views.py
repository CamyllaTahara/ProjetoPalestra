import traceback

from flask import render_template, request, Blueprint, redirect, url_for, flash, current_app
from flask import Blueprint, request, render_template, redirect, url_for, session, flash
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
# from utils.security import set_user_session # Comentado para usar session diretamente
#from utils.auth import login_required, logout_user
from utils.security import  logout_user, login_required
from email.header import Header

# O nome interno do Blueprint para roteamento é 'login_administrador'
login_administrador_bp = Blueprint('login_administrador', __name__)

def cpf_valido(cpf):
    """
    Verifica se um número de CPF é válido de acordo com o algoritmo de validação.
    """
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


def validar_email(email):
    """Verifica se o formato básico do e-mail é válido."""
    return '@' in email and '.' in email

def validar_cargo(cargo):
    """Verifica se o cargo fornecido é um dos cargos válidos no sistema."""
    cargos_validos = [
        "super_admin",
        "admin_instituicoes",
        "admin_palestrantes",
        "admin_financeiro",
        "admin_suporte"
    ]
    return cargo in cargos_validos

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

def enviar_email_recuperacao(email, token):
    """Envia um e-mail com o link de recuperação de senha."""
    try:
        remetente_email = "camytahara@gmail.com"
        remetente_senha = "miqr fggg v unn iwnl"
        
        # O link agora usa o endpoint completo: 'login_instituicao.reset_senha'
        link_recuperacao = url_for('login_administrador.reset_senha_administrador', 
                                   token=token, 
                                   _external=True)
        
 
        corpo_email = f"""
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:0; background-color:#0b0f1a; font-family:Arial, sans-serif;">

    <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#0b0f1a; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px; width:100%;">

                    <!-- Header -->
                    <tr>
                        <td align="center" style="padding-bottom: 30px;">
                            <h1 style="margin:0; font-size:1.6rem; color:#00d2ff; letter-spacing:-0.5px;">✦ PalestraApp</h1>
                            <p style="margin:6px 0 0; color:#94a3b8; font-size:0.85rem;">Sistema de Agendamento de Palestras</p>
                        </td>
                    </tr>

                    <!-- Card -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #0f172a, #1e293b); border: 1px solid rgba(0,210,255,0.15); border-radius: 16px; padding: 35px;">
                            <table width="100%" cellpadding="0" cellspacing="0">

                                <!-- Título -->
                                <tr>
                                    <td align="center" style="padding-bottom: 25px; border-bottom: 1px solid rgba(255,255,255,0.07);">
                                        <div style="background: rgba(0,210,255,0.1); border: 1px solid rgba(0,210,255,0.3); border-radius: 50px; display:inline-block; padding: 10px 22px; margin-bottom: 15px;">
                                            <span style="color:#00d2ff; font-size:0.85rem; font-weight:600; letter-spacing:1px;">🔐 RECUPERAÇÃO DE SENHA</span>
                                        </div>
                                        <h2 style="margin:0; color:#f8fafc; font-size:1.4rem;">Redefinição de Senha</h2>
                                        <p style="margin:10px 0 0; color:#94a3b8; font-size:0.95rem; line-height:1.6;">
                                            Recebemos uma solicitação para redefinir sua senha.
                                        </p>
                                    </td>
                                </tr>

                                <!-- Corpo -->
                                <tr>
                                    <td style="padding-top: 25px; padding-bottom: 20px;">
                                        <p style="margin:0 0 15px; color:#cbd5e1; font-size:0.95rem; line-height:1.7;">
                                            Olá! Para redefinir sua senha clique no botão abaixo. O link é válido por <strong style="color:#f8fafc;">1 hora</strong>.
                                        </p>
                                    </td>
                                </tr>

                                <!-- Botão -->
                                <tr>
                                    <td align="center" style="padding-bottom: 25px;">
                                        <a href="{link_recuperacao}"
                                           style="display:inline-block; background: linear-gradient(135deg, #00d2ff, #0099cc); color:#000000; font-weight:700; font-size:0.95rem; text-decoration:none; padding: 14px 35px; border-radius: 10px;">
                                            🔐 Redefinir Senha →
                                        </a>
                                    </td>
                                </tr>

                                <!-- Link alternativo -->
                                <tr>
                                    <td style="padding-bottom: 25px;">
                                        <p style="margin:0 0 8px; color:#94a3b8; font-size:0.75rem; text-transform:uppercase; letter-spacing:1px; font-weight:600;">Ou copie o link abaixo</p>
                                        <div style="background: rgba(0,0,0,0.25); border-left: 3px solid #475569; border-radius: 8px; padding: 12px 18px; word-break: break-all;">
                                            <p style="margin:0; color:#94a3b8; font-size:0.8rem; line-height:1.6;">
                                                {link_recuperacao}
                                            </p>
                                        </div>
                                    </td>
                                </tr>

                                <!-- Aviso -->
                                <tr>
                                    <td>
                                        <div style="background: rgba(245,158,11,0.06); border-left: 3px solid #f59e0b; border-radius: 8px; padding: 12px 18px;">
                                            <p style="margin:0; color:#94a3b8; font-size:0.85rem; line-height:1.6;">
                                                ⚠️ Se você não solicitou a redefinição de senha, ignore este e-mail. Sua senha permanecerá a mesma.
                                            </p>
                                        </div>
                                    </td>
                                </tr>

                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td align="center" style="padding-top: 25px;">
                            <p style="margin:0; color:#475569; font-size:0.8rem; line-height:1.6;">
                                Este e-mail foi enviado automaticamente pelo sistema PalestraApp — TCC.<br>
                                Por favor, não responda diretamente a este e-mail.
                            </p>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>

</body>
</html>
"""
        mensagem = MIMEMultipart()
        mensagem['From'] = remetente_email
        mensagem['To'] = email
        mensagem['Subject'] = Header ("Recuperação de Senha - Sistema de Palestras", "utf-8")
        mensagem.attach(MIMEText(corpo_email, 'html', 'utf-8'))
        servidor = smtplib.SMTP('smtp.gmail.com', 587)
        servidor.starttls()
        servidor.login(remetente_email, remetente_senha)
        servidor.sendmail(remetente_email, email, mensagem.as_bytes())
        servidor.quit()
        return True

    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        return False


@login_administrador_bp.route('/login_administrador', methods=['GET', 'POST'])

def login_administrador():
    """Rota de login para administradores."""
    mensagem_erro = None
    mensagem_sucesso = request.args.get('mensagem_sucesso') # Pega a mensagem de sucesso da URL se houver
    
    if request.method == 'POST':
        cpf = request.form['cpf']
        senha = request.form['senha']
        
        try:
            conexao = conectar_bd()
            cursor = conexao.cursor(dictionary=True)
            
            # Verificar se o e-mail existe e obter a senha hash
            cursor.execute("SELECT id, nome_completo, senha FROM admins WHERE cpf = %s", (cpf,))
            usuario = cursor.fetchone()
            
            if usuario and check_password_hash(usuario['senha'], senha):
                # Autenticação bem-sucedida
                
                # CORREÇÃO CRÍTICA: Define a sessão diretamente para garantir que 'logged_in' esteja presente
                session['logged_in'] = True
                session['user_id'] = usuario['id']
                session['user_type'] = "administrador"
                
                
                # Otimização: usa o nome do Blueprint corretamente
                return redirect(url_for('login_administrador.painel_administrador'))
            else:
                mensagem_erro = "CPF ou senha incorretos."
        
        except Exception as e:
            mensagem_erro = f"Erro ao tentar fazer login: {e}"
        finally:
            if 'conexao' in locals() and conexao.is_connected():
                cursor.close()
                conexao.close()
    
    return render_template('login_administrador.html', 
                           mensagem_erro=mensagem_erro,
                           mensagem_sucesso=mensagem_sucesso)

@login_administrador_bp.route('/cadastro_administrador', methods=['GET', 'POST'])
def cadastro_administrador():
    """Rota de cadastro para novos administradores."""
    mensagem_erro_senha = None
    mensagem_erro_nome = None
    mensagem_erro_email = None
    mensagem_erro_cpf = None
    mensagem_erro_cargo = None
    dados_form = {}

    if request.method == 'POST':
        senha = request.form['senha']
        dados_form['nome_completo'] = request.form.get('nome_completo', '')
        dados_form['cpf'] = request.form.get('cpf', '')
        dados_form['email'] = request.form.get('email', '')
        dados_form['cargo'] = request.form.get('cargo', '')

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


        # Validação do e-mail
        if not validar_email(dados_form['email']):
            mensagem_erro_email = "Erro: E-mail inválido."
        
        if not validar_cargo(dados_form['cargo']):
            mensagem_erro_cargo = "Erro: Cargo incorreto."

        
        if (mensagem_erro_senha or mensagem_erro_email or mensagem_erro_cpf or
                            mensagem_erro_nome or mensagem_erro_cargo):
            return render_template('cadastro_administrador.html',
                                   mensagem_erro_senha=mensagem_erro_senha,
                                   mensagem_erro_email=mensagem_erro_email,
                                   mensagem_erro_cpf=mensagem_erro_cpf,
                                   mensagem_erro_cargo=mensagem_erro_cargo,
                                   dados_form=dados_form)
        else:
            try:
                conexao = conectar_bd()
                cursor = conexao.cursor()

                # Verificar se o e-mail já existe
                cursor.execute("SELECT id FROM admins WHERE email = %s", (dados_form['email'],))
                if cursor.fetchone():
                    mensagem_erro_email = "Erro: Este e-mail já está cadastrado."
                    return render_template('cadastro_administrador.html',
                                           mensagem_erro_senha=mensagem_erro_senha,
                                           mensagem_erro_email=mensagem_erro_email,
                                           mensagem_erro_cpf=mensagem_erro_cpf,
                                           mensagem_erro_cargo=mensagem_erro_cargo,
                                           dados_form=dados_form)

                # Verificar se o CPF já está cadastrado
                cpf_limpo = re.sub(r'\D', '', dados_form['cpf'])
                cursor.execute("SELECT id FROM admins WHERE cpf = %s", (cpf_limpo,))
                if cursor.fetchone():
                    mensagem_erro_cpf = "Erro: Este CPF já está cadastrado."
                    return render_template('cadastro_administrador.html',
                                           mensagem_erro_senha=mensagem_erro_senha,
                                           mensagem_erro_email=mensagem_erro_email,
                                           mensagem_erro_cpf=mensagem_erro_cpf,
                                           mensagem_erro_cargo=mensagem_erro_cargo,
                                           dados_form=dados_form)

                # Se não houver erros, cadastrar o admin
                dados = (
                    dados_form['nome_completo'],
                    dados_form['email'],
                    cpf_limpo,
                    dados_form['cargo'],
                    generate_password_hash(senha)
                )
                
                sql = """
                    INSERT INTO admins
                    (nome_completo, email, cpf, cargo, senha)
                    VALUES (%s, %s, %s, %s, %s)
                """
                
                cursor.execute(sql, dados)
                conexao.commit()
                
                # CORREÇÃO DE ROTEAMENTO: usa 'login_administrador' como prefixo
                return redirect(url_for('login_administrador.login_administrador', mensagem_sucesso="Cadastro realizado com sucesso!"))

            except mysql.connector.Error as err:
                print(f"Erro de banco de dados ao cadastrar: {err}")
                return f"Erro de banco de dados: {err}"
            except Exception as e:
                print(f"Erro inesperado ao cadastrar: {e}")
                return f"Erro inesperado: {e}"
            finally:
                if 'conexao' in locals() and conexao.is_connected():
                    cursor.close()
                    conexao.close()
    
    return render_template('cadastro_administrador.html', dados_form=dados_form)

@login_administrador_bp.route('/esqueci_senha_administrador', methods=['GET', 'POST'])
def esqueci_senha_administrador():
    """Rota para lidar com a solicitação de recuperação de senha."""
    mensagem_erro = None
    mensagem_sucesso = None
    
    if request.method == 'POST':
        email = request.form['email']
        
        try:
            conexao = conectar_bd()
            cursor = conexao.cursor(dictionary=True)
            
            # Verificar se o e-mail existe
            cursor.execute("SELECT id, nome_completo FROM admins WHERE email = %s", (email,))
            usuario = cursor.fetchone()
            
            if usuario:
                # Gerar um token seguro
                token = secrets.token_urlsafe(32)
                expiracao = datetime.now() + timedelta(hours=1) # Token válido por 1 hora
                
                # Salvar o token no banco de dados (tokens_recuperacao_administradores deve existir)
                cursor.execute("""
                    INSERT INTO tokens_recuperacao_administradores (administrador_id, token, data_expiracao)
                    VALUES (%s, %s, %s)
                """, (usuario['id'], token, expiracao))
                conexao.commit()
                
                # Enviar e-mail com o link de recuperação. A função enviar_email_recuperacao foi corrigida internamente
                if enviar_email_recuperacao(email, token):
                    mensagem_sucesso = "Um e-mail com instruções para recuperar sua senha foi enviado."
                else:
                    mensagem_erro = "Erro ao enviar e-mail de recuperação. Tente novamente mais tarde."
            else:
                # Por segurança, não informamos se o e-mail existe ou não
                mensagem_sucesso = "Se este e-mail estiver cadastrado, enviaremos instruções para recuperar sua senha."
        
        except Exception as e:
            print(f"Erro ao processar recuperação de senha: {e}")
            mensagem_erro = "Erro ao processar a solicitação. Tente novamente mais tarde."
        finally:
            if 'conexao' in locals() and conexao.is_connected():
                cursor.close()
                conexao.close()
    
    return render_template('esqueci_senha_administrador.html', 
                           mensagem_erro=mensagem_erro,
                           mensagem_sucesso=mensagem_sucesso)

@login_administrador_bp.route('/reset_senha_administrador/<token>', methods=['GET', 'POST'])
def reset_senha_administrador(token):
    """Rota para redefinir a senha usando o token recebido por e-mail."""
    mensagem_erro = None
    token_valido = False
    
    try:
        conexao = conectar_bd()
        cursor = conexao.cursor(dictionary=True)
        
        # Verificar se o token é válido e não expirou
        cursor.execute("""
            SELECT tr.administrador_id, p.email 
            FROM tokens_recuperacao_administradores tr
            JOIN admins p ON tr.administrador_id = p.id
            WHERE tr.token = %s AND tr.data_expiracao > %s
        """, (token, datetime.now()))
        
        resultado = cursor.fetchone()
        
        if resultado:
            token_valido = True
            administrador_id = resultado['administrador_id']
            
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
                            UPDATE admins
                            SET senha = %s 
                            WHERE id = %s
                        """, (generate_password_hash(senha), administrador_id))
                        
                        # Invalidar o token usado
                        cursor.execute("""
                            DELETE FROM tokens_recuperacao_administradores
                            WHERE token = %s
                        """, (token,))
                        
                        conexao.commit()
                        
                        # CORREÇÃO DE ROTEAMENTO: usa 'login_administrador' como prefixo
                        return redirect(url_for('login_administrador.login_administrador', mensagem_sucesso="Senha redefinida com sucesso!"))

        else:
            token_valido = False
    
    except Exception as e:
        print(f"Erro ao processar redefinição de senha: {e}")
        mensagem_erro = "Erro ao processar a solicitação. Tente novamente mais tarde."
    finally:
        if 'conexao' in locals() and conexao.is_connected():
            cursor.close()
            conexao.close()
    
    return render_template('reset_senha_administrador.html', 
                           token=token,
                           token_valido=token_valido,
                           mensagem_erro=mensagem_erro)

@login_administrador_bp.route('/painel_administrador')
@login_required("administrador")
def painel_administrador():
    """Rota do painel de controle do administrador (requer login)."""
    # Para o painel funcionar, ele precisa da informação do usuário logado
    if 'user_id' in session:
        # Busca os dados completos do usuário, incluindo o cargo
        try:
            conexao = conectar_bd()
            cursor = conexao.cursor(dictionary=True)
            cursor.execute("SELECT nome_completo, cargo FROM admins WHERE id = %s", (session['user_id'],))
            usuario = cursor.fetchone()

            cursor.execute ("SELECT COUNT(*) AS total_pendentes FROM  chamados_suporte WHERE status = 'Pendente' ")
            # Pega o resultado com segurança
            resultado = cursor.fetchone()
        
            total_chamados_pendentes = resultado['total_pendentes'] if resultado else 0

            
            cursor.execute("SELECT COUNT(*) AS total FROM chamados WHERE status = 'em aberto' ")
            total_chamados_aberto=cursor.fetchone()

            resultado = cursor.fetchone()
        
            total_chamados_aberto = resultado ['total'] if resultado else 0

            cursor.close()
            conexao.close()
            


            if usuario:
                return render_template("painel_administrador.html",
                                        chamados_pendentes=total_chamados_pendentes, 
                                        chamados_aberto=total_chamados_aberto, 
                                        usuario=usuario)
            else:
                # Se o ID na sessão for inválido, limpa a sessão e redireciona para o login
                session.clear()
                flash("Sessão inválida. Por favor, faça login novamente.", "erro")
                return redirect(url_for('login_administrador.login_administrador'))

        except Exception as e:
            print(f"Erro ao carregar dados do administrador: {e}")
            print("\n" + "🛑" * 20)
            print("AQUI ESTÁ O ERRO VERDADEIRO ESCONDIDO ATRÁS DO 0:")
            traceback.print_exc() # ISSO VAI MOSTRAR A LINHA EXATA DO ERRO
            print("🛑" * 20 + "\n")

            flash("Erro ao carregar dados do painel.", "erro")
           
            return redirect(url_for('login_administrador.login_administrador'))
        finally:
            if 'conexao' in locals() and conexao.is_connected():
                cursor.close()
                conexao.close()
    
    # Se 'user_id' não estiver na sessão (o que não deve acontecer por causa do @login_required), redireciona.
    return redirect(url_for('login_administrador.login_administrador'))

@login_administrador_bp.route("/logout/administrador")
def logout_administrador():
    """Rota para fazer logout do administrador. CORRIGIDA para retornar redirect."""
    
    # 1. Chama a função utilitária para limpar a sessão.
    # Esta função deve apenas manipular a sessão e não retornar um Response.
    logout_user() 
    
    # 2. Opcional: Mensagem de feedback
    flash('Logout do administrador realizado com sucesso.', 'success')
    
    # 3. OBRIGATÓRIO: Retorna o objeto de redirecionamento Flask.
    # Redireciona para a rota de login do administrador.
    return redirect(url_for('login_administrador.login_administrador'))