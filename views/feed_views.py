from flask import Blueprint, render_template, session, redirect, url_for, request, flash, current_app, jsonify
from utils.security import login_required
import mysql.connector
import os
from werkzeug.utils import secure_filename
import re

feed_bp = Blueprint('feed', __name__)

UPLOAD_FOLDER_FEED = 'uploads_feed'
EXTENSOES_PERMITIDAS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="palestra"
    )

def extensao_permitida(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in EXTENSOES_PERMITIDAS

def get_autor_nome(cursor, autor_tipo, autor_id):
    if autor_tipo == 'palestrante':
        cursor.execute("SELECT nome_completo AS nome FROM palestrantes WHERE id = %s", (autor_id,))
    else:
        cursor.execute("SELECT nome FROM instituicoes WHERE id = %s", (autor_id,))
    result = cursor.fetchone()
    return result['nome'] if result else 'Usuário'

def criar_notificacao(cursor, post_id, autor_tipo, autor_id, tipo):
    cursor.execute("SELECT autor_tipo, autor_id FROM posts_feed WHERE id = %s", (post_id,))
    post = cursor.fetchone()
    if not post:
        return
    if post['autor_tipo'] == autor_tipo and post['autor_id'] == autor_id:
        return
    cursor.execute("""
        INSERT INTO notificacoes (destinatario_tipo, destinatario_id, tipo, post_id, autor_tipo, autor_id)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (post['autor_tipo'], post['autor_id'], tipo, post_id, autor_tipo, autor_id))

def processar_mencoes(texto, post_id, autor_tipo, autor_id, cursor):
    mencoes = re.findall(r'@([\w\s]+?)(?=\s|$|[,.])', texto)
    for nome in mencoes:
        nome = nome.strip()
        if not nome:
            continue
        cursor.execute("SELECT id FROM palestrantes WHERE nome_completo LIKE %s", (f"%{nome}%",))
        encontrado = cursor.fetchone()
        tipo_encontrado = 'palestrante'
        if not encontrado:
            cursor.execute("SELECT id FROM instituicoes WHERE nome LIKE %s", (f"%{nome}%",))
            encontrado = cursor.fetchone()
            tipo_encontrado = 'instituicao'
        if encontrado:
            dest_id = encontrado['id']
            if tipo_encontrado == autor_tipo and dest_id == autor_id:
                continue
            cursor.execute("""
                INSERT INTO notificacoes (destinatario_tipo, destinatario_id, tipo, post_id, autor_tipo, autor_id)
                VALUES (%s, %s, 'mencao', %s, %s, %s)
            """, (tipo_encontrado, dest_id, post_id, autor_tipo, autor_id))

def destacar_mencoes(texto):
    def substituir(match):
        nome = match.group(1).strip()
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM palestrantes WHERE nome_completo LIKE %s", (f"%{nome}%",))
        encontrado = cursor.fetchone()
        if encontrado:
            url = f"/perfil/palestrante/{encontrado['id']}"
        else:
            cursor.execute("SELECT id FROM instituicoes WHERE nome LIKE %s", (f"%{nome}%",))
            encontrado = cursor.fetchone()
            url = f"/perfil/instituicao/{encontrado['id']}" if encontrado else None
        cursor.close()
        conn.close()
        if url:
            return f'<a href="{url}" style="color:#4CAF50; font-weight:bold; text-decoration:none;">@{nome}</a>'
        return f'<strong style="color:#4CAF50;">@{nome}</strong>'
    return re.sub(r'@([\w\s]+?)(?=\s|$|[,.])', substituir, texto)

def buscar_usuarios():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT nome_completo AS nome, 'palestrante' AS tipo FROM palestrantes WHERE status = 'ativo'")
    usuarios = cursor.fetchall()
    cursor.execute("SELECT nome, 'instituicao' AS tipo FROM instituicoes WHERE status = 'ativo'")
    usuarios += cursor.fetchall()
    cursor.close()
    conn.close()
    return usuarios

def buscar_lista_seguidores(cursor, tipo, id):
    """Busca lista de seguidores de um usuário."""
    cursor.execute("""
        SELECT s.seguidor_tipo, s.seguidor_id,
               COALESCE(p.nome_completo, i.nome) AS nome
        FROM seguidores s
        LEFT JOIN palestrantes p ON s.seguidor_tipo = 'palestrante' AND s.seguidor_id = p.id
        LEFT JOIN instituicoes i ON s.seguidor_tipo = 'instituicao' AND s.seguidor_id = i.id
        WHERE s.seguido_tipo = %s AND s.seguido_id = %s
    """, (tipo, id))
    return cursor.fetchall()

def buscar_lista_seguindo(cursor, tipo, id):
    """Busca lista de quem um usuário segue."""
    cursor.execute("""
        SELECT s.seguido_tipo, s.seguido_id,
               COALESCE(p.nome_completo, i.nome) AS nome
        FROM seguidores s
        LEFT JOIN palestrantes p ON s.seguido_tipo = 'palestrante' AND s.seguido_id = p.id
        LEFT JOIN instituicoes i ON s.seguido_tipo = 'instituicao' AND s.seguido_id = i.id
        WHERE s.seguidor_tipo = %s AND s.seguidor_id = %s
    """, (tipo, id))
    return cursor.fetchall()


# ─────────────────────────────────────────────
# FEED PRINCIPAL
# ─────────────────────────────────────────────
@feed_bp.route('/feed')
def feed():
    user_id = session.get('user_id')
    user_type = session.get('user_type')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if user_id and user_type in ('palestrante', 'instituicao'):
        cursor.execute("""
            SELECT p.id, p.autor_tipo, p.autor_id, p.descricao, p.localizacao, p.criado_em,
                   COUNT(DISTINCT c.id) AS total_curtidas,
                   COUNT(DISTINCT cm.id) AS total_comentarios
            FROM posts_feed p
            LEFT JOIN curtidas_post c ON c.post_id = p.id
            LEFT JOIN comentarios_post cm ON cm.post_id = p.id
            WHERE 
                (p.autor_tipo = %s AND p.autor_id = %s)
                OR EXISTS (
                    SELECT 1 FROM seguidores s 
                    WHERE s.seguidor_tipo = %s AND s.seguidor_id = %s 
                      AND s.seguido_tipo = p.autor_tipo AND s.seguido_id = p.autor_id
                )
            GROUP BY p.id
            ORDER BY p.criado_em DESC
        """, (user_type, user_id, user_type, user_id))
        posts_raw = cursor.fetchall()
    else:
        posts_raw = []

    if not posts_raw:
        cursor.execute("""
            SELECT p.id, p.autor_tipo, p.autor_id, p.descricao, p.localizacao, p.criado_em,
                   COUNT(DISTINCT c.id) AS total_curtidas,
                   COUNT(DISTINCT cm.id) AS total_comentarios
            FROM posts_feed p
            LEFT JOIN curtidas_post c ON c.post_id = p.id
            LEFT JOIN comentarios_post cm ON cm.post_id = p.id
            GROUP BY p.id
            ORDER BY p.criado_em DESC
            LIMIT 20
        """)
        posts_raw = cursor.fetchall()

    posts_final = []
    for post in posts_raw:
        post['autor_nome'] = get_autor_nome(cursor, post['autor_tipo'], post['autor_id'])
        cursor.execute("SELECT caminho FROM fotos_post WHERE post_id = %s", (post['id'],))
        post['fotos'] = cursor.fetchall()
        post['ja_curtiu'] = False
        if user_id and user_type:
            cursor.execute("""
                SELECT id FROM curtidas_post
                WHERE post_id = %s AND autor_tipo = %s AND autor_id = %s
            """, (post['id'], user_type, user_id))
            post['ja_curtiu'] = cursor.fetchone() is not None
        posts_final.append(post)

    notificacoes_nao_lidas = 0
    if user_id and user_type in ('palestrante', 'instituicao'):
        cursor.execute("""
            SELECT COUNT(*) AS total FROM notificacoes
            WHERE destinatario_tipo = %s AND destinatario_id = %s AND lida = 0
        """, (user_type, user_id))
        result_notif = cursor.fetchone()
        notificacoes_nao_lidas = result_notif['total'] if result_notif else 0

    cursor.close()
    conn.close()

    return render_template('feed.html', posts=posts_final, user_id=user_id,
                           user_type=user_type, notificacoes_nao_lidas=notificacoes_nao_lidas)


# ─────────────────────────────────────────────
# EXPLORAR
# ─────────────────────────────────────────────
@feed_bp.route('/explorar')
def explorar():
    user_id = session.get('user_id')
    user_type = session.get('user_type')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if user_type == 'instituicao':
        cursor.execute("SELECT * FROM instituicoes WHERE id != %s", (user_id,))
    else:
        cursor.execute("SELECT * FROM instituicoes")
    instituicoes = cursor.fetchall()

    if user_type == 'palestrante':
        cursor.execute("SELECT * FROM palestrantes WHERE id != %s", (user_id,))
    else:
        cursor.execute("SELECT * FROM palestrantes")
    palestrantes = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('explorar.html', instituicoes=instituicoes, palestrantes=palestrantes)


# ─────────────────────────────────────────────
# SEGUIR / DEIXAR DE SEGUIR
# ─────────────────────────────────────────────
@feed_bp.route('/seguir/<tipo>/<int:alvo_id>', methods=['POST'])
def seguir(tipo, alvo_id):

    print(f"Tentativa de seguir: Tipo {tipo}, ID Alvo {alvo_id}")
    user_id = session.get('user_id')
    user_type = session.get('user_type')

    if not user_id:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id FROM seguidores 
            WHERE seguidor_tipo = %s AND seguidor_id = %s 
            AND seguido_tipo = %s AND seguido_id = %s
        """, (user_type, user_id, tipo, alvo_id))
        vinculo = cursor.fetchone()

        if vinculo:
            cursor.execute("DELETE FROM seguidores WHERE id = %s", (vinculo['id'],))
        else:
            cursor.execute("""
                INSERT INTO seguidores (seguidor_tipo, seguidor_id, seguido_tipo, seguido_id) 
                VALUES (%s, %s, %s, %s)
            """, (user_type, user_id, tipo, alvo_id))
        conn.commit()
    except mysql.connector.Error as err:
        print(f"Erro no banco: {err}")
    finally:
        cursor.close()
        conn.close()

    return redirect(request.referrer or url_for('feed.explorar'))


# ─────────────────────────────────────────────
# CRIAR POST
# ─────────────────────────────────────────────
@feed_bp.route('/feed/novo', methods=['GET', 'POST'])
def novo_post():
    user_id = session.get('user_id')
    user_type = session.get('user_type')

    if not user_id or user_type not in ('palestrante', 'instituicao'):
        return redirect(url_for('feed.feed'))

    if request.method == 'POST':
        descricao = request.form.get('descricao', '').strip()
        localizacao = request.form.get('localizacao', '').strip()
        fotos = request.files.getlist('fotos')

        if not descricao:
            flash("A descrição é obrigatória.", "danger")
            return render_template('novo_post.html', usuarios=buscar_usuarios())

        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("""
                INSERT INTO posts_feed (autor_tipo, autor_id, descricao, localizacao)
                VALUES (%s, %s, %s, %s)
            """, (user_type, user_id, descricao, localizacao or None))
            conn.commit()

            cursor.execute("SELECT LAST_INSERT_ID() AS post_id")
            post_id = cursor.fetchone()['post_id']

            processar_mencoes(descricao, post_id, user_type, user_id, cursor)

            pasta = os.path.join(current_app.root_path, UPLOAD_FOLDER_FEED)
            os.makedirs(pasta, exist_ok=True)

            for foto in fotos:
                if foto and foto.filename and extensao_permitida(foto.filename):
                    filename = f"{post_id}_{secure_filename(foto.filename)}"
                    caminho = os.path.join(pasta, filename)
                    foto.save(caminho)
                    cursor.execute("""
                        INSERT INTO fotos_post (post_id, caminho) VALUES (%s, %s)
                    """, (post_id, filename))

            conn.commit()
            cursor.close()
            conn.close()

            flash("Post publicado com sucesso!", "success")
            return redirect(url_for('feed.feed'))

        except Exception as e:
            flash(f"Erro ao publicar: {e}", "danger")

    return render_template('novo_post.html', usuarios=buscar_usuarios())


# ─────────────────────────────────────────────
# CURTIR / DESCURTIR
# ─────────────────────────────────────────────
@feed_bp.route('/feed/curtir/<int:post_id>', methods=['POST'])
def curtir_post(post_id):
    user_id = session.get('user_id')
    user_type = session.get('user_type')

    if not user_id or user_type not in ('palestrante', 'instituicao'):
        return redirect(url_for('feed.feed'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT id FROM curtidas_post
        WHERE post_id = %s AND autor_tipo = %s AND autor_id = %s
    """, (post_id, user_type, user_id))
    ja_curtiu = cursor.fetchone()

    if ja_curtiu:
        cursor.execute("DELETE FROM curtidas_post WHERE id = %s", (ja_curtiu['id'],))
    else:
        cursor.execute("""
            INSERT INTO curtidas_post (post_id, autor_tipo, autor_id)
            VALUES (%s, %s, %s)
        """, (post_id, user_type, user_id))
        criar_notificacao(cursor, post_id, user_type, user_id, 'curtida')

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('feed.feed') + f'#post-{post_id}')


# ─────────────────────────────────────────────
# COMENTAR
# ─────────────────────────────────────────────
@feed_bp.route('/feed/comentar/<int:post_id>', methods=['POST'])
def comentar_post(post_id):
    user_id = session.get('user_id')
    user_type = session.get('user_type')

    if not user_id or user_type not in ('palestrante', 'instituicao'):
        return redirect(url_for('feed.feed'))

    texto = request.form.get('texto', '').strip()
    comentario_pai_id = request.form.get('comentario_pai_id')

    if not texto:
        flash("O comentário não pode ser vazio.", "danger")
        return redirect(url_for('feed.ver_post', post_id=post_id))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        INSERT INTO comentarios_post (post_id, autor_tipo, autor_id, texto, comentario_pai_id)
        VALUES (%s, %s, %s, %s, %s)
    """, (post_id, user_type, user_id, texto, comentario_pai_id or None))

    processar_mencoes(texto, post_id, user_type, user_id, cursor)

    if comentario_pai_id:
        cursor.execute("SELECT autor_tipo, autor_id FROM comentarios_post WHERE id = %s", (comentario_pai_id,))
        pai = cursor.fetchone()
        if pai and not (pai['autor_tipo'] == user_type and pai['autor_id'] == user_id):
            cursor.execute("""
                INSERT INTO notificacoes (destinatario_tipo, destinatario_id, tipo, post_id, autor_tipo, autor_id)
                VALUES (%s, %s, 'resposta_comentario', %s, %s, %s)
            """, (pai['autor_tipo'], pai['autor_id'], post_id, user_type, user_id))
    else:
        criar_notificacao(cursor, post_id, user_type, user_id, 'comentario')

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('feed.ver_post', post_id=post_id))


# ─────────────────────────────────────────────
# VER POST
# ─────────────────────────────────────────────
@feed_bp.route('/feed/post/<int:post_id>')
def ver_post(post_id):
    user_id = session.get('user_id')
    user_type = session.get('user_type')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT p.*, COUNT(DISTINCT c.id) AS total_curtidas
        FROM posts_feed p
        LEFT JOIN curtidas_post c ON c.post_id = p.id
        WHERE p.id = %s
        GROUP BY p.id
    """, (post_id,))
    post = cursor.fetchone()

    if not post:
        flash("Post não encontrado.", "danger")
        return redirect(url_for('feed.feed'))

    post['autor_nome'] = get_autor_nome(cursor, post['autor_tipo'], post['autor_id'])
    cursor.execute("SELECT caminho FROM fotos_post WHERE post_id = %s", (post_id,))
    post['fotos'] = cursor.fetchall()

    post['ja_curtiu'] = False
    if user_id and user_type:
        cursor.execute("""
            SELECT id FROM curtidas_post
            WHERE post_id = %s AND autor_tipo = %s AND autor_id = %s
        """, (post_id, user_type, user_id))
        post['ja_curtiu'] = cursor.fetchone() is not None

    cursor.execute("""
        SELECT cm.id, cm.texto, cm.autor_tipo, cm.autor_id, cm.criado_em, cm.comentario_pai_id
        FROM comentarios_post cm
        WHERE cm.post_id = %s
        ORDER BY cm.criado_em ASC
    """, (post_id,))
    comentarios_raw = cursor.fetchall()

    comentarios = []
    mapa = {}
    for c in comentarios_raw:
        c['autor_nome'] = get_autor_nome(cursor, c['autor_tipo'], c['autor_id'])
        c['respostas'] = []
        mapa[c['id']] = c

    for c in comentarios_raw:
        if c['comentario_pai_id'] and c['comentario_pai_id'] in mapa:
            mapa[c['comentario_pai_id']]['respostas'].append(c)
        else:
            comentarios.append(c)

    cursor.close()
    conn.close()

    return render_template('ver_post.html', post=post, comentarios=comentarios,
                           user_id=user_id, user_type=user_type, usuarios=buscar_usuarios())


# ─────────────────────────────────────────────
# NOTIFICAÇÕES
# ─────────────────────────────────────────────
@feed_bp.route('/feed/notificacoes')
def notificacoes():
    user_id = session.get('user_id')
    user_type = session.get('user_type')

    if not user_id or user_type not in ('palestrante', 'instituicao'):
        return redirect(url_for('feed.feed'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT n.id, n.tipo, n.post_id, n.autor_tipo, n.autor_id, n.lida, n.criado_em,
               pf.descricao AS post_descricao
        FROM notificacoes n
        JOIN posts_feed pf ON n.post_id = pf.id
        WHERE n.destinatario_tipo = %s AND n.destinatario_id = %s
        ORDER BY n.criado_em DESC
        LIMIT 50
    """, (user_type, user_id))
    notifs_raw = cursor.fetchall()

    notificacoes_lista = []
    for n in notifs_raw:
        n['autor_nome'] = get_autor_nome(cursor, n['autor_tipo'], n['autor_id'])
        if n['tipo'] == 'curtida':
            n['mensagem'] = f"{n['autor_nome']} curtiu seu post"
        elif n['tipo'] == 'comentario':
            n['mensagem'] = f"{n['autor_nome']} comentou no seu post"
        elif n['tipo'] == 'mencao':
            n['mensagem'] = f"{n['autor_nome']} mencionou você em um post"
        else:
            n['mensagem'] = f"{n['autor_nome']} respondeu seu comentário"
        notificacoes_lista.append(n)

    cursor.execute("""
        UPDATE notificacoes SET lida = 1
        WHERE destinatario_tipo = %s AND destinatario_id = %s AND lida = 0
    """, (user_type, user_id))
    conn.commit()
    cursor.close()
    conn.close()

    return render_template('notificacoes.html', notificacoes=notificacoes_lista, user_type=user_type)


# ─────────────────────────────────────────────
# API — CONTAR NOTIFICAÇÕES
# ─────────────────────────────────────────────
@feed_bp.route('/feed/notificacoes/count')
def contar_notificacoes():
    user_id = session.get('user_id')
    user_type = session.get('user_type')

    if not user_id or user_type not in ('palestrante', 'instituicao'):
        return jsonify({'count': 0})

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT COUNT(*) AS total FROM notificacoes
        WHERE destinatario_tipo = %s AND destinatario_id = %s AND lida = 0
    """, (user_type, user_id))
    total = cursor.fetchone()['total']
    cursor.close()
    conn.close()

    return jsonify({'count': total})


# ─────────────────────────────────────────────
# DELETAR POST
# ─────────────────────────────────────────────
@feed_bp.route('/feed/deletar/<int:post_id>', methods=['POST'])
def deletar_post(post_id):
    user_id = session.get('user_id')
    user_type = session.get('user_type')

    if not user_id:
        return redirect(url_for('feed.feed'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, autor_tipo, autor_id FROM posts_feed
        WHERE id = %s AND autor_tipo = %s AND autor_id = %s
    """, (post_id, user_type, user_id))
    post = cursor.fetchone()

    if not post:
        flash("Post não encontrado ou acesso negado.", "danger")
        return redirect(url_for('feed.feed'))

    cursor.execute("SELECT caminho FROM fotos_post WHERE post_id = %s", (post_id,))
    fotos = cursor.fetchall()
    for foto in fotos:
        caminho = os.path.join(current_app.root_path, UPLOAD_FOLDER_FEED, foto['caminho'])
        if os.path.exists(caminho):
            os.remove(caminho)

    cursor.execute("DELETE FROM posts_feed WHERE id = %s", (post_id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash("Post deletado com sucesso.", "success")
    return redirect(url_for('feed.feed'))


# ─────────────────────────────────────────────
# PERFIL PÚBLICO — PALESTRANTE
# ─────────────────────────────────────────────
@feed_bp.route('/perfil/palestrante/<int:palestrante_id>')
def perfil_palestrante(palestrante_id):
    user_id = session.get('user_id')
    user_type = session.get('user_type')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM palestrantes WHERE id = %s", (palestrante_id,))
    perfil = cursor.fetchone()
    if not perfil:
        return "Não encontrado", 404
    perfil['display_name'] = perfil['nome_completo']

    cursor.execute("SELECT COUNT(*) as total FROM seguidores WHERE seguido_tipo='palestrante' AND seguido_id=%s", (palestrante_id,))
    total_seguidores = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as total FROM seguidores WHERE seguidor_tipo='palestrante' AND seguidor_id=%s", (palestrante_id,))
    total_seguindo = cursor.fetchone()['total']

    

    cursor.execute("""
        SELECT p.* FROM posts_feed p 
        WHERE p.autor_tipo = 'palestrante' AND p.autor_id = %s
        ORDER BY p.criado_em DESC
    """, (palestrante_id,))
    posts_raw = cursor.fetchall()
    for post in posts_raw:
        post['autor_nome'] = perfil['nome_completo']
        cursor.execute("SELECT caminho FROM fotos_post WHERE post_id = %s", (post['id'],))
        post['fotos'] = cursor.fetchall()

    ja_segue = False
    if user_id and user_type:
        cursor.execute("""SELECT id FROM seguidores WHERE seguidor_tipo=%s AND seguidor_id=%s 
                          AND seguido_tipo='palestrante' AND seguido_id=%s""",
                       (user_type, user_id, palestrante_id))
        ja_segue = cursor.fetchone() is not None

    # ✅ Usando as funções auxiliares
    lista_seguidores = buscar_lista_seguidores(cursor, 'palestrante', palestrante_id)
    print(f"🔴 lista_seguidores: {lista_seguidores}") 
    lista_seguindo = buscar_lista_seguindo(cursor, 'palestrante', palestrante_id)

    cursor.close()
    conn.close()
    return render_template('perfil_palestrante.html',
                           perfil=perfil, total_seguidores=total_seguidores,
                           total_seguindo=total_seguindo, ja_segue=ja_segue,
                           user_id=user_id, user_type=user_type, posts=posts_raw,
                           lista_seguidores=lista_seguidores, lista_seguindo=lista_seguindo)


# ─────────────────────────────────────────────
# PERFIL PÚBLICO — INSTITUIÇÃO
# ─────────────────────────────────────────────
@feed_bp.route('/perfil/instituicao/<int:instituicao_id>')
def perfil_instituicao(instituicao_id):
    user_id = session.get('user_id')
    user_type = session.get('user_type')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM instituicoes WHERE id = %s", (instituicao_id,))
    perfil = cursor.fetchone()
    if not perfil:
        return "Não encontrado", 404
    perfil['display_name'] = perfil['nome']

    cursor.execute("SELECT COUNT(*) as total FROM seguidores WHERE seguido_tipo='instituicao' AND seguido_id=%s", (instituicao_id,))
    total_seguidores = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as total FROM seguidores WHERE seguidor_tipo='instituicao' AND seguidor_id=%s", (instituicao_id,))
    total_seguindo = cursor.fetchone()['total']

    cursor.execute("""
        SELECT p.* FROM posts_feed p 
        WHERE p.autor_tipo = 'instituicao' AND p.autor_id = %s
        ORDER BY p.criado_em DESC
    """, (instituicao_id,))
    posts_raw = cursor.fetchall()
    for post in posts_raw:
        post['autor_nome'] = perfil['nome']
        cursor.execute("SELECT caminho FROM fotos_post WHERE post_id = %s", (post['id'],))
        post['fotos'] = cursor.fetchall()

    ja_segue = False
    if user_id and user_type:
        cursor.execute("""SELECT id FROM seguidores WHERE seguidor_tipo=%s AND seguidor_id=%s 
                          AND seguido_tipo='instituicao' AND seguido_id=%s""",
                       (user_type, user_id, instituicao_id))
        ja_segue = cursor.fetchone() is not None

    # ✅ Usando as funções auxiliares
    lista_seguidores = buscar_lista_seguidores(cursor, 'instituicao', instituicao_id)
    lista_seguindo = buscar_lista_seguindo(cursor, 'instituicao', instituicao_id)

    cursor.close()
    conn.close()
    return render_template('perfil_instituicao.html',
                           perfil=perfil, total_seguidores=total_seguidores,
                           total_seguindo=total_seguindo, ja_segue=ja_segue,
                           user_id=user_id, user_type=user_type, posts=posts_raw,
                           lista_seguidores=lista_seguidores, lista_seguindo=lista_seguindo)


# ─────────────────────────────────────────────
# MEU PERFIL — PALESTRANTE
# ─────────────────────────────────────────────
@feed_bp.route('/meu_perfil_pal')
def meu_perfil_pal():
    user_id = session.get('user_id')
    user_type = session.get('user_type')

    if not user_id or user_type != 'palestrante':
        return redirect(url_for('feed.feed'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM palestrantes WHERE id = %s", (user_id,))
    perfil = cursor.fetchone()
    perfil['display_name'] = perfil['nome_completo']

    cursor.execute("SELECT COUNT(*) as total FROM seguidores WHERE seguido_tipo='palestrante' AND seguido_id=%s", (user_id,))
    total_seguidores = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as total FROM seguidores WHERE seguidor_tipo='palestrante' AND seguidor_id=%s", (user_id,))
    total_seguindo = cursor.fetchone()['total']

    cursor.execute("""
        SELECT p.* FROM posts_feed p 
        WHERE p.autor_tipo = 'palestrante' AND p.autor_id = %s
        ORDER BY p.criado_em DESC
    """, (user_id,))
    meus_posts = cursor.fetchall()
    for post in meus_posts:
        cursor.execute("SELECT caminho FROM fotos_post WHERE post_id = %s", (post['id'],))
        post['fotos'] = cursor.fetchall()

   
    lista_seguidores = buscar_lista_seguidores(cursor, 'palestrante', user_id)
    lista_seguindo = buscar_lista_seguindo(cursor, 'palestrante', user_id)

    cursor.close()
    conn.close()

    return render_template('meu_perfil_palestrante.html',
                           perfil=perfil, total_seguidores=total_seguidores,
                           total_seguindo=total_seguindo, posts=meus_posts,
                           lista_seguidores=lista_seguidores, lista_seguindo=lista_seguindo)


# ─────────────────────────────────────────────
# MEU PERFIL — INSTITUIÇÃO
# ─────────────────────────────────────────────
@feed_bp.route('/meu_perfil_inst')
def meu_perfil_inst():
    user_id = session.get('user_id')
    user_type = session.get('user_type')

    if not user_id or user_type != 'instituicao':
        return redirect(url_for('feed.feed'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM instituicoes WHERE id = %s", (user_id,))
    perfil = cursor.fetchone()
    perfil['display_name'] = perfil['nome']

    cursor.execute("SELECT COUNT(*) as total FROM seguidores WHERE seguido_tipo='instituicao' AND seguido_id=%s", (user_id,))
    total_seguidores = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as total FROM seguidores WHERE seguidor_tipo='instituicao' AND seguidor_id=%s", (user_id,))
    total_seguindo = cursor.fetchone()['total']

    cursor.execute("""
        SELECT p.* FROM posts_feed p 
        WHERE p.autor_tipo = 'instituicao' AND p.autor_id = %s
        ORDER BY p.criado_em DESC
    """, (user_id,))
    meus_posts = cursor.fetchall()
    for post in meus_posts:
        cursor.execute("SELECT caminho FROM fotos_post WHERE post_id = %s", (post['id'],))
        post['fotos'] = cursor.fetchall()

    # ✅ user_id em vez de palestrante_id
    lista_seguidores = buscar_lista_seguidores(cursor, 'instituicao', user_id)
    lista_seguindo = buscar_lista_seguindo(cursor, 'instituicao', user_id)

    cursor.close()
    conn.close()

    return render_template('meu_perfil_instituicao.html',
                           perfil=perfil, total_seguidores=total_seguidores,
                           total_seguindo=total_seguindo, posts=meus_posts,
                           lista_seguidores=lista_seguidores, lista_seguindo=lista_seguindo)