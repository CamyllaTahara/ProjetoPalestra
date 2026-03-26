from flask import Blueprint, render_template, session, redirect, url_for, request
from flask_socketio import SocketIO, emit, join_room
from utils.security import login_required
import mysql.connector
from datetime import datetime
from utils.security import login_required

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
        mensagem = data.get('mensagem', '').strip()
        remetente_tipo = data.get('remetente_tipo')
        remetente_id = data.get('remetente_id')
        remetente_nome = data.get('remetente_nome')
        print(f"🔴 palestra_id: {palestra_id}")
        print(f"🔴 mensagem: {mensagem}")
        print(f"🔴 remetente_tipo: {remetente_tipo}")
        print(f"🔴 remetente_id: {remetente_id}")

        if not mensagem:
            print("🔴 MENSAGEM VAZIA, abortando")
            return

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO mensagens_chat 
                (palestra_id, remetente_tipo, remetente_id, mensagem)
                VALUES (%s, %s, %s, %s)
            """, (palestra_id, remetente_tipo, remetente_id, mensagem))
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Erro ao salvar mensagem: {e}")
            return

        # Envia para todos na sala
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