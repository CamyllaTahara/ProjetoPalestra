from email import message

from flask import Blueprint, current_app, render_template, session, redirect, url_for, request
from flask_socketio import SocketIO, emit, join_room
from utils.security import login_required
import mysql.connector
from datetime import datetime
from utils.security import login_required
from flask_mail import Message

chat_bp = Blueprint('chat', __name__)
socketio_instance = None

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="palestra"
    )

def init_socketio(socketio):
    global socketio_instance
    socketio_instance = socketio

    @socketio.on('entrar_sala')
    def entrar_sala(data):
        palestra_id = data.get('palestra_id')
        join_room(f"palestra_{palestra_id}")

    @socketio.on('enviar_mensagem')
    def enviar_mensagem(data):
        print(f"🔴 EVENTO RECEBIDO: {data}")
        palestra_id = data.get('palestra_id')
        mensagem = data.get('mensagem', '').strip() # Variável correta: mensagem
        remetente_tipo = data.get('remetente_tipo')
        remetente_id = data.get('remetente_id')
        remetente_nome = data.get('remetente_nome')
        
        if not mensagem: 
            return

        enviar_notificacao = False 
        email_destinatario = None

        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True) 
            
            # 🔍 1. BUSCAR A ÚLTIMA MENSAGEM
            cursor.execute("""
                SELECT remetente_tipo FROM mensagens_chat 
                WHERE palestra_id = %s 
                ORDER BY enviada_em DESC LIMIT 1
            """, (palestra_id,))
            ultima_mensagem = cursor.fetchone()

            if not ultima_mensagem or ultima_mensagem['remetente_tipo'] != remetente_tipo:
                enviar_notificacao = True

            # 🔍 2. BUSCAR O E-MAIL DO DESTINATÁRIO
            if enviar_notificacao:
                if remetente_tipo == 'palestrante':
                    cursor.execute("""
                        SELECT i.email FROM palestras_confirmadas pc
                        JOIN instituicoes i ON pc.instituicao_id = i.id
                        WHERE pc.id = %s
                    """, (palestra_id,))
                else:
                    cursor.execute("""
                        SELECT p.email FROM palestras_confirmadas pc
                        JOIN palestrantes p ON pc.palestrante_id = p.id
                        WHERE pc.id = %s
                    """, (palestra_id,))
                
                resultado_email = cursor.fetchone()
                if resultado_email:
                    email_destinatario = resultado_email['email']

            # 💾 3. FAZ O INSERT DA MENSAGEM NOVA
            # 🟢 CORRIGIDO: Mudei a coluna de 'message' para 'mensagem' para bater com seu banco
            cursor.execute("""
                INSERT INTO mensagens_chat 
                (palestra_id, remetente_tipo, remetente_id, mensagem, lida)
                VALUES (%s, %s, %s, %s, 0)
            """, (palestra_id, remetente_tipo, remetente_id, mensagem))
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"Erro no banco durante o envio de mensagem: {e}")
            return

        # ✉️ 4. DISPARAR O E-MAIL
        if enviar_notificacao and email_destinatario:
            try:
                mail = current_app.extensions.get('mail')
                if mail:
                    # Criamos a estrutura HTML com o mesmo design do site
                    conteudo_html = f"""
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
                                            <span style="color:#00d2ff; font-size:0.85rem; font-weight:600; letter-spacing:1px;">💬 NOVA MENSAGEM</span>
                                        </div>
                                        <h2 style="margin:0; color:#f8fafc; font-size:1.4rem;">Você recebeu uma mensagem!</h2>
                                        <p style="margin:10px 0 0; color:#94a3b8; font-size:0.95rem; line-height:1.6;">
                                            <strong style="color:#f8fafc;">{remetente_nome}</strong> enviou uma mensagem no chat da palestra.
                                        </p>
                                    </td>
                                </tr>

                                <!-- Mensagem -->
                                <tr>
                                    <td style="padding-top: 25px; padding-bottom: 25px;">
                                        <p style="margin:0 0 10px; color:#94a3b8; font-size:0.75rem; text-transform:uppercase; letter-spacing:1px; font-weight:600;">Mensagem recebida</p>
                                        <div style="background: rgba(0,210,255,0.06); border-left: 3px solid #00d2ff; border-radius: 8px; padding: 15px 18px;">
                                            <p style="margin:0; color:#f8fafc; font-size:0.95rem; line-height:1.7; font-style:italic;">
                                                "{mensagem}"
                                            </p>
                                        </div>
                                    </td>
                                </tr>

                                <!-- Aviso -->
                                <tr>
                                    <td style="padding-bottom: 25px;">
                                        <div style="background: rgba(245,158,11,0.06); border-left: 3px solid #f59e0b; border-radius: 8px; padding: 12px 18px;">
                                            <p style="margin:0; color:#94a3b8; font-size:0.85rem; line-height:1.6;">
                                                ⚠️ Se você não esperava esta mensagem, pode ignorar este e-mail com segurança.
                                            </p>
                                        </div>
                                    </td>
                                </tr>

                                <!-- Botão -->
                                <tr>
                                    <td align="center" style="padding-bottom: 10px;">
                                        <a href="http://localhost:5000/login"
                                           style="display:inline-block; background: linear-gradient(135deg, #00d2ff, #0099cc); color:#000000; font-weight:700; font-size:0.95rem; text-decoration:none; padding: 14px 35px; border-radius: 10px;">
                                            💬 Responder no Chat →
                                        </a>
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

                    msg = Message(
                        subject="Notificação: Nova mensagem sobre a palestra!",
                        sender=current_app.config.get('MAIL_USERNAME'),
                        recipients=[email_destinatario],
                        html=conteudo_html # 🟢 Mudamos aqui para enviar o HTML estruturado!
                    )
                    mail.send(msg)
                    print(f"📧 E-mail HTML enviado com sucesso para: {email_destinatario}")
            except Exception as mail_error:
                print(f"⚠️ Erro ao enviar e-mail estilizado: {mail_error}")
        # 5. ENVIAR VIA WEBSOCKET (Tempo real na tela)
        emit('nova_mensagem', {
            'mensagem': mensagem,
            'remetente_nome': remetente_nome,
            'remetente_tipo': remetente_tipo,
            'enviada_em': datetime.now().strftime('%d/%m/%Y %H:%M')
        }, room=f"palestra_{palestra_id}")

@chat_bp.route('/chat/<int:palestra_id>')
def chat(palestra_id):
    """Abre o chat de uma palestra confirmada."""
    user_id = session.get('user_id')
    user_type = session.get('user_type')

    if not user_id or user_type not in ('palestrante', 'instituicao', 'administrador'):
        return redirect(url_for('login_palestrante.login_palestrante'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        id_sessao = int(session.get('user_id'))
        tipo_sessao = str(session.get('user_type')).strip()

        # Executa o UPDATE usando a lógica do NOT para blindar no MariaDB
        cursor.execute("""
            UPDATE mensagens_chat 
            SET lida = 1 
            WHERE palestra_id = %s 
              AND NOT (remetente_id = %s AND remetente_tipo = %s)
        """, (palestra_id, id_sessao, tipo_sessao))
        conn.commit()

        # Buscar dados da palestra
        cursor.execute("""
            SELECT pc.id, pc.titulo, pc.data, pc.horario,
                   p.nome_completo AS nome_palestrante, p.id AS palestrante_id,
                   i.nome AS nome_instituicao, i.id AS instituicao_id
            FROM palestras_confirmadas pc
            JOIN palestrantes p ON pc.palestrante_id = p.id
            JOIN instituicoes i ON pc.instituicao_id = i.id
            WHERE pc.id = %s
        """, (palestra_id,))
        palestra = cursor.fetchone()

        if not palestra:
            return "Palestra não encontrada", 404

        # Verificar permissão (só participantes ou admin)
        if user_type == 'palestrante' and palestra['palestrante_id'] != user_id:
            return "Acesso negado", 403
        if user_type == 'instituicao' and palestra['instituicao_id'] != user_id:
            return "Acesso negado", 403

        # Buscar histórico de mensagens
        cursor.execute("""
            SELECT mc.mensagem, mc.remetente_tipo, mc.enviada_em,
                   COALESCE(p.nome_completo, i.nome) AS remetente_nome
            FROM mensagens_chat mc
            LEFT JOIN palestrantes p ON mc.remetente_tipo = 'palestrante' AND mc.remetente_id = p.id
            LEFT JOIN instituicoes i ON mc.remetente_tipo = 'instituicao' AND mc.remetente_id = i.id
            WHERE mc.palestra_id = %s
            ORDER BY mc.enviada_em ASC
        """, (palestra_id,))
        mensagens = cursor.fetchall()

        cursor.close()
        conn.close()

        # Definir nome do usuário logado
        if user_type == 'palestrante':
            meu_nome = palestra['nome_palestrante']
        elif user_type == 'instituicao':
            meu_nome = palestra['nome_instituicao']
        else:
            meu_nome = 'Administrador'

        return render_template('chat.html',
                               palestra=palestra,
                               mensagens=mensagens,
                               user_id=user_id,
                               user_type=user_type,
                               meu_nome=meu_nome,
                               somente_leitura=(user_type == 'administrador'))

    except Exception as e:
        return f"Erro ao carregar chat: {e}", 500
    

@chat_bp.route('/admin/conversas')
@login_required("administrador")
def admin_conversas():
    """Lista todas as conversas para o administrador com filtros."""
    filtro_palestrante = request.args.get('palestrante', '')
    filtro_instituicao = request.args.get('instituicao', '')

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Buscar todas as palestras confirmadas com filtros
        query = """
            SELECT pc.id, pc.titulo, pc.data, pc.status,
                   p.nome_completo AS nome_palestrante,
                   i.nome AS nome_instituicao,
                   COUNT(mc.id) AS total_mensagens,
                   MAX(mc.enviada_em) AS ultima_mensagem
            FROM palestras_confirmadas pc
            JOIN palestrantes p ON pc.palestrante_id = p.id
            JOIN instituicoes i ON pc.instituicao_id = i.id
            LEFT JOIN mensagens_chat mc ON mc.palestra_id = pc.id
            WHERE 1=1
        """
        params = []

        if filtro_palestrante:
            query += " AND p.nome_completo LIKE %s"
            params.append(f"%{filtro_palestrante}%")

        if filtro_instituicao:
            query += " AND i.nome LIKE %s"
            params.append(f"%{filtro_instituicao}%")

        query += " GROUP BY pc.id ORDER BY ultima_mensagem DESC, pc.data DESC"

        cursor.execute(query, params)
        conversas = cursor.fetchall()
        cursor.close()
        conn.close()

        return render_template('admin_conversas.html',
                               conversas=conversas,
                               filtro_palestrante=filtro_palestrante,
                               filtro_instituicao=filtro_instituicao)

    except Exception as e:
        return f"Erro ao carregar conversas: {e}", 500