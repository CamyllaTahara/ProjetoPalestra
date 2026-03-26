from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from utils.auth import login_required
import mysql.connector
from datetime import datetime, date
import smtplib
from utils.mail import send_notification_email

gerenciar_palestras_bp = Blueprint("gerenciar_palestras", __name__)


def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="palestra"
    )



@gerenciar_palestras_bp.route("/minhas_palestras", methods=['GET'])
@login_required("palestrante")
def minhas_palestras():
    palestrante_id = session['user_id']

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT pc.id, pc.titulo, pc.descricao, pc.data, pc.horario, pc.status, 
                   pc.criada_em, pc.endereco_palestra, i.nome, i.email, i.telefone
            FROM palestras_confirmadas pc
            JOIN instituicoes i ON pc.instituicao_id = i.id
            WHERE pc.palestrante_id = %s
            AND pc.status = 'agendada'
            AND pc.data >= CURDATE()
            ORDER BY pc.data, pc.horario           
        """, (palestrante_id,))
        
        palestras_agendadas = cursor.fetchall()
        
        # ✅ Converter timedelta para string
        for palestra in palestras_agendadas:
            if palestra.get('horario') and not isinstance(palestra['horario'], str):
                h, m = divmod(int(palestra['horario'].total_seconds()), 3600)
                m = m // 60
                palestra['horario'] = f"{h:02d}:{m:02d}"

        cursor.execute("""
            SELECT pc.id, pc.titulo, pc.descricao, pc.data, pc.horario, pc.status, 
                   pc.criada_em, pc.endereco_palestra, i.nome, i.email, i.telefone
            FROM palestras_confirmadas pc
            JOIN instituicoes i ON pc.instituicao_id = i.id
            WHERE pc.palestrante_id = %s
            AND (pc.status = 'realizada' OR (pc.status = 'agendada' AND pc.data < CURDATE()))
            ORDER BY pc.data DESC, pc.horario DESC
        """, (palestrante_id,))
        
        historico = cursor.fetchall()
        
        # ✅ Converter timedelta para string
        for palestra in historico:
            if palestra.get('horario') and not isinstance(palestra['horario'], str):
                h, m = divmod(int(palestra['horario'].total_seconds()), 3600)
                m = m // 60
                palestra['horario'] = f"{h:02d}:{m:02d}"

        cursor.close()
        conn.close()

        return render_template("minhas_palestras_palestrante.html",
                                palestras_agendadas=palestras_agendadas,
                                historico=historico,  today=date.today())
    
    except Exception as e:
        flash(f"Erro ao listar palestras: {e}", "danger")
        return redirect(url_for("login_palestrante.painel_palestrante"))
        
@gerenciar_palestras_bp.route("/palestra/<int:palestra_id>/marcar_realizada", methods=["POST"])
@login_required("palestrante")
def marcar_realizada(palestra_id):
    palestrante_id = session['user_id']

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, data FROM palestras_confirmadas
            WHERE id = %s AND palestrante_id = %s AND status = 'agendada'
        """, (palestra_id, palestrante_id))
        
        palestra = cursor.fetchone()

        if not palestra:
            flash("Palestra não encontrada ou não pode ser marcada como realizada", "danger")
            cursor.close()
            conn.close()
            return redirect(url_for('gerenciar_palestras.minhas_palestras'))
        
        if palestra['data'] > date.today():
            flash("Só é possível marcar como realizada após a data da palestra", "danger")
            cursor.close()
            conn.close()
            return redirect(url_for('gerenciar_palestras.minhas_palestras'))
        
        cursor.execute("""
            UPDATE palestras_confirmadas
            SET status = 'realizada'
            WHERE id = %s
        """, (palestra_id,))
        
        conn.commit()
        cursor.close()
        conn.close()

        flash("Palestra marcada como realizada!", "success")  # ✅ CORRIGIDO: 'success' não 'sucess'
        return redirect(url_for('gerenciar_palestras.minhas_palestras'))
    
    except Exception as e:
        flash(f"Erro ao marcar palestra como realizada: {e}", "danger")
        return redirect(url_for('gerenciar_palestras.minhas_palestras'))
    
@gerenciar_palestras_bp.route("/palestra/<int:palestra_id>/cancelar_palestrante", methods=["POST"])
@login_required("palestrante")
def cancelar_palestra_palestrante(palestra_id):
    palestrante_id = session['user_id']

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. BUSCA DADOS COMPLETOS
        cursor.execute("""
            SELECT pc.id, pc.titulo, pc.data, pc.horario, pc.status,
                   i.nome as nome_instituicao, i.email as email_instituicao,
                   p.nome_completo as nome_palestrante
            FROM palestras_confirmadas pc
            JOIN instituicoes i ON pc.instituicao_id = i.id
            JOIN palestrantes p ON pc.palestrante_id = p.id
            WHERE pc.id = %s AND pc.palestrante_id = %s AND pc.status = 'agendada'
        """, (palestra_id, palestrante_id))
        
        palestra = cursor.fetchone()
        
        if not palestra:
            flash("Palestra não encontrada ou não pode ser cancelada", "danger")
            cursor.close()
            conn.close()
            return redirect(url_for('gerenciar_palestras.minhas_palestras'))
        
        # Converte horário se for timedelta
        horario_formatado = palestra['horario']
        if not isinstance(horario_formatado, str):
            h, m = divmod(int(horario_formatado.total_seconds()), 3600)
            m = m // 60
            horario_formatado = f"{h:02d}:{m:02d}"
        
        # 2. ATUALIZA STATUS NO BANCO
        cursor.execute("""
            UPDATE palestras_confirmadas
            SET status = 'cancelada'
            WHERE id = %s
        """, (palestra_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # ============================================================
        # 📧 LÓGICA DE ENVIO DE E-MAIL DIRETO PARA A INSTITUIÇÃO (NOVO PADRÃO)
        # ============================================================

        # Preparação dos dados
        email_instituicao = palestra['email_instituicao']
        nome_instituicao = palestra['nome_instituicao']
        titulo = palestra['titulo']
        data_formatada = palestra['data'].strftime('%d/%m/%Y')
        nome_palestrante = palestra['nome_palestrante']

        # 🚨 DEBUG: Este é o ponto crítico. Imprima o e-mail antes de enviar.
        print(f"\nDEBUG E-MAIL CANCELE: Destinatário da Instituição: {email_instituicao}")
        
        # 3. Montar Subject
        subject = f"⚠️ Cancelamento de Palestra: {titulo}"
        
        # 4. Montar Corpo HTML
        # Usando a estrutura HTML que você já tinha:
        corpo_email_html = f"""
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{ font-family: Arial, sans-serif; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #f44336; color: white; padding: 20px; text-align: center; border-radius: 5px; }}
                    .content {{ padding: 20px; background-color: #f9f9f9; margin-top: 10px; border-radius: 5px; }}
                    .info-box {{ background-color: #fff; padding: 15px; margin: 10px 0; border-left: 4px solid #f44336; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>⚠️ Palestra Cancelada</h2>
                    </div>
                    <div class="content">
                        <p>Olá, <strong>{nome_instituicao}</strong>,</p>
                        <p>Informamos que a palestra abaixo foi <strong>cancelada pelo palestrante</strong>:</p>
                        
                        <div class="info-box">
                            <p><strong>Título:</strong> {titulo}</p>
                            <p><strong>Data:</strong> {data_formatada}</p>
                            <p><strong>Horário:</strong> {horario_formatado}</p>
                            <p><strong>Palestrante:</strong> {nome_palestrante}</p>
                        </div>
                        
                        <p>Atenciosamente,<br><strong>Sistema de Gestão de Palestras</strong></p>
                    </div>
                </div>
            </body>
            </html>
        """
        
        # 5. Chamar a função centralizada
        # A importação deve estar no topo: from utils.mail import send_notification_email
        email_enviado = send_notification_email(
            recipient=email_instituicao,
            subject=subject,
            body=corpo_email_html,
            is_html=True # Sinaliza que o corpo é HTML
        )

        # 6. Feedback baseado no envio
        if email_enviado:
            flash("Palestra cancelada! A instituição foi notificada por e-mail.", "success")
        else:
            flash("Palestra cancelada, mas houve **erro** ao notificar a instituição por e-mail.", "warning")

        # ============================================================
        # FIM DA LÓGICA DE ENVIO DE E-MAIL
        # ============================================================
        
        return redirect(url_for('gerenciar_palestras.minhas_palestras'))

    except Exception as e:
        flash(f"Erro ao cancelar palestra: {e}", "danger")
        return redirect(url_for('gerenciar_palestras.minhas_palestras'))
    
@gerenciar_palestras_bp.route("/palestras_instituicao", methods=["GET"])
@login_required("instituicao")
def palestras_instituicao():
    instituicao_id = session['user_id']

    try:
        conn = get_db_connection()  # ✅ CORRIGIDO: faltava ()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT pc.id, pc.titulo, pc.descricao, pc.data, pc.horario, pc.status, 
                   pc.criada_em, p.nome_completo, p.email, p.telefone
            FROM palestras_confirmadas pc
            JOIN palestrantes p ON pc.palestrante_id = p.id
            WHERE pc.instituicao_id = %s
            AND pc.status = 'agendada'
            AND pc.data >= CURDATE()
            ORDER BY pc.data, pc.horario            
        """, (instituicao_id,))  # ✅ CORRIGIDO: faltava vírgula para tupla
        
        palestras_agendadas = cursor.fetchall()
        
        # ✅ Converter timedelta para string
        for palestra in palestras_agendadas:
            if palestra.get('horario') and not isinstance(palestra['horario'], str):
                h, m = divmod(int(palestra['horario'].total_seconds()), 3600)
                m = m // 60
                palestra['horario'] = f"{h:02d}:{m:02d}"

        cursor.execute("""
            SELECT pc.id, pc.titulo, pc.descricao, pc.data, pc.horario, pc.status, 
                   pc.criada_em, p.nome_completo 
            FROM palestras_confirmadas pc
            JOIN palestrantes p ON pc.palestrante_id = p.id
            WHERE pc.instituicao_id = %s
            AND (pc.status IN ('realizada','cancelada') OR (pc.status='agendada' AND pc.data < CURDATE()))
            ORDER BY pc.data DESC, pc.horario DESC
        """, (instituicao_id,))
        
        historico = cursor.fetchall()
        
        # ✅ Converter timedelta para string
        for palestra in historico:
            if palestra.get('horario') and not isinstance(palestra['horario'], str):
                h, m = divmod(int(palestra['horario'].total_seconds()), 3600)
                m = m // 60
                palestra['horario'] = f"{h:02d}:{m:02d}"

        cursor.close()
        conn.close()

        return render_template("palestras_instituicao.html", 
                             palestras_agendadas=palestras_agendadas, 
                             historico=historico, today=date.today())
    
    except Exception as e:
        flash(f"Erro ao listar palestras: {e}", "danger")
        return redirect(url_for('login_instituicao.painel_instituicao'))
    
@gerenciar_palestras_bp.route("/palestra/<int:palestra_id>/cancelar_instituicao", methods=["POST"])
@login_required("instituicao")
def cancelar_palestra_instituicao(palestra_id):
    instituicao_id = session['user_id']

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. BUSCA DADOS COMPLETOS
        cursor.execute("""
            SELECT pc.id, pc.titulo, pc.data, pc.horario, pc.status,
                   p.nome_completo as nome_palestrante, p.email as email_palestrante,
                   i.nome as nome_instituicao
            FROM palestras_confirmadas pc
            JOIN palestrantes p ON pc.palestrante_id = p.id
            JOIN instituicoes i ON pc.instituicao_id = i.id
            WHERE pc.id = %s AND pc.instituicao_id = %s AND pc.status = 'agendada'
        """, (palestra_id, instituicao_id))
        
        palestra = cursor.fetchone()
        
        if not palestra:
            flash("Palestra não encontrada ou não pode ser cancelada", "danger")
            cursor.close()
            conn.close()
            return redirect(url_for('gerenciar_palestras.palestras_instituicao'))
        
        # Converte horário se for timedelta
        horario_formatado = palestra['horario']
        if not isinstance(horario_formatado, str):
            h, m = divmod(int(horario_formatado.total_seconds()), 3600)
            m = m // 60
            horario_formatado = f"{h:02d}:{m:02d}"
        
        # 2. ATUALIZA STATUS NO BANCO
        cursor.execute("""
            UPDATE palestras_confirmadas
            SET status = 'cancelada'
            WHERE id = %s
        """, (palestra_id,))

        conn.commit()
        cursor.close()
        conn.close()
        
        # ============================================================
        # 📧 LÓGICA DE ENVIO DE E-MAIL DIRETO PARA O PALESTRANTE (NOVO PADRÃO)
        # ============================================================
        
        # Preparação dos dados
        email_palestrante = palestra['email_palestrante']
        nome_palestrante = palestra['nome_palestrante']
        titulo = palestra['titulo']
        
        # 🎯 CORREÇÃO DO ERRO 'str object' has no attribute 'strftime'
        data_para_formatar = palestra['data']
        if isinstance(data_para_formatar, (datetime, date)):
            data_formatada = data_para_formatar.strftime('%d/%m/%Y')
        else:
            data_formatada = str(data_para_formatar) 
            
        nome_instituicao = palestra['nome_instituicao']

        # 🚨 DEBUG: Imprima o e-mail antes de enviar.
        print(f"\nDEBUG E-MAIL CANCELE: Destinatário do Palestrante: {email_palestrante}")
        
        # 3. Montar Subject
        subject = f"⚠️ Cancelamento de Palestra: {titulo}"
        
        # 4. Montar Corpo HTML
        # Usando a estrutura HTML que você já tinha, adaptada para o Palentrante:
        corpo_email_html = f"""
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{ font-family: Arial, sans-serif; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #f44336; color: white; padding: 20px; text-align: center; border-radius: 5px; }}
                    .content {{ padding: 20px; background-color: #f9f9f9; margin-top: 10px; border-radius: 5px; }}
                    .info-box {{ background-color: #fff; padding: 15px; margin: 10px 0; border-left: 4px solid #f44336; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>⚠️ Palestra Cancelada</h2>
                    </div>
                    <div class="content">
                        <p>Olá, <strong>{nome_palestrante}</strong>,</p>
                        <p>Informamos que a palestra abaixo foi <strong>cancelada pela instituição</strong>:</p>
                        
                        <div class="info-box">
                            <p><strong>Título:</strong> {titulo}</p>
                            <p><strong>Data:</strong> {data_formatada}</p>
                            <p><strong>Horário:</strong> {horario_formatado}</p>
                            <p><strong>Instituição:</strong> {nome_instituicao}</p>
                        </div>
                        
                        <p>Atenciosamente,<br><strong>Sistema de Gestão de Palestras</strong></p>
                    </div>
                </div>
            </body>
            </html>
        """
        
        # 5. Chamar a função centralizada
        from utils.mail import send_notification_email # Garantindo a importação
        email_enviado = send_notification_email(
            recipient=email_palestrante,
            subject=subject,
            body=corpo_email_html,
            is_html=True # Sinaliza que o corpo é HTML
        )

        # 6. Feedback baseado no envio
        if email_enviado:
            flash("Palestra cancelada com sucesso! O palestrante foi notificado por e-mail.", 'success')
        else:
            flash("Palestra cancelada, mas houve **erro** ao notificar o palestrante por e-mail.", 'warning')

        # ============================================================
        # FIM DA LÓGICA DE ENVIO DE E-MAIL
        # ============================================================
        
        return redirect(url_for('gerenciar_palestras.palestras_instituicao'))

    except Exception as e:
        flash(f"Erro ao cancelar palestra: {e}", "danger")
        return redirect(url_for('gerenciar_palestras.palestras_instituicao'))