from flask import render_template, request, Blueprint, redirect, url_for, flash, current_app, session
from werkzeug.security import generate_password_hash, check_password_hash
import re
from models.instituicao import conectar_bd
import mysql.connector
import os 
import secrets 
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import urllib.parse
from utils.security import login_required
from utils.mail import send_notification_email



login_palestrante_bp = Blueprint('login_palestrante', __name__)


def cpf_valido(cpf):
    """Verifica se um CPF é válido, incluindo o cálculo dos dígitos verificadores."""
    cpf = ''.join(filter(str.isdigit, cpf))
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    

    soma = 0
    for i in range(9):
        soma += int(cpf[i]) * (10 - i)
    resto = 11 - (soma % 11)
    digito1_esperado = str(resto) if resto < 10 else '0'
    if cpf[9] != digito1_esperado:
        return False
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




def enviar_email_recuperacao(email, token):
    """Envia um e-mail com o link de recuperação de senha."""
    try:
        remetente_email = current_app.config.get('MAIL_USERNAME')
        remetente_senha = current_app.config.get('MAIL_PASSWORD')
        
        if not remetente_email or not remetente_senha:
            print("Erro de configuração: Credenciais de e-mail não definidas em current_app.config.")
            return False

        mensagem = MIMEMultipart()
        mensagem['From'] = remetente_email
        mensagem['To'] = email
        from email.header import Header
        mensagem['Subject'] =Header ( "Recuperação de Senha - Sistema de Palestras","utf-8")

        link_recuperacao = url_for('login_palestrante.reset_senha_palestrante', 
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

        
                                <tr>
                                    <td style="padding-top: 25px; padding-bottom: 20px;">
                                        <p style="margin:0 0 15px; color:#cbd5e1; font-size:0.95rem; line-height:1.7;">
                                            Olá! Para redefinir sua senha clique no botão abaixo. O link é válido por <strong style="color:#f8fafc;">1 hora</strong>.
                                        </p>
                                    </td>
                                </tr>

         
                                <tr>
                                    <td align="center" style="padding-bottom: 25px;">
                                        <a href="{link_recuperacao}"
                                           style="display:inline-block; background: linear-gradient(135deg, #00d2ff, #0099cc); color:#000000; font-weight:700; font-size:0.95rem; text-decoration:none; padding: 14px 35px; border-radius: 10px;">
                                            🔐 Redefinir Senha →
                                        </a>
                                    </td>
                                </tr>
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
        
        mensagem.attach(MIMEText(corpo_email, 'html','utf-8'))
        
        servidor = smtplib.SMTP('smtp.gmail.com', 587)
        servidor.starttls()
        servidor.login(remetente_email, remetente_senha)
        

        
        servidor.sendmail(remetente_email, email,  mensagem.as_bytes())
        servidor.quit()
        
        return True
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        return False

UPLOAD_FOLDER = 'uploads_curriculos'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)




@login_palestrante_bp.route('/login_palestrante', methods=['GET', 'POST'])
def login_palestrante():
    print(f"🔴🔴🔴 ARQUIVO login_palestrante.py FOI CARREGADO 🔴🔴🔴")
    print("--- DEBUG LOGIN ---")
    print(f"ID na sessão: {session.get('user_id')}")
    print(f"Tipo na sessão: {session.get('user_type')}")
    
    mensagem_erro = None
    mensagem_sucesso = request.args.get('mensagem_sucesso')
    conexao = None
    
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        
        try:
            conexao = conectar_bd()
            cursor = conexao.cursor(dictionary=True)
            
       
            cursor.execute("SELECT id, nome_completo, senha, status FROM palestrantes WHERE email = %s", (email,))
            usuario = cursor.fetchone()
            
            if usuario and check_password_hash(usuario['senha'], senha):
               
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

        dados_form['nome_completo'] = request.form.get('nome', '')
        dados_form['cpf'] = request.form.get('cpf', '')
        dados_form['email'] = request.form.get('email', '')
        dados_form['telefone'] = request.form.get('telefone', '')
        dados_form['anos_experiencia'] = request.form.get('anos_experiencia', '')
        dados_form['ramo_atividade'] = request.form.get('ramo_atividade', '')
        curriculo = request.files.get('curriculo')


        
        if not dados_form['nome_completo'].strip():
            mensagem_erro_nome = "Erro: O nome completo é obrigatório."


        valida, mensagem = validar_senha(senha)
        if not valida:
            mensagem_erro_senha = f"Erro: {mensagem}"


        if not cpf_valido(dados_form['cpf']):
            mensagem_erro_cpf = "Erro: CPF inválido."


        if not validar_telefone(dados_form['telefone']):
            mensagem_erro_telefone = "Erro: Telefone inválido. Deve ter 10 ou 11 dígitos."


        if not validar_email(dados_form['email']):
            mensagem_erro_email = "Erro: E-mail inválido."

        curriculo_filename = None
        if curriculo:
            if curriculo.filename == '':
                mensagem_erro_curriculo = "Erro: Nenhum arquivo de currículo selecionado."
            elif not curriculo.filename.lower().endswith('.pdf'):
                mensagem_erro_curriculo = "Erro: Por favor, envie um arquivo PDF."
            else:
           
                filename_base = re.sub(r'\D', '', dados_form['cpf'])
                curriculo_filename = os.path.join(UPLOAD_FOLDER, f"{filename_base}.pdf")
                try:
                    curriculo.save(curriculo_filename)
                except Exception as e:
                    mensagem_erro_curriculo = f"Erro ao salvar o currículo: {e}"
                    curriculo_filename = None 
        else:
            mensagem_erro_curriculo = "Erro: O currículo é obrigatório."
            
        
  
        if (mensagem_erro_senha or mensagem_erro_email or mensagem_erro_cpf or
            mensagem_erro_telefone or mensagem_erro_nome or mensagem_erro_curriculo):
            
           
            if curriculo_filename and os.path.exists(curriculo_filename):
                 os.remove(curriculo_filename)
                 
            return render_template('cadastro_palestrante.html',
                                   mensagem_erro_senha=mensagem_erro_senha,
                                   mensagem_erro_email=mensagem_erro_email,
                                   mensagem_erro_cpf=mensagem_erro_cpf,
                                   mensagem_erro_telefone=mensagem_erro_telefone,
                                   mensagem_erro_curriculo=mensagem_erro_curriculo,
                                   dados_form=dados_form)
        
      
        else:
            try:
                conexao = conectar_bd()
                cursor = conexao.cursor()

           
                cursor.execute("SELECT id FROM palestrantes WHERE email = %s", (dados_form['email'],))
                if cursor.fetchone():
                    mensagem_erro_email = "Erro: Este e-mail já está cadastrado."
                    

                cursor.execute("SELECT id FROM palestrantes WHERE cpf = %s", (re.sub(r'\D', '', dados_form['cpf']),))
                if cursor.fetchone():
                    mensagem_erro_cpf = "Erro: Este CPF já está cadastrado."
                
          
                cursor.execute("SELECT id FROM palestrantes WHERE telefone = %s", (re.sub(r'\D', '', dados_form['telefone']),))
                if cursor.fetchone():
                    mensagem_erro_telefone = "Erro: Este telefone já está cadastrado."

                if mensagem_erro_email or mensagem_erro_cpf or mensagem_erro_telefone:
                    
            
                    if curriculo_filename and os.path.exists(curriculo_filename):
                        os.remove(curriculo_filename)
                        
                    return render_template('cadastro_palestrante.html',
                                           mensagem_erro_senha=mensagem_erro_senha,
                                           mensagem_erro_email=mensagem_erro_email,
                                           mensagem_erro_cpf=mensagem_erro_cpf,
                                           mensagem_erro_telefone=mensagem_erro_telefone,
                                           mensagem_erro_curriculo=mensagem_erro_curriculo,
                                           dados_form=dados_form)
                
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
                
   
                if senha != confirmar_senha:
                    mensagem_erro = "As senhas não coincidem."
                else:
              
                    valida, mensagem = validar_senha(senha)
                    if not valida:
                        mensagem_erro = mensagem
                    else:
                
                        cursor.execute("""
                            UPDATE palestrantes 
                            SET senha = %s 
                            WHERE id = %s
                        """, (generate_password_hash(senha), palestrante_id))
                        
           
                        cursor.execute("""
                            DELETE FROM tokens_recuperacao_palestrantes
                            WHERE token = %s
                        """, (token,))
                        
                        conexao.commit()
                        
              
                        return redirect(url_for('login_palestrante.login_palestrante', mensagem_sucesso="Senha redefinida com sucesso!"))

        else:
            token_valido = False 
    
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

from flask import Blueprint, render_template, session, redirect, url_for, g


@login_palestrante_bp.route('/painel_palestrante')
@login_required("palestrante")
def painel_palestrante():
    """Rota do painel de controle do  administrador (requer login)."""

    if 'user_id' in session:

        try:
            conexao = conectar_bd()
            cursor = conexao.cursor(dictionary=True)
            cursor.execute("SELECT nome_completo FROM palestrantes WHERE id = %s", (session['user_id'],))
            usuario = cursor.fetchone()
            
            if usuario:
                return render_template("painel_palestrante.html", usuario=usuario)
            else:
     
                session.clear()
                if usuario:
                 return render_template("painel_palestrante.html", usuario=usuario)
                else:
                 print("DEBUG: PERDI A SESSÃO PORQUE NÃO ACHEI O USUÁRIO NO BANCO!") # <--- ADICIONE ISSO
                session.clear()
                return redirect(url_for('login_palestrante.login_palestrante'))
            

        except Exception as e:
            print(f"Erro ao carregar dados do palestrante: {e}")
            flash("Erro ao carregar dados do painel.", "erro")
   
            return redirect(url_for('login_palestrante.login_palestrante'))
        finally:
            if 'conexao' in locals() and conexao.is_connected():
                cursor.close()
                conexao.close()
    
    return redirect(url_for('login_palestrante.login_palestrante'))


@login_palestrante_bp.route("/logout_palestrante")
def logout_palestrante():
    """Rota para fazer logout do palestrante."""
    from utils.security import logout_user
    
    logout_user()  
    flash('Logout realizado com sucesso.', 'success')
    
    return redirect(url_for('login_palestrante.login_palestrante'))

@login_palestrante_bp.route("/excluir_conta", methods=["POST"])
@login_required("user_id")
def excluir_conta_palestrante():
    palestrante_id = session.get('user_id')

    try:
        conexao = conectar_bd()
        cursor = conexao.cursor(dictionary=True)
        id_limpo = int(palestrante_id)

        cursor.execute("DELETE FROM chamados_suporte WHERE palestrante_id = %s", [id_limpo])

        cursor.execute(""" 
            UPDATE palestras_confirmadas
            SET status='cancelada'
            WHERE palestrante_id = %s AND status = 'agendada'
        """, (id_limpo,))
        
   
        cursor.execute("DELETE FROM palestrantes WHERE id = %s", [id_limpo])
        

        conexao.commit()
        
        cursor.close()
        conexao.close()

        session.clear()
        flash("Sua conta foi excluída permanentemente. Sentiremos sua falta!", "warning")
        return redirect(url_for("login_palestrante.login_palestrante")) 
        
    except Exception as e:
      
        if 'conexao' in locals() and conexao:
            conexao.rollback()
            cursor.close()
            conexao.close()
            
   
        print("\n" + "#"*60)
        print(f"❌ ERRO REAL DO BANCO DE DADOS: {e}")
        print("#"*60 + "\n")
    
        flash(f"Não foi possível excluir sua conta porque existem dados vinculados a ela. Erro: {e}", "danger")
        return redirect(url_for("login_palestrante.painel_palestrante"))