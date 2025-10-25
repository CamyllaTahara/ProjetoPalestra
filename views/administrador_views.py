# views/instituicao_views.py
from flask import render_template, request, Blueprint, redirect, url_for
from werkzeug.security import generate_password_hash
import re
from models.instituicao import conectar_bd
import mysql.connector
import os  # Para manipulação de arquivos

administrador_bp = Blueprint('administrador', __name__)

def cpf_valido(cpf):
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
    telefone = ''.join(filter(str.isdigit, telefone))
    return len(telefone) in (10, 11)

def validar_email(email):
    return '@' in email and '.' in email


@administrador_bp.route('/cadastro_administrador', methods=['GET', 'POST'])
def cadastro_administrador():
    mensagem_erro_senha = None
    mensagem_erro_email = None
    mensagem_erro_cpf = None
    dados_form = {}

    if request.method == 'POST':
        senha = request.form['senha']
        dados_form['nome_completo'] = request.form.get('nome', '')  # Use 'nome' aqui
        dados_form['cpf'] = request.form.get('cpf', '')
        dados_form['email'] = request.form.get('email', '')
        dados_form['cargo'] = request.form.get('cargo', '')

        # Validação do nome
        if not dados_form['nome_completo'].strip():
            mensagem_erro_nome = "Erro: O nome completo é obrigatório."

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

        # Validação do CPF
        if not cpf_valido(dados_form['cpf']):
            mensagem_erro_cpf = "Erro: CPF inválido."

        # Validação do e-mail
        if not validar_email(dados_form['email']):
            mensagem_erro_email = "Erro: E-mail inválido."

        if (mensagem_erro_senha or mensagem_erro_email or mensagem_erro_cpf 
                    ):
            return render_template('cadastro_administrador.html',
                                   mensagem_erro_senha=mensagem_erro_senha,
                                   mensagem_erro_email=mensagem_erro_email,
                                   mensagem_erro_cpf=mensagem_erro_cpf,
                                   dados_form=dados_form)
        else:
            try:
                print("Tentando conectar ao banco de dados...")
                conexao = conectar_bd()
                print("Conexão bem-sucedida!")
                cursor = conexao.cursor()
                
                # Verificar se o e-mail já existe
                cursor.execute("SELECT id FROM admins WHERE email = %s", (dados_form['email'],))
                if cursor.fetchone():
                    mensagem_erro_email = "Erro: Este e-mail já está cadastrado."
                    return render_template('cadastro_administrador.html',
                                           mensagem_erro_senha=mensagem_erro_senha,
                                           mensagem_erro_email=mensagem_erro_email,
                                           mensagem_erro_cpf=mensagem_erro_cpf,
                                           dados_form=dados_form)

                # Verificar se o CPF já está cadastrado
                cursor.execute("SELECT id FROM admins WHERE cpf = %s", (re.sub(r'\D', '', dados_form['cpf']),))
                if cursor.fetchone():
                    mensagem_erro_cpf = "Erro: Este CPF já está cadastrado."
                    return render_template('cadastro_administrador.html',
                                           mensagem_erro_senha=mensagem_erro_senha,
                                           mensagem_erro_email=mensagem_erro_email,
                                           mensagem_erro_cpf=mensagem_erro_cpf,
                                           dados_form=dados_form)

                # Se não houver erros, cadastrar o palestrante
                dados = (
                    dados_form['nome_completo'],
                    dados_form['email'],
                    re.sub(r'\D', '', dados_form['cpf']),
                    dados_form['cargo'],
                    generate_password_hash(senha)
                )
                print(f"Tupla 'dados' ANTES da inserção: {dados}")
                sql = """
                    INSERT INTO admins
                    (nome_completo, email, cpf, cargo, senha)
                    VALUES (%s, %s, %s, %s, %s)
                """
                print("Dados a serem inseridos:", dados) # Imprima os dados que você está tentando salvar
                print("Query SQL:", sql) # Imprima a query SQL
                cursor.execute(sql, dados)
                conexao.commit()
                print("Dados inseridos com sucesso!")
                return "Administrador cadastrado com sucesso!"

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
                    print("Conexão fechada.")

    return render_template('cadastro_administrador.html',
                           mensagem_erro_senha=mensagem_erro_senha,
                           mensagem_erro_email=mensagem_erro_email,
                           mensagem_erro_cpf=mensagem_erro_cpf,
                           dados_form=dados_form)


                             