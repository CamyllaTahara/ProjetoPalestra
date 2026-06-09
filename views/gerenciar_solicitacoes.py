import os
from flask import Blueprint, render_template, request, redirect, send_file, url_for, flash, session
from utils import mail
from utils.security import login_required
import mysql.connector
from datetime import datetime, timedelta
from utils.mail import send_notification_email
from flask import current_app

from views.feed_views import buscar_lista_seguidores, buscar_lista_seguindo

gerenciar_solicitacoes_bp = Blueprint("gerenciar_solicitacoes", __name__)

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="palestra"
    )

@gerenciar_solicitacoes_bp.route("/listar_palestrantes", methods=["GET"])
@login_required("instituicao")
def listar_palestrantes():
    """Lista todos os palestrantes disponíveis para a instituição solicitar palestra."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT id, nome_completo, ramo_atividade, anos_experiencia, email, telefone
            FROM palestrantes
            ORDER BY nome_completo
        """)
        
        palestrantes = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return render_template("listar_palestrantes_instituicao.html", palestrantes=palestrantes)
    
    except Exception as e:
        flash(f"Erro ao listar palestrantes: {e}", "danger")
        return redirect(url_for('login_instituicao.painel_instituicao'))

@gerenciar_solicitacoes_bp.route("/perfil_palestrante/<int:palestrante_id>", methods=["GET"])
@login_required("instituicao")
def perfil_palestrante(palestrante_id):
    """Exibe o perfil de um palestrante com suas disponibilidades."""
    try:
        user_id = session.get('user_id')
        user_type = session.get('user_type')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, nome_completo, ramo_atividade, anos_experiencia, email, telefone, curriculo_pdf,descricao,foto
            FROM palestrantes
            WHERE id = %s
        """, (palestrante_id,))
        
        palestrante = cursor.fetchone()
        
        if not palestrante:
            flash("Palestrante não encontrado", "danger")
            return redirect(url_for('gerenciar_solicitacoes.listar_palestrantes'))
        
        cursor.execute("SELECT COUNT(*) as total FROM seguidores WHERE seguido_tipo='palestrante' AND seguido_id=%s", (palestrante_id,))
        total_seguidores = cursor.fetchone()['total']
        cursor.execute("SELECT COUNT(*) as total FROM seguidores WHERE seguidor_tipo='palestrante' AND seguidor_id=%s", (palestrante_id,))
        total_seguindo = cursor.fetchone()['total']

        
        ja_segue = False
        if user_id and user_type:
         cursor.execute("""SELECT id FROM seguidores WHERE seguidor_tipo=%s AND seguidor_id=%s 
                          AND seguido_tipo='palestrante' AND seguido_id=%s""",
                       (user_type, user_id, palestrante_id))
        ja_segue = cursor.fetchone() is not None
        
        

        cursor.execute("""
            SELECT id, data, horario_inicio, horario_fim
            FROM disponibilidade_palestrantes
            WHERE palestrante_id = %s AND data >= CURDATE()
            ORDER BY data, horario_inicio
        """, (palestrante_id,))
        disponibilidades = cursor.fetchall()
        if disponibilidades:
         print(f"DEBUG: Tipo da data: {type(disponibilidades[0]['horario_inicio'])}")
         print(f"DEBUG: Valor Bruto da Data: {disponibilidades[0]['horario_inicio']}")

        ja_segue = False
        if user_id and user_type:
         cursor.execute("""SELECT id FROM seguidores WHERE seguidor_tipo=%s AND seguidor_id=%s 
                          AND seguido_tipo='palestrante' AND seguido_id=%s""",
                       (user_type, user_id, palestrante_id))
        ja_segue = cursor.fetchone() is not None


        lista_seguidores = buscar_lista_seguidores(cursor, 'palestrante', palestrante_id)
        lista_seguindo = buscar_lista_seguindo(cursor, 'palestrante', palestrante_id)
        cursor.close()
        conn.close()

        

        
        return render_template("perfil_palestrante.html", total_seguidores=total_seguidores,
                           total_seguindo=total_seguindo, ja_segue=ja_segue,
                             perfil=palestrante, 
                             disponibilidades=disponibilidades,lista_seguidores=lista_seguidores, lista_seguindo=lista_seguindo,
                             user_type=session.get('user_type'))
    
    except Exception as e:
        flash(f"Erro ao carregar perfil: {e}", "danger")
        return redirect(url_for('gerenciar_solicitacoes.listar_palestrantes'))



    
@gerenciar_solicitacoes_bp.route("/download_curriculo/<int:palestrante_id>", methods=["GET"])
@login_required("instituicao")
def download_curriculo(palestrante_id):
    """Permite à instituição logada baixar o PDF do currículo do palestrante."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT nome_completo, curriculo_pdf
            FROM palestrantes
            WHERE id = %s
        """, (palestrante_id,))
        
        palestrante = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
   
        if not palestrante or not palestrante['curriculo_pdf']:
            flash("Currículo não encontrado ou não cadastrado.", "danger")
            return redirect(url_for('gerenciar_solicitacoes.perfil_palestrante', palestrante_id=palestrante_id))

        curriculo_pdf_nome = palestrante['curriculo_pdf']
        caminho_arquivo = os.path.join(
    current_app.root_path,
    "uploads_curriculos",
    curriculo_pdf_nome
)
        print(f"DEBUG: Tentando encontrar o arquivo em: {os.path.abspath(caminho_arquivo)}")

        nome_download = f"Curriculo_{palestrante['nome_completo'].replace(' ', '_').replace('.', '')}.pdf"
        

        return send_file(os.path.abspath(caminho_arquivo), 
                         as_attachment=True, 
                         download_name=nome_download,
                         mimetype='application/pdf')

    except FileNotFoundError:
        flash("Arquivo de currículo não foi encontrado no servidor. Verifique se o arquivo existe em static/curriculos.", "danger")
        return redirect(url_for('gerenciar_solicitacoes.perfil_palestrante', palestrante_id=palestrante_id))
        
    except Exception as e:
        flash(f"Erro ao processar o download: {e}", "danger")
        return redirect(url_for('gerenciar_solicitacoes.perfil_palestrante', palestrante_id=palestrante_id))
    

@gerenciar_solicitacoes_bp.route("/ver_curriculo/<int:palestrante_id>")
@login_required("instituicao")
def ver_curriculo(palestrante_id):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT curriculo_pdf
        FROM palestrantes
        WHERE id=%s
    """, (palestrante_id,))

    palestrante = cursor.fetchone()

    cursor.close()
    conn.close()

    if not palestrante or not palestrante["curriculo_pdf"]:
        flash("Currículo não encontrado.")
        return redirect(url_for("gerenciar_solicitacoes.listar_palestrantes"))
    
    nome_arquivo = os.path.basename (palestrante["curriculo_pdf"])
    caminho = os.path.join(
        current_app.root_path,
        "uploads_curriculos",
        nome_arquivo)

    return send_file(caminho, mimetype="application/pdf")

@gerenciar_solicitacoes_bp.route("/solicitar_palestra/<int:palestrante_id>", methods=["GET", "POST"])
@login_required("instituicao")
def solicitar_palestra(palestrante_id):
    """Cria uma solicitação de palestra para um palestrante."""
    instituicao_id = session['user_id']
    
    if request.method == "POST":
        titulo = request.form.get('titulo')
        descricao = request.form.get('descricao')
        endereco_palestra = request.form.get('endereco_palestra')
        data_proposta = request.form.get('data_proposta')
        horario_proposta = request.form.get('horario_proposta')
        
        
        if not titulo or not descricao:
            flash("Título e descrição são obrigatórios", "danger")
            return redirect(url_for('gerenciar_solicitacoes.solicitar_palestra', palestrante_id=palestrante_id))
        
        try:
            data_obj = datetime.strptime(data_proposta, '%Y-%m-%d')
            if data_obj.date() <= datetime.now().date():
                flash("A data deve ser no futuro", "danger")
                return redirect(url_for('gerenciar_solicitacoes.solicitar_palestra', palestrante_id=palestrante_id))
        except ValueError:
            flash("Formato de data inválido", "danger")
            return redirect(url_for('gerenciar_solicitacoes.solicitar_palestra', palestrante_id=palestrante_id))
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            prazo_expiracao = datetime.now() + timedelta(days=3)
            
           
            cursor.execute("""
                SELECT id FROM solicitacoes_palestras
                WHERE instituicao_id = %s 
                AND palestrante_id = %s 
                AND data_proposta = %s 
                AND horario_proposta = %s
                AND status = 'pendente'
            """, (instituicao_id, palestrante_id, data_proposta, horario_proposta))
            
            if cursor.fetchone():
                flash("Você já solicitou uma palestra para esse palestrante nesse horário", "danger")
                cursor.close()
                conn.close()
                return redirect(url_for('gerenciar_solicitacoes.solicitar_palestra', palestrante_id=palestrante_id))
         
            sql = """
                INSERT INTO solicitacoes_palestras 
                (instituicao_id, palestrante_id, titulo, descricao, data_proposta, horario_proposta, status, endereco_palestra, prazo_expiracao)
                VALUES (%s, %s, %s, %s, %s, %s, 'pendente', %s, %s)
            """
            cursor.execute(sql, (instituicao_id, palestrante_id, titulo, descricao, data_proposta, horario_proposta, endereco_palestra, prazo_expiracao))
            conn.commit() 

            cursor.execute("""
                SELECT email, nome_completo 
                FROM palestrantes 
                WHERE id = %s
            """, (palestrante_id,))
            palestrante = cursor.fetchone()
            

            cursor.execute("""
                SELECT nome, email 
                FROM instituicoes 
                WHERE id = %s
            """, (instituicao_id,))
            instituicao = cursor.fetchone()
            

            data_formatada = data_obj.strftime('%d/%m/%Y')
            data_expiracao_formatada = prazo_expiracao.strftime('%d/%m/%Y às %H:%M')
            
            from utils.mail import send_notification_email
            

            subject_palestrante = f"📬 Nova Solicitação de Palestra: {titulo}"
            body_palestrante = f"""
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

            
                    <tr>
                        <td align="center" style="padding-bottom: 30px;">
                            <h1 style="margin:0; font-size:1.6rem; color:#00d2ff; letter-spacing:-0.5px;">✦ PalestraApp</h1>
                            <p style="margin:6px 0 0; color:#94a3b8; font-size:0.85rem;">Sistema de Agendamento de Palestras</p>
                        </td>
                    </tr>

    
                    <tr>
                        <td style="background: linear-gradient(135deg, #0f172a, #1e293b); border: 1px solid rgba(0,210,255,0.15); border-radius: 16px; padding: 35px;">
                            <table width="100%" cellpadding="0" cellspacing="0">

                                <tr>
                                    <td align="center" style="padding-bottom: 25px; border-bottom: 1px solid rgba(255,255,255,0.07);">
                                        <div style="background: rgba(0,210,255,0.1); border: 1px solid rgba(0,210,255,0.3); border-radius: 50px; display:inline-block; padding: 10px 22px; margin-bottom: 15px;">
                                            <span style="color:#00d2ff; font-size:0.85rem; font-weight:600; letter-spacing:1px;">📋 NOVA SOLICITAÇÃO</span>
                                        </div>
                                        <h2 style="margin:0; color:#f8fafc; font-size:1.4rem;">Olá, {palestrante['nome_completo']}!</h2>
                                        <p style="margin:10px 0 0; color:#94a3b8; font-size:0.95rem; line-height:1.6;">
                                            Você recebeu uma nova solicitação de palestra.
                                        </p>
                                    </td>
                                </tr>

                     
                                <tr>
                                    <td style="padding-top: 25px; padding-bottom: 20px;">
                                        <p style="margin:0 0 12px; color:#94a3b8; font-size:0.75rem; text-transform:uppercase; letter-spacing:1px; font-weight:600;">Detalhes da Solicitação</p>

                                        <table width="100%" cellpadding="0" cellspacing="0">
                                            <tr>
                                                <td style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">🏢 Instituição</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">{instituicao['nome']}</strong>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">📋 Título</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">{titulo}</strong>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">📅 Data</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">{data_formatada}</strong>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">🕐 Horário</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">{horario_proposta}</strong>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">📍 Local</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">{endereco_palestra}</strong>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 10px 0;">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">📝 Descrição</span><br>
                                                    <span style="color:#cbd5e1; font-size:0.95rem; line-height:1.6;">{descricao}</span>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>

                                <tr>
                                    <td style="padding-bottom: 25px;">
                                        <div style="background: rgba(245,158,11,0.06); border-left: 3px solid #f59e0b; border-radius: 8px; padding: 15px 18px;">
                                            <p style="margin:0 0 4px; color:#f59e0b; font-size:0.8rem; font-weight:600; text-transform:uppercase; letter-spacing:1px;">⚠️ Prazo de Resposta</p>
                                            <p style="margin:0; color:#cbd5e1; font-size:0.9rem; line-height:1.6;">
                                                Esta solicitação expira em <strong style="color:#f8fafc;">{data_expiracao_formatada}</strong>. Acesse o sistema para aceitar ou recusar.
                                            </p>
                                        </div>
                                    </td>
                                </tr>

                 
                                <tr>
                                    <td align="center" style="padding-bottom: 10px;">
                                        <a href="http://localhost:5000"
                                           style="display:inline-block; background: linear-gradient(135deg, #00d2ff, #0099cc); color:#000000; font-weight:700; font-size:0.95rem; text-decoration:none; padding: 14px 35px; border-radius: 10px;">
                                            Acessar o Sistema →
                                        </a>
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
            
            email_palestrante_enviado = send_notification_email(
                recipient=palestrante['email'],
                subject=subject_palestrante,
                body=body_palestrante
            )

            subject_instituicao = f"✅ Solicitação Enviada: {titulo}"
            body_instituicao =  f"""
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

                
                    <tr>
                        <td align="center" style="padding-bottom: 30px;">
                            <h1 style="margin:0; font-size:1.6rem; color:#00d2ff; letter-spacing:-0.5px;">✦ PalestraApp</h1>
                            <p style="margin:6px 0 0; color:#94a3b8; font-size:0.85rem;">Sistema de Agendamento de Palestras</p>
                        </td>
                    </tr>

                  
                    <tr>
                        <td style="background: linear-gradient(135deg, #0f172a, #1e293b); border: 1px solid rgba(0,210,255,0.15); border-radius: 16px; padding: 35px;">
                            <table width="100%" cellpadding="0" cellspacing="0">

                          
                                <tr>
                                    <td align="center" style="padding-bottom: 25px; border-bottom: 1px solid rgba(255,255,255,0.07);">
                                        <div style="background: rgba(0,210,255,0.1); border: 1px solid rgba(0,210,255,0.3); border-radius: 50px; display:inline-block; padding: 10px 22px; margin-bottom: 15px;">
                                            <span style="color:#00d2ff; font-size:0.85rem; font-weight:600; letter-spacing:1px;">📋 NOVA SOLICITAÇÃO</span>
                                        </div>
                                        <h2 style="margin:0; color:#f8fafc; font-size:1.4rem;">Olá, {palestrante['nome_completo']}!</h2>
                                        <p style="margin:10px 0 0; color:#94a3b8; font-size:0.95rem; line-height:1.6;">
                                            Você recebeu uma nova solicitação de palestra.
                                        </p>
                                    </td>
                                </tr>

            
                                <tr>
                                    <td style="padding-top: 25px; padding-bottom: 20px;">
                                        <p style="margin:0 0 12px; color:#94a3b8; font-size:0.75rem; text-transform:uppercase; letter-spacing:1px; font-weight:600;">Detalhes da Solicitação</p>

                                        <table width="100%" cellpadding="0" cellspacing="0">
                                            <tr>
                                                <td style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">🏢 Instituição</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">{instituicao['nome']}</strong>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">📋 Título</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">{titulo}</strong>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">📅 Data</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">{data_formatada}</strong>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">🕐 Horário</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">{horario_proposta}</strong>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">📍 Local</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">{endereco_palestra}</strong>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 10px 0;">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">📝 Descrição</span><br>
                                                    <span style="color:#cbd5e1; font-size:0.95rem; line-height:1.6;">{descricao}</span>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>

                         
                                <tr>
                                    <td style="padding-bottom: 25px;">
                                        <div style="background: rgba(245,158,11,0.06); border-left: 3px solid #f59e0b; border-radius: 8px; padding: 15px 18px;">
                                            <p style="margin:0 0 4px; color:#f59e0b; font-size:0.8rem; font-weight:600; text-transform:uppercase; letter-spacing:1px;">⚠️ Prazo de Resposta</p>
                                            <p style="margin:0; color:#cbd5e1; font-size:0.9rem; line-height:1.6;">
                                                Esta solicitação expira em <strong style="color:#f8fafc;">{data_expiracao_formatada}</strong>. Acesse o sistema para aceitar ou recusar.
                                            </p>
                                        </div>
                                    </td>
                                </tr>

                 
                                <tr>
                                    <td align="center" style="padding-bottom: 10px;">
                                        <a href="http://localhost:5000"
                                           style="display:inline-block; background: linear-gradient(135deg, #00d2ff, #0099cc); color:#000000; font-weight:700; font-size:0.95rem; text-decoration:none; padding: 14px 35px; border-radius: 10px;">
                                            Acessar o Sistema →
                                        </a>
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
            
            email_instituicao_enviado = send_notification_email(
                recipient=instituicao['email'],
                subject=subject_instituicao,
                body=body_instituicao
            )
            
    
            
            cursor.close()
            conn.close()
            
          
            if email_palestrante_enviado and email_instituicao_enviado:
                flash(f"✅ Solicitação enviada! Você e o palestrante foram notificados por e-mail. O palestrante tem até {data_expiracao_formatada} para responder.", "success")
            elif email_palestrante_enviado:
                flash(f"Solicitação enviada! O palestrante foi notificado. Prazo de resposta: {data_expiracao_formatada}", "success")
            else:
                flash(f"Solicitação enviada com sucesso! Prazo de resposta: {data_expiracao_formatada}", "warning")
            
            return redirect(url_for('gerenciar_solicitacoes.minhas_solicitacoes'))
        
        except Exception as e:
            flash(f"Erro ao criar solicitação: {e}", "danger")
            return redirect(url_for('gerenciar_solicitacoes.solicitar_palestra', palestrante_id=palestrante_id))
    

    
    data_pre = request.args.get('data') 
    horario_inicio_pre = request.args.get('horario_inicio')
    horario_fim_pre = request.args.get('horario_fim')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT id, nome_completo FROM palestrantes WHERE id = %s
        """, (palestrante_id,))
        
        palestrante = cursor.fetchone()
        
        if not palestrante:
            flash("Palestrante não encontrado", "danger")
            return redirect(url_for('gerenciar_solicitacoes.listar_palestrantes'))
        
        cursor.close()
        conn.close()
        
        return render_template("formulario_solicitacao.html", 
                               palestrante=palestrante,
                               data_pre=data_pre,
                               horario_inicio_pre=horario_inicio_pre,
                               horario_fim_pre=horario_fim_pre)
    
    except Exception as e:
        flash(f"Erro ao carregar formulário: {e}", "danger")
        return redirect(url_for('gerenciar_solicitacoes.listar_palestrantes'))
    
@gerenciar_solicitacoes_bp.route("/minhas_solicitacoes", methods=["GET"])
@login_required("instituicao")
def minhas_solicitacoes():
    """Lista as solicitações feitas pela instituição."""
    instituicao_id = session['user_id']
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
       
        cursor.execute(""" UPDATE solicitacoes_palestras
                            SET status = 'sem resposta'
                            WHERE instituicao_id = %s
                            AND status = 'pendente'
                            AND prazo_expiracao < NOW()
                            """, [instituicao_id]) 
        conn.commit()
        
       
        cursor.execute("""
            SELECT sp.id, sp.titulo, sp.descricao, sp.endereco_palestra, sp.data_proposta, sp.horario_proposta, 
                   sp.status, sp.criada_em, p.nome_completo, sp.endereco_palestra, sp.prazo_expiracao
            FROM solicitacoes_palestras sp
            JOIN palestrantes p ON sp.palestrante_id = p.id
            WHERE sp.instituicao_id = %s
            ORDER BY sp.data_proposta DESC
        """, (instituicao_id,))
        
        solicitacoes = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return render_template("minhas_solicitacoes_instituicao.html", solicitacoes=solicitacoes)
    
    except Exception as e:
        flash(f"Erro ao listar solicitações: {e}", "danger")
        return redirect(url_for('login_instituicao.painel_instituicao'))

@gerenciar_solicitacoes_bp.route("/solicitacoes_recebidas", methods=["GET"])
@login_required("palestrante")
def solicitacoes_recebidas():
    """Lista as solicitações recebidas pelo palestrante."""
    palestrante_id = session['user_id']
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        

        cursor.execute("""
            UPDATE solicitacoes_palestras
            SET status = 'sem resposta'
            WHERE palestrante_id = %s 
            AND status = 'pendente' 
            AND prazo_expiracao < NOW()
        """, (palestrante_id,))
        conn.commit() 
        
        cursor.execute("""
            SELECT sp.id, i.nome, sp.titulo, sp.descricao, sp.data_proposta, sp.horario_proposta, 
                   sp.status, sp.criada_em, sp.endereco_palestra, 
                   sp.prazo_expiracao,                
                   i.nome AS nome_instituicao          
            FROM solicitacoes_palestras sp
            JOIN instituicoes i ON sp.instituicao_id = i.id
            WHERE sp.palestrante_id = %s
            ORDER BY sp.criada_em DESC
        """, (palestrante_id,))
        
        solicitacoes = cursor.fetchall()
        cursor.close()
        
        conn.close()
        

        return render_template("solicitacoes_recebidas.html", solicitacoes=solicitacoes)
    
    except Exception as e:
        flash(f"Erro ao listar solicitações: {e}", "danger")
        return redirect(url_for('login_palestrante.painel_palestrante'))
    
@gerenciar_solicitacoes_bp.route("/responder_solicitacao/<int:solicitacao_id>/<string:resposta>", methods=["POST"])
@login_required("palestrante")
def responder_solicitacao(solicitacao_id, resposta):
    """Responde uma solicitação de palestra (aceita ou recusa) e notifica por e-mail."""
    palestrante_id = session['user_id']
    
    if resposta not in ['aceita', 'recusada']:
        flash("Resposta inválida", "danger")
        return redirect(url_for('gerenciar_solicitacoes.solicitacoes_recebidas'))
    
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                sp.id, sp.instituicao_id, sp.data_proposta, sp.horario_proposta, 
                sp.titulo, sp.descricao, sp.endereco_palestra,
                i.email AS email_instituicao, i.nome AS nome_instituicao,
                p.nome_completo AS nome_palestrante
            FROM solicitacoes_palestras sp
            JOIN instituicoes i ON sp.instituicao_id = i.id
            JOIN palestrantes p ON sp.palestrante_id = p.id
            WHERE sp.id = %s AND sp.palestrante_id = %s AND sp.status = 'pendente'
        """, (solicitacao_id, palestrante_id))
        
        solicitacao = cursor.fetchone()
        
        if not solicitacao:
            flash("Solicitação não encontrada, já respondida ou não pertence a você.", "danger")
            return redirect(url_for('gerenciar_solicitacoes.solicitacoes_recebidas'))


        data_proposta = solicitacao['data_proposta']
        horario_proposta = solicitacao['horario_proposta']
        titulo = solicitacao['titulo']
        nome_palestrante = solicitacao['nome_palestrante']
        nome_instituicao = solicitacao['nome_instituicao']
        email_instituicao = solicitacao['email_instituicao']
        
        body_recusa = ""

        if resposta == 'aceita':
            
        
            cursor.execute("""
                SELECT id FROM palestras_confirmadas
                WHERE palestrante_id = %s 
                AND data = %s 
                AND horario = %s
                AND status != 'cancelada'
            """, (palestrante_id, data_proposta, horario_proposta))
            
            if cursor.fetchone():
                flash("Conflito de agenda: Você já tem uma palestra confirmada nesta data e horário.", "danger")
                return redirect(url_for('gerenciar_solicitacoes.solicitacoes_recebidas'))
                
            cursor.execute("""
                INSERT INTO palestras_confirmadas 
                (solicitacao_id, palestrante_id, instituicao_id, titulo, descricao, 
                 data, horario, status, endereco_palestra)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'agendada', %s)
            """, (solicitacao_id, palestrante_id, solicitacao['instituicao_id'], 
                  titulo, solicitacao['descricao'], data_proposta, 
                  horario_proposta, solicitacao['endereco_palestra']))

            print("\n" + "="*60)
            print("🗑️  REMOVENDO DISPONIBILIDADE ACEITA")
            print("="*60)
            print(f"Palestrante ID: {palestrante_id}")
            print(f"Data: {data_proposta}")
            print(f"Horário: {horario_proposta}")
            
            cursor.execute("""
                SELECT id, horario_inicio, horario_fim 
                FROM disponibilidade_palestrantes
                WHERE palestrante_id = %s 
                AND data = %s 
                AND horario_inicio <= %s 
                AND horario_fim >= %s
            """, (palestrante_id, data_proposta, horario_proposta, horario_proposta))
            
            disponibilidade = cursor.fetchone()
            
            if disponibilidade:
                print(f"✅ Disponibilidade encontrada: ID {disponibilidade['id']}")
                print(f"   Horário: {disponibilidade['horario_inicio']} - {disponibilidade['horario_fim']}")
                
                cursor.execute("""
                    DELETE FROM disponibilidade_palestrantes 
                    WHERE id = %s
                """, (disponibilidade['id'],))
                
                print(f"✅ Disponibilidade ID {disponibilidade['id']} removida!")
            else:
                print("⚠️  Nenhuma disponibilidade correspondente encontrada")
                print("   (Pode ser que a solicitação foi feita sem usar uma disponibilidade específica)")
            
            print("="*60 + "\n")
      
        elif resposta == 'recusada':
            motivo=request.form.get('motivo_recusa','').strip()
            body_recusa = f"\nMotivo da Recusa: {motivo}" if motivo else "\nMotivo da Recusa: Não especificado pelo palestrante."
        
        cursor.execute("""
            UPDATE solicitacoes_palestras
            SET status = %s, respondida_em = NOW(), motivo_recusa=%s
            WHERE id = %s
        """, (resposta, motivo if resposta == 'recusada' else None, solicitacao_id))
        
        conn.commit()  

        data_formatada = data_proposta.strftime('%d/%m/%Y')
        
        if resposta == 'aceita':
            subject = f"✅ Confirmação: Palestra '{titulo}' Aceita!"
            body =f"""
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

                  
                    <tr>
                        <td align="center" style="padding-bottom: 30px;">
                            <h1 style="margin:0; font-size:1.6rem; color:#00d2ff; letter-spacing:-0.5px;">✦ PalestraApp</h1>
                            <p style="margin:6px 0 0; color:#94a3b8; font-size:0.85rem;">Sistema de Agendamento de Palestras</p>
                        </td>
                    </tr>

                  
                    <tr>
                        <td style="background: linear-gradient(135deg, #0f172a, #1e293b); border: 1px solid rgba(16,185,129,0.2); border-radius: 16px; padding: 35px;">
                            <table width="100%" cellpadding="0" cellspacing="0">

                              
                                <tr>
                                    <td align="center" style="padding-bottom: 25px; border-bottom: 1px solid rgba(255,255,255,0.07);">
                                        <div style="background: rgba(16,185,129,0.1); border: 1px solid rgba(16,185,129,0.3); border-radius: 50px; display:inline-block; padding: 10px 22px; margin-bottom: 15px;">
                                            <span style="color:#10b981; font-size:0.85rem; font-weight:600; letter-spacing:1px;">✔ PALESTRA ACEITA</span>
                                        </div>
                                        <h2 style="margin:0; color:#f8fafc; font-size:1.4rem;">Ótimas notícias, {nome_instituicao}!</h2>
                                        <p style="margin:10px 0 0; color:#94a3b8; font-size:0.95rem; line-height:1.6;">
                                            O palestrante aceitou a sua solicitação.
                                        </p>
                                    </td>
                                </tr>

                            
                                <tr>
                                    <td style="padding-top: 25px; padding-bottom: 20px;">
                                        <p style="margin:0 0 12px; color:#94a3b8; font-size:0.75rem; text-transform:uppercase; letter-spacing:1px; font-weight:600;">Detalhes da Palestra</p>
                                        <table width="100%" cellpadding="0" cellspacing="0">
                                            <tr>
                                                <td style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">👤 Palestrante</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">{nome_palestrante}</strong>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">📋 Título</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">{titulo}</strong>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">📅 Data</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">{data_formatada}</strong>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 10px 0;">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">🕐 Horário</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">{horario_proposta}</strong>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>

                               
                                <tr>
                                    <td style="padding-bottom: 25px;">
                                        <div style="background: rgba(0,210,255,0.06); border-left: 3px solid #00d2ff; border-radius: 8px; padding: 12px 18px;">
                                            <p style="margin:0; color:#94a3b8; font-size:0.85rem; line-height:1.6;">
                                                💡 Os detalhes logísticos podem ser acertados diretamente com o palestrante.
                                            </p>
                                        </div>
                                    </td>
                                </tr>

                           
                                <tr>
                                    <td align="center" style="padding-bottom: 10px;">
                                        <a href="http://localhost:5000"
                                           style="display:inline-block; background: linear-gradient(135deg, #00d2ff, #0099cc); color:#000000; font-weight:700; font-size:0.95rem; text-decoration:none; padding: 14px 35px; border-radius: 10px;">
                                            Acessar o Sistema →
                                        </a>
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
Sua Plataforma"""
        else:
            subject = f"❌ Resposta: Palestra '{titulo}' Recusada"
            body = f"""
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

                    
                    <tr>
                        <td align="center" style="padding-bottom: 30px;">
                            <h1 style="margin:0; font-size:1.6rem; color:#00d2ff; letter-spacing:-0.5px;">✦ PalestraApp</h1>
                            <p style="margin:6px 0 0; color:#94a3b8; font-size:0.85rem;">Sistema de Agendamento de Palestras</p>
                        </td>
                    </tr>

                    
                    <tr>
                        <td style="background: linear-gradient(135deg, #0f172a, #1e293b); border: 1px solid rgba(244,63,94,0.2); border-radius: 16px; padding: 35px;">
                            <table width="100%" cellpadding="0" cellspacing="0">

                               
                                <tr>
                                    <td align="center" style="padding-bottom: 25px; border-bottom: 1px solid rgba(255,255,255,0.07);">
                                        <div style="background: rgba(244,63,94,0.1); border: 1px solid rgba(244,63,94,0.3); border-radius: 50px; display:inline-block; padding: 10px 22px; margin-bottom: 15px;">
                                            <span style="color:#f43f5e; font-size:0.85rem; font-weight:600; letter-spacing:1px;">❌ PALESTRA RECUSADA</span>
                                        </div>
                                        <h2 style="margin:0; color:#f8fafc; font-size:1.4rem;">Prezada, {nome_instituicao}!</h2>
                                        <p style="margin:10px 0 0; color:#94a3b8; font-size:0.95rem; line-height:1.6;">
                                            Lamentamos informar que o palestrante recusou a solicitação.
                                        </p>
                                    </td>
                                </tr>

                                
                                <tr>
                                    <td style="padding-top: 25px; padding-bottom: 20px;">
                                        <p style="margin:0 0 12px; color:#94a3b8; font-size:0.75rem; text-transform:uppercase; letter-spacing:1px; font-weight:600;">Detalhes da Solicitação</p>
                                        <table width="100%" cellpadding="0" cellspacing="0">
                                            <tr>
                                                <td style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">👤 Palestrante</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">{nome_palestrante}</strong>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">📋 Título</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">{titulo}</strong>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">📅 Data Proposta</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">{data_formatada}</strong>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 10px 0;">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">🕐 Horário</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">{horario_proposta}</strong>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>

                                
                                <tr>
                                    <td style="padding-bottom: 25px;">
                                        <p style="margin:0 0 10px; color:#94a3b8; font-size:0.75rem; text-transform:uppercase; letter-spacing:1px; font-weight:600;">Motivo da Recusa</p>
                                        <div style="background: rgba(244,63,94,0.06); border-left: 3px solid #f43f5e; border-radius: 8px; padding: 15px 18px;">
                                            <p style="margin:0; color:#cbd5e1; font-size:0.95rem; line-height:1.7; font-style:italic;">
                                                "{body_recusa}"
                                            </p>
                                        </div>
                                    </td>
                                </tr>

                                <!-- Dica -->
                                <tr>
                                    <td style="padding-bottom: 25px;">
                                        <div style="background: rgba(245,158,11,0.06); border-left: 3px solid #f59e0b; border-radius: 8px; padding: 12px 18px;">
                                            <p style="margin:0; color:#94a3b8; font-size:0.85rem; line-height:1.6;">
                                                💡 Você pode buscar outro palestrante disponível no sistema.
                                            </p>
                                        </div>
                                    </td>
                                </tr>

                               
                                <tr>
                                    <td align="center" style="padding-bottom: 10px;">
                                        <a href="http://localhost:5000"
                                           style="display:inline-block; background: linear-gradient(135deg, #00d2ff, #0099cc); color:#000000; font-weight:700; font-size:0.95rem; text-decoration:none; padding: 14px 35px; border-radius: 10px;">
                                            Buscar Palestrantes →
                                        </a>
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
        

        from utils.mail import send_notification_email
        email_enviado = send_notification_email(email_instituicao, subject, body)
        
        if email_enviado:
            flash(f"Palestra {resposta} com sucesso! E-mail de notificação enviado.", "success")
        else:
            flash(f"Palestra {resposta}, mas houve erro ao enviar o e-mail de notificação.", "warning")
        
        return redirect(url_for('gerenciar_solicitacoes.solicitacoes_recebidas'))
    
    except Exception as e:
        if conn and conn.is_connected():
            conn.rollback()
        
        print(f"ERRO DETALHADO em responder_solicitacao: {e}")
        print(f"Tipo do erro: {type(e).__name__}")
        import traceback
        print("Traceback completo:")
        print(traceback.format_exc())
        
        flash(f"Erro ao responder solicitação: {e}", "danger")
        return redirect(url_for('gerenciar_solicitacoes.solicitacoes_recebidas'))
    
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()