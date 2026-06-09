
# views/instituicao_views.py
from flask import flash, redirect, render_template, request, Blueprint, session, url_for
from werkzeug.security import generate_password_hash
import requests
import re
from models.instituicao import conectar_bd
import mysql.connector
from utils.security import login_required

instituicao_bp = Blueprint('instituicao', __name__)

def validar_cnpj(cnpj):
    cnpj = ''.join(filter(str.isdigit, cnpj))
    return len(cnpj) == 14

def validar_telefone(telefone):
    telefone = ''.join(filter(str.isdigit, telefone))
    return len(telefone) in (10, 11)

def validar_email(email):
    return '@' in email and '.' in email

def verificar_cnpj_ativo(cnpj_com_formatacao):
    cnpj_sem_formatacao = re.sub(r'\D', '', cnpj_com_formatacao)
    url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_sem_formatacao}"
    print(f"Consultando CNPJ na API: {cnpj_sem_formatacao}") # Adicionado para debug
    try:
        response = requests.get(url)
        if response.status_code == 200:
            dados = response.json()
            print(f"Resposta da API (sucesso): {dados}") # Adicionado para debug
            situacao_codigo = dados.get('situacao_cadastral')
            print(f"Código da Situação Cadastral retornado pela API: {situacao_codigo}") # Debug
            if situacao_codigo == 2:
                return True
            else:
                return False
        else:
            print(f"Erro ao consultar CNPJ (Brasil API): {response.status_code}")
            print(f"Resposta da API (erro): {response.text}") # Adicionado para debug
            return False
    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão ao consultar CNPJ (Brasil API): {e}")
        return False
    except Exception as e:
        print(f"Erro inesperado ao consultar CNPJ (Brasil API): {e}")
        return False

@instituicao_bp.route('/cadastro_instituicao', methods=['GET', 'POST'])
def cadastro_instituicao():
    mensagem_erro_senha = None
    mensagem_erro_nome = None
    mensagem_erro_email = None
    mensagem_erro_cnpj = None
    mensagem_erro_telefone = None
    mensagem_erro_numero = None # Nova mensagem de erro para o número
    dados_form = {}

    if request.method == 'POST':
        senha = request.form['senha']
        dados_form['nome'] = request.form.get('nome', '')
        dados_form['cnpj'] = request.form.get('cnpj', '')
        dados_form['endereco'] = request.form.get('endereco', '')
        dados_form['numero'] = request.form.get('numero', '') # Recebe o número
        dados_form['email'] = request.form.get('email', '')
        dados_form['telefone'] = request.form.get('telefone', '')
    

        # Validação da senha
        if len(senha) < 8:
            mensagem_erro_senha = "Erro: A senha deve ter pelo menos 8 caracteres."
        elif not any(c in "!@#$%&*" for c in senha):
            mensagem_erro_senha = "Erro: A senha deve conter pelo menos um caractere especial (!@#$%&*)."
        elif not any(c.isupper() for c in senha):
            mensagem_erro_senha = "Erro: A senha deve conter pelo menos uma letra maiúscula."
        elif not any(c.islower() for c in senha):
            mensagem_erro_senha = "Erro: A senha deve conter pelo menos uma letra minúscula."
        elif not any(c.isdigit() for c in senha):
            mensagem_erro_senha = "Erro: A senha deve conter pelo menos um número."


        if not validar_cnpj(dados_form['cnpj']):
            mensagem_erro_cnpj = "Erro: CNPJ inválido. Deve conter 14 dígitos."
      
        elif validar_cnpj(dados_form['cnpj']):
            is_cnpj_ativo = verificar_cnpj_ativo(dados_form['cnpj'])
            print(f"CNPJ está ativo? {is_cnpj_ativo}") # Adicionado para debug
            if not is_cnpj_ativo:
                mensagem_erro_cnpj = "Erro: CNPJ não está ativo ou não foi encontrado."


        if not validar_telefone(dados_form['telefone']):
            mensagem_erro_telefone = "Erro: Telefone inválido. Deve ter 10 ou 11 dígitos."

        if not validar_email(dados_form['email']):
            mensagem_erro_email = "Erro: E-mail inválido."


        if dados_form['numero'] and not re.match(r'^[a-zA-Z0-9]+$', dados_form['numero']):
            mensagem_erro_numero = "Erro: O número do endereço deve conter apenas letras e números."

        if (mensagem_erro_senha or mensagem_erro_email 
             or mensagem_erro_cnpj or mensagem_erro_telefone 
              or  mensagem_erro_numero): 
            return render_template('cadastro_instituicao.html',
                                   mensagem_erro_senha=mensagem_erro_senha,
                                   mensagem_erro_email=mensagem_erro_email,
                                   mensagem_erro_cnpj=mensagem_erro_cnpj,
                                   mensagem_erro_telefone=mensagem_erro_telefone,
                                   mensagem_erro_numero=mensagem_erro_numero, 
                                   dados_form=dados_form)
        else:
            try:
                conexao = conectar_bd()
                cursor = conexao.cursor()

          
                cursor.execute("SELECT id FROM instituicoes WHERE nome = %s", (dados_form['nome'],))
                if cursor.fetchone():
                    mensagem_erro_nome = "Erro: Já existe uma instituição cadastrada com este nome."
                    return render_template('cadastro_instituicao.html',
                                           mensagem_erro_senha=mensagem_erro_senha,
                                           mensagem_erro_nome=mensagem_erro_nome,
                                           mensagem_erro_email=mensagem_erro_email,
                                           mensagem_erro_cnpj=mensagem_erro_cnpj,
                                           mensagem_erro_telefone=mensagem_erro_telefone,
                                           mensagem_erro_numero=mensagem_erro_numero,
                                           dados_form=dados_form)

  
                cursor.execute("SELECT id FROM instituicoes WHERE email = %s", (dados_form['email'],))
                if cursor.fetchone():
                    mensagem_erro_email = "Erro: Este e-mail já está cadastrado."
                    return render_template('cadastro_instituicao.html',
                                           mensagem_erro_senha=mensagem_erro_senha,
                                           mensagem_erro_nome=mensagem_erro_nome,
                                           mensagem_erro_email=mensagem_erro_email,
                                           mensagem_erro_cnpj=mensagem_erro_cnpj,
                                           mensagem_erro_telefone=mensagem_erro_telefone,
                                           mensagem_erro_numero=mensagem_erro_numero,
                                           dados_form=dados_form)

            

                cursor.execute("SELECT id FROM instituicoes WHERE cnpj = %s", (re.sub(r'\D', '', dados_form['cnpj']),))
                if cursor.fetchone():
                    mensagem_erro_cnpj = "Erro: Este CNPJ já está cadastrado."
                    return render_template('cadastro_instituicao.html',
                                           mensagem_erro_senha=mensagem_erro_senha,
                                           mensagem_erro_nome=mensagem_erro_nome,
                                           mensagem_erro_email=mensagem_erro_email,
                                           mensagem_erro_cnpj=mensagem_erro_cnpj,
                                           mensagem_erro_telefone=mensagem_erro_telefone,
                                           mensagem_erro_numero=mensagem_erro_numero,
                                           dados_form=dados_form)


                cursor.execute("SELECT id FROM instituicoes WHERE telefone = %s", (re.sub(r'\D', '', dados_form['telefone']),))
                if cursor.fetchone():
                    mensagem_erro_telefone = "Erro: Este telefone já está cadastrado."
                    return render_template('cadastro_instituicao.html',
                                           mensagem_erro_senha=mensagem_erro_senha,
                                           mensagem_erro_nome=mensagem_erro_nome,
                                           mensagem_erro_email=mensagem_erro_email,
                                           mensagem_erro_cnpj=mensagem_erro_cnpj,
                                           mensagem_erro_telefone=mensagem_erro_telefone,
                                           mensagem_erro_numero=mensagem_erro_numero,
                                           dados_form=dados_form)


                dados = (
                    dados_form['nome'],
                    re.sub(r'\D', '', dados_form['cnpj']), 
                    dados_form['endereco'],
                    dados_form['numero'], 
                    dados_form['email'],
                    re.sub(r'\D', '', dados_form['telefone']), 
                    generate_password_hash(senha)
                )
                sql = """
                    INSERT INTO instituicoes
                    (nome, cnpj, endereco, numero, email, telefone, senha)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql, dados)
                conexao.commit()
                return "Instituição cadastrada com sucesso!"

            except mysql.connector.Error as err:
                return f"Erro de banco de dados: {err}"
            except Exception as e:
                return f"Erro inesperado: {e}"
            finally:
                if 'conexao' in locals() and conexao.is_connected():
                    cursor.close()
                    conexao.close()

    return render_template('cadastro_instituicao.html',
                           mensagem_erro_senha=mensagem_erro_senha,
                           mensagem_erro_nome=mensagem_erro_nome,
                           mensagem_erro_email=mensagem_erro_email,
                           mensagem_erro_cnpj=mensagem_erro_cnpj,
                           mensagem_erro_telefone=mensagem_erro_telefone,
                           mensagem_erro_numero=mensagem_erro_numero, # Passa a mensagem de erro para o template
                           dados_form=dados_form)

import time
import os

@instituicao_bp.route("/editar_perfil", methods=["GET", "POST"])
@login_required("instituicao")
def editar_perfil():
    conexao = conectar_bd()
    cursor = conexao.cursor(dictionary=True)
    user_id = session["user_id"]
    
    if request.method == "POST":
        endereco = request.form["endereco"]
        email = request.form["email"]
        telefone = request.form["telefone"]
        cnpj = request.form["cnpj"]
        foto = request.files.get("foto_perfil") 

        cursor.execute("SELECT foto FROM instituicoes WHERE id=%s", (user_id,))
        dados_atuais = cursor.fetchone()
        nome_foto = dados_atuais["foto"] 

        if foto and foto.filename != "":

            extensao = foto.filename.rsplit(".", 1)[1].lower()
            nome_foto = f"inst_{user_id}_{int(time.time())}.{extensao}"
            
   
            pasta_destino = os.path.join("static", "fotos_instituicoes")
            if not os.path.exists(pasta_destino):
                os.makedirs(pasta_destino)
            
            caminho = os.path.join(pasta_destino, nome_foto)

            if dados_atuais["foto"]:
                caminho_antigo = os.path.join(pasta_destino, dados_atuais["foto"])
                if os.path.exists(caminho_antigo):
                    os.remove(caminho_antigo)

            foto.save(caminho)


        sql = "UPDATE instituicoes SET endereco=%s, email=%s, telefone=%s, cnpj=%s, foto=%s WHERE id=%s"
        cursor.execute(sql, (endereco, email, telefone, cnpj, nome_foto, user_id))
        conexao.commit()

        flash("Perfil atualizado com sucesso!", "success")
        return redirect(url_for("instituicao.editar_perfil"))

    cursor.execute("SELECT * FROM instituicoes WHERE id=%s", (user_id,))
    instituicao = cursor.fetchone()
    cursor.close()
    conexao.close()

    return render_template("editar_perfil_instituicao.html", instituicao=instituicao)