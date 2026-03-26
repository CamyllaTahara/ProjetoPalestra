# views/instituicao_views.py
from flask import current_app, render_template, request, Blueprint, redirect, url_for
from werkzeug.security import generate_password_hash
import re
from models.instituicao import conectar_bd
import mysql.connector
import os  # Para manipulação de arquivos
from flask import session
from utils.security import login_required
import time 
 

palestrante_bp = Blueprint('palestrante', __name__)

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

# Pasta para salvar os currículos (certifique-se de criar esta pasta)
UPLOAD_FOLDER = 'uploads_curriculos'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@palestrante_bp.route('/cadastro_palestrante', methods=['GET', 'POST'])
def cadastro_palestrante():
    mensagem_erro_senha = None
    mensagem_erro_nome = None
    mensagem_erro_email = None
    mensagem_erro_cpf = None
    mensagem_erro_telefone = None
    mensagem_erro_curriculo = None
    dados_form = {}

    if request.method == 'POST':
        senha = request.form['senha']
        dados_form['nome_completo'] = request.form.get('nome', '')  # Use 'nome' aqui
        dados_form['cpf'] = request.form.get('cpf', '')
        dados_form['email'] = request.form.get('email', '')
        dados_form['telefone'] = request.form.get('telefone', '')
        dados_form['anos_experiencia'] = request.form.get('anos_experiencia', '')
        dados_form['ramo_atividade'] = request.form.get('ramo_atividade', '')
        curriculo = request.files.get('curriculo')

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

        # Validação do telefone
        if not validar_telefone(dados_form['telefone']):
            mensagem_erro_telefone = "Erro: Telefone inválido. Deve ter 10 ou 11 dígitos."

        # Validação do e-mail
        if not validar_email(dados_form['email']):
            mensagem_erro_email = "Erro: E-mail inválido."

        # Validação do currículo
        curriculo_filename = None
        if curriculo:
            if curriculo.filename == '':
                mensagem_erro_curriculo = "Erro: Nenhum arquivo de currículo selecionado."
            elif not curriculo.filename.lower().endswith('.pdf'):
                mensagem_erro_curriculo = "Erro: Por favor, envie um arquivo PDF."
            else:
                # Salvar o currículo com um nome seguro
                filename = os.path.join(UPLOAD_FOLDER, f"{dados_form['nome_completo']}.pdf") # Nomear pelo CPF
                try:
                    curriculo.save(filename)
                    curriculo_filename = filename  # Salvar o caminho para o banco de dados
                except Exception as e:
                    mensagem_erro_curriculo = f"Erro ao salvar o currículo: {e}"
        else:
            mensagem_erro_curriculo = "Erro: O currículo é obrigatório." # Tornando o currículo obrigatório

        if (mensagem_erro_senha or mensagem_erro_email or mensagem_erro_cpf or
                mensagem_erro_telefone or mensagem_erro_nome or mensagem_erro_curriculo):
            return render_template('cadastro_palestrante.html',
                                   mensagem_erro_senha=mensagem_erro_senha,
                                   mensagem_erro_email=mensagem_erro_email,
                                   mensagem_erro_cpf=mensagem_erro_cpf,
                                   mensagem_erro_telefone=mensagem_erro_telefone,
                                   mensagem_erro_curriculo=mensagem_erro_curriculo,
                                   dados_form=dados_form)
        else:
            try:
                print("Tentando conectar ao banco de dados...")
                conexao = conectar_bd()
                print("Conexão bem-sucedida!")
                cursor = conexao.cursor()

                # Verificar se o e-mail já existe
                cursor.execute("SELECT id FROM palestrantes WHERE email = %s", (dados_form['email'],))
                if cursor.fetchone():
                    mensagem_erro_email = "Erro: Este e-mail já está cadastrado."
                    return render_template('cadastro_palestrante.html',
                    mensagem_erro_senha=mensagem_erro_senha,
                    mensagem_erro_email=mensagem_erro_email,
                    mensagem_erro_cpf=mensagem_erro_cpf,
                    mensagem_erro_telefone=mensagem_erro_telefone,
                    mensagem_erro_curriculo=mensagem_erro_curriculo,
                    dados_form=dados_form)

                # Verificar se o CPF já está cadastrado
                cursor.execute("SELECT id FROM palestrantes WHERE cpf = %s", (re.sub(r'\D', '', dados_form['cpf']),))
                if cursor.fetchone():
                    mensagem_erro_cpf = "Erro: Este CPF já está cadastrado."
                    return render_template('cadastro_palestrante.html',
                    mensagem_erro_senha=mensagem_erro_senha,
                    mensagem_erro_email=mensagem_erro_email,
                    mensagem_erro_cpf=mensagem_erro_cpf,
                    mensagem_erro_telefone=mensagem_erro_telefone,
                    mensagem_erro_curriculo=mensagem_erro_curriculo,
                    dados_form=dados_form)

                # Verificar se o telefone já está cadastrado
                cursor.execute("SELECT id FROM palestrantes WHERE telefone = %s", (re.sub(r'\D', '', dados_form['telefone']),))
                if cursor.fetchone():
                    mensagem_erro_telefone = "Erro: Este telefone já está cadastrado."
                    return render_template('cadastro_palestrante.html',
                    mensagem_erro_senha=mensagem_erro_senha,
                    mensagem_erro_email=mensagem_erro_email,
                    mensagem_erro_cpf=mensagem_erro_cpf,
                    mensagem_erro_telefone=mensagem_erro_telefone,
                    mensagem_erro_curriculo=mensagem_erro_curriculo,
                    dados_form=dados_form)
                

                # Se não houver erros, cadastrar o palestrante
                dados = (
                    dados_form['nome_completo'],
                    re.sub(r'\D', '', dados_form['cpf']),
                    dados_form['anos_experiencia'],
                    dados_form['ramo_atividade'],
                    curriculo_filename,  # Salvar o caminho do arquivo
                    dados_form['email'],
                    re.sub(r'\D', '', dados_form['telefone']),
                    generate_password_hash(senha)
                )
                print(f"Tupla 'dados' ANTES da inserção: {dados}")
                sql = """
                    INSERT INTO palestrantes
                    (nome_completo, cpf, anos_experiencia, ramo_atividade, curriculo_pdf, email, telefone, senha)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                print("Dados a serem inseridos:", dados) # Imprima os dados que você está tentando salvar
                print("Query SQL:", sql) # Imprima a query SQL
                cursor.execute(sql, dados)
                conexao.commit()
                print("Dados inseridos com sucesso!")
                return "Palestrante cadastrado com sucesso!"

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

    return render_template('cadastro_palestrante.html',
                        mensagem_erro_senha=mensagem_erro_senha,
                        mensagem_erro_email=mensagem_erro_email,
                        mensagem_erro_cpf=mensagem_erro_cpf,
                        mensagem_erro_telefone=mensagem_erro_telefone,
                        mensagem_erro_curriculo=mensagem_erro_curriculo,
                        dados_form=dados_form)
                        

@palestrante_bp.route("/editar_perfil",methods=["GET","POST"])
@login_required("palestrante")
def editar_perfil():
    conexao=conectar_bd()
    cursor=conexao.cursor(dictionary=True)
    user_id=session["user_id"]
    
    if request.method == "POST":
        descricao=request.form["descricao"]
        ramo_atividade=request.form["ramo_atividade"]
        anos_experiencia=request.form["anos_experiencia"]
        email=request.form["email"]
        telefone=request.form["telefone"]
        foto=request.files.get("foto_perfil")  
        curriculo_pdf=request.files.get("curriculo_pdf")

        # NOVO
        nome_foto = None
        nome_curriculo = None
        
        cursor.execute("SELECT curriculo_pdf, foto FROM palestrantes WHERE id=%s",(user_id,))
        dados_atuais = cursor.fetchone()

        if foto and foto.filename !="":
            extensao=foto.filename.rsplit(".",1)[1].lower()
            nome_foto=f"{user_id}_foto_{int(time.time())}.{extensao}"

            caminho = os.path.join("static", "fotos_palestrantes", nome_foto)

              # apagar foto antiga
            if dados_atuais["foto"]:
               foto_antiga = os.path.join("static","fotos_palestrantes",dados_atuais["foto"])
            if os.path.exists(foto_antiga):
             os.remove(foto_antiga)

            print("CAMINHO DA FOTO:", caminho)
            foto.save(caminho)


        if curriculo_pdf and curriculo_pdf.filename.endswith(".pdf"):
            nome_curriculo=f"{user_id}_curriculo.pdf"

            caminho = os.path.join(
        
        "uploads_curriculos",
        nome_curriculo
    )
            curriculo_pdf.save(caminho)


        # NOVO — buscar dados atuais
        
        cursor.execute("SELECT curriculo_pdf, foto FROM palestrantes WHERE id=%s",(user_id,))
        dados_atuais = cursor.fetchone()


        # NOVO — manter currículo antigo se não atualizar
        if nome_curriculo is None:
            nome_curriculo = dados_atuais["curriculo_pdf"]


        # NOVO — manter foto antiga se não atualizar
        if nome_foto is None:
            nome_foto = dados_atuais["foto"]


        sql = "UPDATE palestrantes set descricao = %s,ramo_atividade=%s, curriculo_pdf=%s,anos_experiencia=%s, email=%s, telefone=%s, foto=%s WHERE id =%s"
        cursor.execute(sql,(descricao,ramo_atividade,nome_curriculo,anos_experiencia,email,telefone,nome_foto,user_id))
        conexao.commit()

        return redirect(url_for("palestrante.editar_perfil"))

    cursor.execute("SELECT * FROM palestrantes WHERE id=%s",(user_id,))
    palestrante = cursor.fetchone()

    cursor.close()
    conexao.close()

    print(palestrante)

    return render_template("editar_perfil_palestrante.html", palestrante=palestrante)