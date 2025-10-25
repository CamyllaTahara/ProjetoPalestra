from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils.auth import login_required
import mysql.connector

gerenciar_palestrantes_bp = Blueprint("gerenciar_palestrantes", __name__)

# Conexão com o banco de dados
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="palestra"
    )

# LISTAR todos os palestrantes
@gerenciar_palestrantes_bp.route("/gerenciar_palestrantes")
@login_required("administrador")  # ✅ CORRIGIDO: administrador, não palestrante!
def listar_palestrantes():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM palestrantes ORDER BY nome_completo")
        palestrantes = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template("listar_palestrantes.html", palestrantes=palestrantes)
    except Exception as e:
        flash(f"Erro ao listar palestrantes: {e}", "danger")
        return redirect(url_for('login_administrador.painel_administrador'))

# CRIAR novo palestrante
@gerenciar_palestrantes_bp.route("/gerenciar_palestrantes/novo", methods=["GET", "POST"])
@login_required("administrador")
def criar_palestrante():
    if request.method == "POST":
        nome_completo = request.form.get('nome_completo')
        cpf = request.form.get('cpf')
        email = request.form.get('email')
        telefone = request.form.get('telefone')
        
        # Validações básicas
        if not nome_completo or not email:
            flash("Nome e e-mail são obrigatórios!", "danger")
            return render_template("form_palestrante.html")
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            sql = """
                INSERT INTO palestrantes (nome_completo, cpf, email, telefone)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(sql, (nome_completo, cpf, email, telefone))
            conn.commit()
            cursor.close()
            conn.close()
            
            flash("Palestrante cadastrado com sucesso!", "success")
            return redirect(url_for('gerenciar_palestrantes.listar_palestrantes'))
        
        except mysql.connector.IntegrityError:
            flash("Erro: CPF ou e-mail já cadastrado!", "danger")
            return render_template("form_palestrante.html")
        except Exception as e:
            flash(f"Erro ao cadastrar palestrante: {e}", "danger")
            return render_template("form_palestrante.html")
    
    # GET - exibe o formulário vazio
    return render_template("form_palestrante.html", palestrante=None)

# EDITAR palestrante existente
@gerenciar_palestrantes_bp.route("/gerenciar_palestrantes/<int:id>/editar", methods=["GET", "POST"])
@login_required("administrador")  # ✅ CORRIGIDO
def editar_palestrante(id):  # ✅ CORRIGIDO: nome da função estava errado (editar_instituicao)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == "POST":
        nome_completo = request.form.get('nome_completo')
        cpf = request.form.get('cpf')
        email = request.form.get('email')
        telefone = request.form.get('telefone')
        
        # Validações básicas
        if not nome_completo or not email:
            flash("Nome e e-mail são obrigatórios!", "danger")
            cursor.execute("SELECT * FROM palestrantes WHERE id = %s", (id,))
            palestrante = cursor.fetchone()
            cursor.close()
            conn.close()
            return render_template("form_palestrante.html", palestrante=palestrante)
        
        try:
            sql = """
                UPDATE palestrantes 
                SET nome_completo = %s, cpf = %s, email = %s, telefone = %s
                WHERE id = %s
            """
            # ✅ CORRIGIDO: removida vírgula extra antes do WHERE
            cursor.execute(sql, (nome_completo, cpf, email, telefone, id))
            conn.commit()
            cursor.close()
            conn.close()
            
            flash("Palestrante atualizado com sucesso!", "success")
            return redirect(url_for('gerenciar_palestrantes.listar_palestrantes'))
        
        except Exception as e:
            flash(f"Erro ao atualizar palestrante: {e}", "danger")
            cursor.execute("SELECT * FROM palestrantes WHERE id = %s", (id,))
            palestrante = cursor.fetchone()
            cursor.close()
            conn.close()
            return render_template("form_palestrante.html", palestrante=palestrante)
    
    # GET - busca os dados do palestrante e exibe o formulário preenchido
    cursor.execute("SELECT * FROM palestrantes WHERE id = %s", (id,))
    palestrante = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not palestrante:
        flash("Palestrante não encontrado!", "danger")
        return redirect(url_for('gerenciar_palestrantes.listar_palestrantes'))
    
    return render_template("form_palestrante.html", palestrante=palestrante)

# REMOVER palestrante
@gerenciar_palestrantes_bp.route("/gerenciar_palestrantes/<int:id>/remover", methods=["POST"])
@login_required("administrador")  # ✅ CORRIGIDO
def remover_palestrante(id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verifica se o palestrante existe antes de deletar
        cursor.execute("SELECT id FROM palestrantes WHERE id = %s", (id,))
        if not cursor.fetchone():
            flash("Palestrante não encontrado!", "danger")
            return redirect(url_for('gerenciar_palestrantes.listar_palestrantes'))
        
        cursor.execute("DELETE FROM palestrantes WHERE id = %s", (id,))
        conn.commit()
        cursor.close()
        conn.close()
        
        flash("Palestrante removido com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao remover palestrante: {e}", "danger")
    
    return redirect(url_for('gerenciar_palestrantes.listar_palestrantes'))