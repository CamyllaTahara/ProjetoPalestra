from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from utils.auth import login_required
import mysql.connector
from datetime import datetime, timedelta

gerenciar_disponibilidades_bp = Blueprint("gerenciar_disponibilidades", __name__)

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="palestra"
    )

@gerenciar_disponibilidades_bp.route("/minhas_disponibilidades")
@login_required("palestrante")
def listar_disponibilidades():
    try:
        print(f"DEBUG 1 - Entrou na função listar_disponibilidades")
        print(f"DEBUG 2 - Session: {dict(session)}")
        
        palestrante_id = session['user_id']
        print(f"DEBUG 3 - palestrante_id: {palestrante_id}")
        
        conn = get_db_connection()
        print(f"DEBUG 4 - Conexão com BD estabelecida")
        
        cursor = conn.cursor(dictionary=True)
        print(f"DEBUG 5 - Cursor criado")
        
        cursor.execute("""
            SELECT id, data, horario_inicio, horario_fim, criado_em
            FROM disponibilidade_palestrantes
            WHERE palestrante_id = %s
            ORDER BY data DESC, horario_inicio
        """, (palestrante_id,))
        
        print(f"DEBUG 6 - Query executada")
        
        disponibilidades = cursor.fetchall()
        print(f"DEBUG 7 - Disponibilidades recuperadas: {len(disponibilidades)} registros")

        for disp in disponibilidades:
            if disp['horario_inicio']:
                h, m = divmod(int(disp['horario_inicio'].total_seconds()), 3600)
                m = m // 60
                disp['horario_inicio'] = f"{h:02d}:{m:02d}"
            if disp['horario_fim']:
                h, m = divmod(int(disp['horario_fim'].total_seconds()), 3600)
                m = m // 60
                disp['horario_fim'] = f"{h:02d}:{m:02d}"
        
        cursor.close()
        conn.close()
        print(f"DEBUG 8 - Cursor e conexão fechados")
        
        print(f"DEBUG 9 - Renderizando template...")
        return render_template("listar_disponibilidades.html", disponibilidades=disponibilidades)
    
    except Exception as e:
        print(f"DEBUG - ERRO na função: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        flash(f"Erro ao listar disponibilidades: {e}", "danger")
        return redirect(url_for('login_palestrante.painel_palestrante'))
    
    except Exception as e:
        flash(f"Erro ao listar disponibilidades: {e}", "danger")
        return redirect(url_for('login_palestrante.painel_palestrante'))

@gerenciar_disponibilidades_bp.route("/nova_disponibilidade", methods=["GET", "POST"])
@login_required("palestrante")
def criar_disponibilidade():
    if request.method == "POST":
        data = request.form.get('data')
        horario_inicio = request.form.get('horario_inicio')
        horario_fim = request.form.get('horario_fim')

        if not data or not horario_inicio or not horario_fim:
            flash("Todos os campos são obrigatórios", "danger")
            return render_template("form_disponibilidade.html")

        try:
            data_obj = datetime.strptime(data, '%Y-%m-%d')
            if data_obj.date() < datetime.now().date():
                flash("A data deve ser no futuro", "danger")
                return render_template("form_disponibilidade.html")
        except ValueError:
            flash("Formato de data inválido!", "danger")
            return render_template("form_disponibilidade.html")
        
        try: 
            inicio = datetime.strptime(horario_inicio, '%H:%M')
            fim = datetime.strptime(horario_fim, '%H:%M')

            if inicio >= fim:
                flash("Horário de inicio deve ser menor que o horário de fim", "danger")
                return render_template("form_disponibilidade.html")
        except ValueError:
            flash("Formato de horário inválido!", "danger")
            return render_template("form_disponibilidade.html")
        
        try:
            palestrante_id = session['user_id']
            conn = get_db_connection()
            cursor = conn.cursor()

            sql = """ 
               INSERT INTO disponibilidade_palestrantes
               (palestrante_id, data, horario_inicio, horario_fim)
               VALUES (%s, %s, %s, %s)
            """
            cursor.execute(sql, (palestrante_id, data, horario_inicio, horario_fim))
            conn.commit()
            cursor.close()
            conn.close()

            flash("Disponibilidade adicionada com sucesso!", "success")
            return redirect(url_for('gerenciar_disponibilidades.listar_disponibilidades'))
        
        except mysql.connector.IntegrityError:
            flash("Você já tem uma disponibilidade nessa data e horário", "danger")
            return render_template("form_disponibilidade.html")
        
        except Exception as e:
            flash(f"Erro ao adicionar disponibilidade: {e}", "danger")
            return render_template("form_disponibilidade.html")
        
    return render_template("form_disponibilidade.html", disponibilidade=None)

@gerenciar_disponibilidades_bp.route("/disponibilidade/<int:id>/editar", methods=["GET", "POST"])
@login_required("palestrante")
def editar_disponibilidade(id):
    palestrante_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True) 

    cursor.execute("""
       SELECT * FROM disponibilidade_palestrantes
       WHERE id = %s AND palestrante_id = %s
    """, (id, palestrante_id))
    disponibilidade = cursor.fetchone()

    if not disponibilidade:
        flash("Disponibilidade não encontrada", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('gerenciar_disponibilidades.listar_disponibilidades'))
    
    # Converter timedelta para string formatada (apenas para exibição no formulário)
    if disponibilidade['horario_inicio']:
        if not isinstance(disponibilidade['horario_inicio'], str):
            h, m = divmod(int(disponibilidade['horario_inicio'].total_seconds()), 3600)
            m = m // 60
            disponibilidade['horario_inicio'] = f"{h:02d}:{m:02d}"
    
    if disponibilidade['horario_fim']:
        if not isinstance(disponibilidade['horario_fim'], str):
            h, m = divmod(int(disponibilidade['horario_fim'].total_seconds()), 3600)
            m = m // 60
            disponibilidade['horario_fim'] = f"{h:02d}:{m:02d}"
    
    if request.method == "POST":
        data = request.form.get('data')
        horario_inicio = request.form.get('horario_inicio')
        horario_fim = request.form.get('horario_fim')

        if not data or not horario_inicio or not horario_fim:
            flash("Todos os campos são obrigatórios", 'danger')
            return render_template("form_disponibilidade.html", disponibilidade=disponibilidade)
        
        try:
            inicio = datetime.strptime(horario_inicio, '%H:%M')
            fim = datetime.strptime(horario_fim, '%H:%M')
            if inicio >= fim:
                flash("Horário de inicio deve ser menor que o de fim", "danger")
                return render_template("form_disponibilidade.html", disponibilidade=disponibilidade)
        except ValueError:
            flash("Formato de horário inválido", "danger")
            return render_template("form_disponibilidade.html", disponibilidade=disponibilidade)
        
        try:
            sql = """
               UPDATE disponibilidade_palestrantes
               SET data = %s, horario_inicio = %s, horario_fim = %s
               WHERE id = %s
            """
            cursor.execute(sql, (data, horario_inicio, horario_fim, id))
            conn.commit()
            cursor.close()
            conn.close()

            flash("Disponibilidade atualizada com sucesso", "success")
            return redirect(url_for('gerenciar_disponibilidades.listar_disponibilidades'))

        except Exception as e:
            flash(f"Erro ao atualizar disponibilidade: {e}", "danger")
            return render_template("form_disponibilidade.html", disponibilidade=disponibilidade)
        
    cursor.close()
    conn.close()
    return render_template("form_disponibilidade.html", disponibilidade=disponibilidade)

@gerenciar_disponibilidades_bp.route("/disponibilidade/<int:id>/remover", methods=["GET", "POST"])
@login_required("palestrante")
def remover_disponibilidade(id):
    palestrante_id = session['user_id']

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(""" 
           SELECT id FROM disponibilidade_palestrantes
           WHERE id = %s AND palestrante_id = %s
        """, (id, palestrante_id))
        
        if not cursor.fetchone():
            flash("Disponibilidade não encontrada!", 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('gerenciar_disponibilidades.listar_disponibilidades'))
        
        cursor.execute("DELETE FROM disponibilidade_palestrantes WHERE id = %s", (id,))
        flash("Disponibilidade removida com sucesso", "success")
        conn.commit()
        cursor.close()
        conn.close()
        

    except Exception as e:
        flash(f"Erro ao remover disponibilidade: {e}", "danger")

    return redirect(url_for('gerenciar_disponibilidades.listar_disponibilidades'))
       