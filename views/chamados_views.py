from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from utils.security import login_required
from utils.mail import send_notification_email
import mysql.connector

chamados_bp = Blueprint('chamados', __name__)

CATEGORIAS = {
    'conduta_inadequada': 'Conduta Inadequada',
    'nao_comparecimento': 'Não Comparecimento',
    'cancelamento_sem_aviso': 'Cancelamento Sem Aviso'
}

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="palestra"
    )

@chamados_bp.route('/chamado/abrir/<int:palestra_id>', methods=['GET', 'POST'])
def abrir_chamado(palestra_id):
    user_id = session.get('user_id')
    user_type = session.get('user_type')

    if not user_id or user_type not in ('palestrante', 'instituicao'):
        return redirect(url_for('login_palestrante.login_palestrante'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT pc.id, pc.titulo, pc.data,
               p.nome_completo AS nome_palestrante, p.id AS palestrante_id,
               i.nome AS nome_instituicao, i.id AS instituicao_id
        FROM palestras_confirmadas pc
        JOIN palestrantes p ON pc.palestrante_id = p.id
        JOIN instituicoes i ON pc.instituicao_id = i.id
        WHERE pc.id = %s
    """, (palestra_id,))
    palestra = cursor.fetchone()

    if not palestra:
        flash("Palestra não encontrada.", "danger")
        return redirect(url_for('login_palestrante.painel_palestrante'))

    if user_type == 'palestrante' and palestra['palestrante_id'] != user_id:
        flash("Acesso negado.", "danger")
        return redirect(url_for('login_palestrante.painel_palestrante'))
    if user_type == 'instituicao' and palestra['instituicao_id'] != user_id:
        flash("Acesso negado.", "danger")
        return redirect(url_for('login_instituicao.painel_instituicao'))

    if request.method == 'POST':
        categoria = request.form.get('categoria')
        descricao = request.form.get('descricao', '').strip()

        if not categoria or not descricao:
            flash("Preencha todos os campos.", "danger")
        elif categoria not in CATEGORIAS:
            flash("Categoria inválida.", "danger")
        else:
            try:
                cursor.execute("""
                    INSERT INTO chamados (palestra_id, aberto_por_tipo, aberto_por_id, categoria, descricao)
                    VALUES (%s, %s, %s, %s, %s)
                """, (palestra_id, user_type, user_id, categoria, descricao))
                conn.commit()

                cursor.execute("SELECT LAST_INSERT_ID() AS chamado_id")
                chamado_id_novo = cursor.fetchone()['chamado_id']

                if user_type == 'palestrante':
                    cursor.execute("SELECT email, nome_completo FROM palestrantes WHERE id = %s", (user_id,))
                else:
                    cursor.execute("SELECT email, nome AS nome_completo FROM instituicoes WHERE id = %s", (user_id,))

                quem_abriu = cursor.fetchone()
                nome_quem_abriu = quem_abriu['nome_completo'] if quem_abriu else ''

                if quem_abriu:
                    send_notification_email(
                        recipient=quem_abriu['email'],
                        subject=f"✅ Chamado #{chamado_id_novo} aberto com sucesso - {CATEGORIAS[categoria]}",
                        body=f"""Olá, {quem_abriu['nome_completo']}!

Seu chamado foi aberto com sucesso e já está sendo analisado pela administração.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 DETALHES DO CHAMADO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Número do Chamado: #{chamado_id_novo}
Palestra: {palestra['titulo']}
Data da palestra: {palestra['data']}
Categoria: {CATEGORIAS[categoria]}

Descrição enviada:
{descricao}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏳ PRÓXIMOS PASSOS:
- O administrador irá analisar sua solicitação
- Você receberá atualizações por e-mail
- Acompanhe o status pelo sistema em "Meus Chamados"

⚠️ IMPORTANTE:
- Não abra chamados duplicados sobre o mesmo problema
- Guarde este e-mail como comprovante — Chamado #{chamado_id_novo}
- Em caso de dúvidas, acesse o sistema

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Atenciosamente,
Administração da Plataforma"""
                    )

                cursor.execute("SELECT email FROM admins LIMIT 1")
                admin = cursor.fetchone()
                if admin:
                    send_notification_email(
                        recipient=admin['email'],
                        subject=f"🚨 Novo Chamado #{chamado_id_novo}: {CATEGORIAS[categoria]} - {palestra['titulo']}",
                        body=f"""Um novo chamado foi aberto no sistema.

Número do Chamado: #{chamado_id_novo}
Palestra: {palestra['titulo']}
Data: {palestra['data']}
Aberto por: {nome_quem_abriu} ({user_type})
Categoria: {CATEGORIAS[categoria]}

Descrição:
{descricao}

Acesse o sistema para responder."""
                    )

                flash("Chamado aberto com sucesso! Você receberá um e-mail de confirmação.", "success")
                cursor.close()
                conn.close()
                return redirect(url_for('chamados.meus_chamados'))

            except Exception as e:
                flash(f"Erro ao abrir chamado: {e}", "danger")

    cursor.close()
    conn.close()
    return render_template('abrir_chamado.html', palestra=palestra, categorias=CATEGORIAS)


@chamados_bp.route('/chamados/meus')
def meus_chamados():
    user_id = session.get('user_id')
    user_type = session.get('user_type')

    if not user_id or user_type not in ('palestrante', 'instituicao'):
        return redirect(url_for('login_palestrante.login_palestrante'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT c.id, c.categoria, c.status, c.criado_em,
               pc.titulo, pc.data,
               p.nome_completo AS nome_palestrante,
               i.nome AS nome_instituicao
        FROM chamados c
        JOIN palestras_confirmadas pc ON c.palestra_id = pc.id
        JOIN palestrantes p ON pc.palestrante_id = p.id
        JOIN instituicoes i ON pc.instituicao_id = i.id
        WHERE c.aberto_por_tipo = %s AND c.aberto_por_id = %s
        ORDER BY c.criado_em DESC
    """, (user_type, user_id))
    chamados = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('meus_chamados.html', chamados=chamados, categorias=CATEGORIAS)


@chamados_bp.route('/chamado/<int:chamado_id>', methods=['GET', 'POST'])
def ver_chamado(chamado_id):
    user_id = session.get('user_id')
    user_type = session.get('user_type')

    if not user_id or user_type not in ('palestrante', 'instituicao', 'administrador'):
        return redirect(url_for('login_palestrante.login_palestrante'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT c.*, pc.titulo, pc.data,
               p.nome_completo AS nome_palestrante, p.id AS palestrante_id, p.email AS email_palestrante,
               i.nome AS nome_instituicao, i.id AS instituicao_id, i.email AS email_instituicao
        FROM chamados c
        JOIN palestras_confirmadas pc ON c.palestra_id = pc.id
        JOIN palestrantes p ON pc.palestrante_id = p.id
        JOIN instituicoes i ON pc.instituicao_id = i.id
        WHERE c.id = %s
    """, (chamado_id,))
    chamado = cursor.fetchone()

    if not chamado:
        flash("Chamado não encontrado.", "danger")
        return redirect(url_for('chamados.meus_chamados'))

    if user_type == 'palestrante' and chamado['palestrante_id'] != user_id:
        flash("Acesso negado.", "danger")
        return redirect(url_for('chamados.meus_chamados'))
    if user_type == 'instituicao' and chamado['instituicao_id'] != user_id:
        flash("Acesso negado.", "danger")
        return redirect(url_for('chamados.meus_chamados'))

    if request.method == 'POST':
        acao = request.form.get('acao', 'mensagem')

        # ── 1. MENSAGEM NORMAL ──
        if acao == 'mensagem':
            mensagem = request.form.get('mensagem', '').strip()
            novo_status = request.form.get('status')
            if mensagem:
                cursor.execute("""
                    INSERT INTO mensagens_chamado (chamado_id, remetente_tipo, remetente_id, mensagem)
                    VALUES (%s, %s, %s, %s)
                """, (chamado_id, user_type, user_id, mensagem))

                if user_type == 'administrador' and novo_status in ('aberto', 'em_andamento', 'resolvido'):
                    cursor.execute("UPDATE chamados SET status = %s WHERE id = %s", (novo_status, chamado_id))

                    # ✅ Se resolvido, envia e-mail de avaliação
                    if novo_status == 'resolvido':
                        cursor.execute("""
                            SELECT c.aberto_por_tipo, c.aberto_por_id, pc.titulo
                            FROM chamados c
                            JOIN palestras_confirmadas pc ON c.palestra_id = pc.id
                            WHERE c.id = %s
                        """, (chamado_id,))
                        dados_chamado = cursor.fetchone()

                        if dados_chamado['aberto_por_tipo'] == 'palestrante':
                            cursor.execute("SELECT email, nome_completo FROM palestrantes WHERE id = %s", (dados_chamado['aberto_por_id'],))
                        else:
                            cursor.execute("SELECT email, nome AS nome_completo FROM instituicoes WHERE id = %s", (dados_chamado['aberto_por_id'],))

                        quem_abriu = cursor.fetchone()
                        if quem_abriu:
                            link_avaliacao = url_for('chamados.avaliar_chamado', chamado_id=chamado_id, _external=True)
                            send_notification_email(
                                recipient=quem_abriu['email'],
                                subject=f"⭐ Como foi o atendimento? Avalie o Chamado #{chamado_id}",
                                body=f"""Olá, {quem_abriu['nome_completo']}!

O chamado #{chamado_id} referente à palestra "{dados_chamado['titulo']}" foi marcado como resolvido.

Gostaríamos de saber sua opinião sobre o atendimento recebido. Sua avaliação é muito importante para continuarmos melhorando nossa plataforma!

Clique no link abaixo para avaliar:
{link_avaliacao}

A avaliação leva menos de 1 minuto. 😊

Atenciosamente,
Administração da Plataforma"""
                            )
                conn.commit()

        # ── 2. NOTIFICAR ──
        elif acao == 'notificar' and user_type == 'administrador':
            destinatario = request.form.get('destinatario')
            msg_notificacao = request.form.get('msg_notificacao', '').strip()

            if destinatario == 'palestrante':
                email_dest = chamado['email_palestrante']
                nome_dest = chamado['nome_palestrante']
            else:
                email_dest = chamado['email_instituicao']
                nome_dest = chamado['nome_instituicao']

            if msg_notificacao and email_dest:
                send_notification_email(
                    recipient=email_dest,
                    subject=f"📋 Notificação do Administrador - Chamado #{chamado_id}",
                    body=f"""Olá, {nome_dest}.

O administrador da plataforma enviou uma notificação referente ao chamado #{chamado_id}:

Palestra: {chamado['titulo']}
Categoria: {CATEGORIAS[chamado['categoria']]}

Mensagem do Administrador:
{msg_notificacao}

Acesse o sistema para mais detalhes."""
                )
                cursor.execute("""
                    INSERT INTO mensagens_chamado (chamado_id, remetente_tipo, remetente_id, mensagem)
                    VALUES (%s, 'administrador', %s, %s)
                """, (chamado_id, user_id, "📧 O administrador enviou uma notificação para a outra parte. Uma providência está sendo tomada referente a este chamado."))
                conn.commit()
                flash(f"Notificação enviada para {nome_dest} por e-mail.", "success")

        # ── 3. AVISO FORMAL ──
        elif acao == 'aviso_formal' and user_type == 'administrador':
            destinatario_tipo = request.form.get('destinatario_tipo')
            msg_aviso = request.form.get('msg_aviso', '').strip()

            if destinatario_tipo == 'palestrante':
                destinatario_id = chamado['palestrante_id']
                email_dest = chamado['email_palestrante']
                nome_dest = chamado['nome_palestrante']
            else:
                destinatario_id = chamado['instituicao_id']
                email_dest = chamado['email_instituicao']
                nome_dest = chamado['nome_instituicao']

            if msg_aviso:
                cursor.execute("""
                    INSERT INTO avisos_formais (chamado_id, destinatario_tipo, destinatario_id, admin_id, mensagem)
                    VALUES (%s, %s, %s, %s, %s)
                """, (chamado_id, destinatario_tipo, destinatario_id, user_id, msg_aviso))
                cursor.execute("""
                    INSERT INTO mensagens_chamado (chamado_id, remetente_tipo, remetente_id, mensagem)
                    VALUES (%s, 'administrador', %s, %s)
                """, (chamado_id, user_id, "⚠️ Um aviso formal foi emitido para a outra parte. O administrador está acompanhando este chamado."))
                conn.commit()

                send_notification_email(
                    recipient=email_dest,
                    subject=f"⚠️ Aviso Formal - Plataforma de Palestras",
                    body=f"""Olá, {nome_dest}.

Você recebeu um AVISO FORMAL da administração da plataforma.

Referente ao chamado #{chamado_id} - {CATEGORIAS[chamado['categoria']]}
Palestra: {chamado['titulo']}

Aviso:
{msg_aviso}

Este aviso fica registrado em seu histórico na plataforma.
Reincidências poderão resultar em suspensão ou banimento.

Atenciosamente,
Administração da Plataforma"""
                )
                flash(f"Aviso formal emitido e enviado para {nome_dest}.", "success")

        # ── 4. SUSPENDER / BANIR ──
        elif acao in ('suspender', 'banir') and user_type == 'administrador':
            alvo_tipo = request.form.get('alvo_tipo')
            novo_status_usuario = 'suspenso' if acao == 'suspender' else 'banido'
            motivo = request.form.get('motivo_punicao', '').strip()

            if alvo_tipo == 'palestrante':
                alvo_id = chamado['palestrante_id']
                email_dest = chamado['email_palestrante']
                nome_dest = chamado['nome_palestrante']
                cursor.execute("UPDATE palestrantes SET status = %s WHERE id = %s", (novo_status_usuario, alvo_id))
            else:
                alvo_id = chamado['instituicao_id']
                email_dest = chamado['email_instituicao']
                nome_dest = chamado['nome_instituicao']
                cursor.execute("UPDATE instituicoes SET status = %s WHERE id = %s", (novo_status_usuario, alvo_id))

            cursor.execute("""
                INSERT INTO mensagens_chamado (chamado_id, remetente_tipo, remetente_id, mensagem)
                VALUES (%s, 'administrador', %s, %s)
            """, (chamado_id, user_id, "🚫 O administrador tomou uma medida disciplinar referente a este chamado. Este chamado foi encerrado."))
            cursor.execute("UPDATE chamados SET status = 'resolvido' WHERE id = %s", (chamado_id,))
            conn.commit()

            send_notification_email(
                recipient=email_dest,
                subject=f"🚫 Conta {'Suspensa' if novo_status_usuario == 'suspenso' else 'Banida'} - Plataforma de Palestras",
                body=f"""Olá, {nome_dest}.

Sua conta foi {'suspensa' if novo_status_usuario == 'suspenso' else 'banida permanentemente'} da plataforma.

Motivo: {motivo}

{'Entre em contato com a administração para mais informações.' if novo_status_usuario == 'suspenso' else 'Esta decisão é definitiva.'}

Atenciosamente,
Administração da Plataforma"""
            )
            flash(f"{nome_dest} foi {'suspenso' if novo_status_usuario == 'suspenso' else 'banido'} com sucesso.", "success")

        return redirect(url_for('chamados.ver_chamado', chamado_id=chamado_id))

    cursor.execute("""
        SELECT mc.mensagem, mc.remetente_tipo, mc.enviada_em, mc.remetente_id,
               COALESCE(p.nome_completo, i.nome, a.nome_completo) AS remetente_nome
        FROM mensagens_chamado mc
        LEFT JOIN palestrantes p ON mc.remetente_tipo = 'palestrante' AND mc.remetente_id = p.id
        LEFT JOIN instituicoes i ON mc.remetente_tipo = 'instituicao' AND mc.remetente_id = i.id
        LEFT JOIN admins a ON mc.remetente_tipo = 'administrador' AND mc.remetente_id = a.id
        WHERE mc.chamado_id = %s
        ORDER BY mc.enviada_em ASC
    """, (chamado_id,))
    mensagens = cursor.fetchall()

    cursor.execute("""
        SELECT af.mensagem, af.criado_em, af.destinatario_tipo,
               COALESCE(p.nome_completo, i.nome) AS destinatario_nome
        FROM avisos_formais af
        LEFT JOIN palestrantes p ON af.destinatario_tipo = 'palestrante' AND af.destinatario_id = p.id
        LEFT JOIN instituicoes i ON af.destinatario_tipo = 'instituicao' AND af.destinatario_id = i.id
        WHERE af.chamado_id = %s
        ORDER BY af.criado_em DESC
    """, (chamado_id,))
    avisos = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('ver_chamado.html',
                           chamado=chamado,
                           mensagens=mensagens,
                           avisos=avisos,
                           categorias=CATEGORIAS,
                           user_type=user_type,
                           user_id=user_id)


@chamados_bp.route('/chamado/<int:chamado_id>/avaliar', methods=['GET', 'POST'])
def avaliar_chamado(chamado_id):
    user_id = session.get('user_id')
    user_type = session.get('user_type')

    if not user_id or user_type not in ('palestrante', 'instituicao'):
        return redirect(url_for('login_palestrante.login_palestrante'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT c.*, pc.titulo
        FROM chamados c
        JOIN palestras_confirmadas pc ON c.palestra_id = pc.id
        WHERE c.id = %s AND c.status = 'resolvido'
          AND c.aberto_por_tipo = %s AND c.aberto_por_id = %s
    """, (chamado_id, user_type, user_id))
    chamado = cursor.fetchone()

    if not chamado:
        flash("Chamado não encontrado ou você não tem permissão para avaliá-lo.", "danger")
        return redirect(url_for('chamados.meus_chamados'))

    cursor.execute("SELECT id FROM avaliacoes_chamados WHERE chamado_id = %s", (chamado_id,))
    ja_avaliou = cursor.fetchone()

    if request.method == 'POST' and not ja_avaliou:
        nota_atendimento = request.form.get('nota_atendimento')
        nota_experiencia = request.form.get('nota_experiencia')
        comentario = request.form.get('comentario', '').strip()

        if not nota_atendimento or not nota_experiencia:
            flash("Por favor, avalie todos os itens.", "danger")
        else:
            cursor.execute("""
                INSERT INTO avaliacoes_chamados
                (chamado_id, avaliador_tipo, avaliador_id, nota_atendimento, nota_experiencia, comentario)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (chamado_id, user_type, user_id, nota_atendimento, nota_experiencia, comentario or None))
            conn.commit()
            flash("Avaliação enviada! Obrigado pelo feedback. 😊", "success")
            cursor.close()
            conn.close()
            return redirect(url_for('chamados.meus_chamados'))

    cursor.close()
    conn.close()
    return render_template('avaliar_chamado.html', chamado=chamado, ja_avaliou=ja_avaliou)


@chamados_bp.route('/admin/avaliacoes')
@login_required("administrador")
def admin_avaliacoes():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT av.*, c.id AS chamado_id, pc.titulo,
               av.nota_atendimento, av.nota_experiencia, av.comentario, av.criado_em,
               COALESCE(p.nome_completo, i.nome) AS avaliador_nome
        FROM avaliacoes_chamados av
        JOIN chamados c ON av.chamado_id = c.id
        JOIN palestras_confirmadas pc ON c.palestra_id = pc.id
        LEFT JOIN palestrantes p ON av.avaliador_tipo = 'palestrante' AND av.avaliador_id = p.id
        LEFT JOIN instituicoes i ON av.avaliador_tipo = 'instituicao' AND av.avaliador_id = i.id
        ORDER BY av.criado_em DESC
    """)
    avaliacoes = cursor.fetchall()

    cursor.execute("""
        SELECT
            ROUND(AVG(nota_atendimento), 1) AS media_atendimento,
            ROUND(AVG(nota_experiencia), 1) AS media_experiencia,
            COUNT(*) AS total
        FROM avaliacoes_chamados
    """)
    medias = cursor.fetchone()

    cursor.close()
    conn.close()
    return render_template('admin_avaliacoes.html', avaliacoes=avaliacoes, medias=medias)


@chamados_bp.route('/admin/chamados')
@login_required("administrador")
def admin_chamados():
    filtro_status = request.args.get('status', '')
    filtro_categoria = request.args.get('categoria', '')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT c.id, c.categoria, c.status, c.criado_em,
               pc.titulo, pc.data,
               p.nome_completo AS nome_palestrante,
               i.nome AS nome_instituicao,
               c.aberto_por_tipo
        FROM chamados c
        JOIN palestras_confirmadas pc ON c.palestra_id = pc.id
        JOIN palestrantes p ON pc.palestrante_id = p.id
        JOIN instituicoes i ON pc.instituicao_id = i.id
        WHERE 1=1
    """
    params = []

    if filtro_status:
        query += " AND c.status = %s"
        params.append(filtro_status)
    if filtro_categoria:
        query += " AND c.categoria = %s"
        params.append(filtro_categoria)

    query += " ORDER BY c.criado_em DESC"
    cursor.execute(query, params)
    chamados = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('admin_chamados.html',
                           chamados=chamados,
                           categorias=CATEGORIAS,
                           filtro_status=filtro_status,
                           filtro_categoria=filtro_categoria)