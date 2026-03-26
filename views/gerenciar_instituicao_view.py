from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils.auth import login_required
import mysql.connector

gerenciar_instituicoes_bp = Blueprint("gerenciar_instituicoes", __name__)

# Conexão com o banco de dados
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="palestra"
    )

# LISTAR todas as instituições
@gerenciar_instituicoes_bp.route("/gerenciar_instituicoes")
@login_required("administrador")
def listar_instituicoes():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM instituicoes ORDER BY nome")
        instituicoes = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template("listar_instituicoes.html", instituicoes=instituicoes)
    except Exception as e:
        flash(f"Erro ao listar instituições: {e}", "danger")
        return redirect(url_for('login_administrador.painel_administrador'))

# CRIAR nova instituição
@gerenciar_instituicoes_bp.route("/gerenciar_instituicoes/nova", methods=["GET", "POST"])
@login_required("administrador")
def criar_instituicao():
    if request.method == "POST":
        nome = request.form.get('nome')
        cnpj = request.form.get('cnpj')
        email = request.form.get('email')
        telefone = request.form.get('telefone')
        endereco = request.form.get('endereco')
        
        # Validações básicas
        if not nome or not email:
            flash("Nome e e-mail são obrigatórios!", "danger")
            return render_template("form_instituicao.html")
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            sql = """
                INSERT INTO instituicoes (nome, cnpj, email, telefone, endereco)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (nome, cnpj, email, telefone, endereco))
            conn.commit()
            cursor.close()
            conn.close()
            
            flash("Instituição cadastrada com sucesso!", "success")
            return redirect(url_for('gerenciar_instituicoes.listar_instituicoes'))
        
        except mysql.connector.IntegrityError:
            flash("Erro: CNPJ ou e-mail já cadastrado!", "danger")
            return render_template("form_instituicao.html")
        except Exception as e:
            flash(f"Erro ao cadastrar instituição: {e}", "danger")
            return render_template("form_instituicao.html")
    
    # GET - exibe o formulário vazio
    return render_template("form_instituicao.html", instituicao=None)

# EDITAR instituição existente
@gerenciar_instituicoes_bp.route("/gerenciar_instituicoes/<int:id>/editar", methods=["GET", "POST"])
@login_required("administrador")
def editar_instituicao(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == "POST":
        nome = request.form.get('nome')
        cnpj = request.form.get('cnpj')
        email = request.form.get('email')
        telefone = request.form.get('telefone')
        endereco = request.form.get('endereco')
        
        # Validações básicas
        if not nome or not email:
            flash("Nome e e-mail são obrigatórios!", "danger")
            cursor.execute("SELECT * FROM instituicoes WHERE id = %s", (id,))
            instituicao = cursor.fetchone()
            cursor.close()
            conn.close()
            return render_template("form_instituicao.html", instituicao=instituicao)
        
        try:
            sql = """
                UPDATE instituicoes 
                SET nome = %s, cnpj = %s, email = %s, telefone = %s, endereco = %s
                WHERE id = %s
            """
            cursor.execute(sql, (nome, cnpj, email, telefone, endereco, id))
            conn.commit()
            cursor.close()
            conn.close()
            
            flash("Instituição atualizada com sucesso!", "success")
            return redirect(url_for('gerenciar_instituicoes.listar_instituicoes'))
        
        except Exception as e:
            flash(f"Erro ao atualizar instituição: {e}", "danger")
            cursor.execute("SELECT * FROM instituicoes WHERE id = %s", (id,))
            instituicao = cursor.fetchone()
            cursor.close()
            conn.close()
            return render_template("form_instituicao.html", instituicao=instituicao)
    
    # GET - busca os dados da instituição e exibe o formulário preenchido
    cursor.execute("SELECT * FROM instituicoes WHERE id = %s", (id,))
    instituicao = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not instituicao:
        flash("Instituição não encontrada!", "danger")
        return redirect(url_for('gerenciar_instituicoes.listar_instituicoes'))
    
    return render_template("form_instituicao.html", instituicao=instituicao)

# REMOVER instituição
@gerenciar_instituicoes_bp.route("/gerenciar_instituicoes/<int:id>/remover", methods=["POST"])
@login_required("administrador")
def remover_instituicao(id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verifica se a instituição existe antes de deletar
        cursor.execute("SELECT id FROM instituicoes WHERE id = %s", (id,))
        if not cursor.fetchone():
            flash("Instituição não encontrada!", "danger")
            return redirect(url_for('gerenciar_instituicoes.listar_instituicoes'))
        
        cursor.execute("DELETE FROM instituicoes WHERE id = %s", (id,))
        conn.commit()
        cursor.close()
        conn.close()
        
        flash("Instituição removida com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao remover instituição: {e}", "danger")
    
    return redirect(url_for('gerenciar_instituicoes.listar_instituicoes'))

# REATIVAR instituição
@gerenciar_instituicoes_bp.route("/gerenciar_instituicoes/<int:id>/reativar", methods=["POST"])
@login_required("administrador")
def reativar_instituicao(id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE instituicoes SET status = 'ativo' WHERE id = %s", (id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Instituição reativada com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao reativar instituição: {e}", "danger")
    return redirect(url_for('gerenciar_instituicoes.listar_instituicoes'))