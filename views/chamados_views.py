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
                        body=f"""
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
                                            <span style="color:#00d2ff; font-size:0.85rem; font-weight:600; letter-spacing:1px;">📋 CHAMADO ABERTO</span>
                                        </div>
                                        <h2 style="margin:0; color:#f8fafc; font-size:1.4rem;">Olá, {quem_abriu['nome_completo']}!</h2>
                                        <p style="margin:10px 0 0; color:#94a3b8; font-size:0.95rem; line-height:1.6;">
                                            Seu chamado foi aberto com sucesso e já está sendo analisado.
                                        </p>
                                    </td>
                                </tr>


                                <tr>
                                    <td align="center" style="padding-top: 25px; padding-bottom: 20px;">
                                        <div style="background: rgba(0,210,255,0.06); border: 1px solid rgba(0,210,255,0.2); border-radius: 12px; padding: 15px 25px; display:inline-block;">
                                            <p style="margin:0; color:#94a3b8; font-size:0.75rem; text-transform:uppercase; letter-spacing:1px;">Número do Chamado</p>
                                            <p style="margin:5px 0 0; color:#00d2ff; font-size:1.6rem; font-weight:700;">#{chamado_id_novo}</p>
                                        </div>
                                    </td>
                                </tr>

                                <tr>
                                    <td style="padding-bottom: 20px;">
                                        <p style="margin:0 0 12px; color:#94a3b8; font-size:0.75rem; text-transform:uppercase; letter-spacing:1px; font-weight:600;">Detalhes do Chamado</p>
                                        <table width="100%" cellpadding="0" cellspacing="0">
                                            <tr>
                                                <td style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">📋 Palestra</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">{palestra['titulo']}</strong>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">📅 Data da Palestra</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">{palestra['data']}</strong>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">🏷️ Categoria</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">{CATEGORIAS[categoria]}</strong>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 10px 0;">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">📝 Descrição</span><br>
                                                    <span style="color:#cbd5e1; font-size:0.9rem; line-height:1.7;">{descricao}</span>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>


                                <tr>
                                    <td style="padding-bottom: 20px;">
                                        <p style="margin:0 0 12px; color:#94a3b8; font-size:0.75rem; text-transform:uppercase; letter-spacing:1px; font-weight:600;">⏳ Próximos Passos</p>
                                        <div style="background: rgba(0,210,255,0.06); border-left: 3px solid #00d2ff; border-radius: 8px; padding: 15px 18px;">
                                            <p style="margin:0 0 8px; color:#cbd5e1; font-size:0.9rem; line-height:1.7;">• O administrador irá analisar sua solicitação.</p>
                                            <p style="margin:0 0 8px; color:#cbd5e1; font-size:0.9rem; line-height:1.7;">• Você receberá atualizações por e-mail.</p>
                                            <p style="margin:0; color:#cbd5e1; font-size:0.9rem; line-height:1.7;">• Acompanhe o status em <strong style="color:#f8fafc;">Meus Chamados</strong> no sistema.</p>
                                        </div>
                                    </td>
                                </tr>

                                <!-- Importante -->                                <tr>
                                    <td style="padding-bottom: 25px;">
                                        <div style="background: rgba(245,158,11,0.06); border-left: 3px solid #f59e0b; border-radius: 8px; padding: 15px 18px;">
                                            <p style="margin:0 0 4px; color:#f59e0b; font-size:0.8rem; font-weight:600; text-transform:uppercase; letter-spacing:1px;">⚠️ Importante</p>
                                            <p style="margin:0 0 6px; color:#94a3b8; font-size:0.85rem; line-height:1.6;">• Não abra chamados duplicados sobre o mesmo problema.</p>
                                            <p style="margin:0; color:#94a3b8; font-size:0.85rem; line-height:1.6;">• Guarde este e-mail como comprovante — Chamado <strong style="color:#f8fafc;">#{chamado_id_novo}</strong>.</p>
                                        </div>
                                    </td>
                                </tr>


                                <tr>
                                    <td align="center" style="padding-bottom: 10px;">
                                        <a href="http://localhost:5000"
                                           style="display:inline-block; background: linear-gradient(135deg, #00d2ff, #0099cc); color:#000000; font-weight:700; font-size:0.95rem; text-decoration:none; padding: 14px 35px; border-radius: 10px;">
                                            Ver Meus Chamados →
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
                    )

                cursor.execute("SELECT email FROM admins LIMIT 1")
                admin = cursor.fetchone()
                if admin:
                    send_notification_email(
                        recipient=admin['email'],
                        subject=f"🚨 Novo Chamado #{chamado_id_novo}: {CATEGORIAS[categoria]} - {palestra['titulo']}",
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
                            <p style="margin:6px 0 0; color:#94a3b8; font-size:0.85rem;">Painel Administrativo</p>
                        </td>
                    </tr>

            
                    <tr>
                        <td style="background: linear-gradient(135deg, #0f172a, #1e293b); border: 1px solid rgba(0,210,255,0.15); border-radius: 16px; padding: 35px;">
                            <table width="100%" cellpadding="0" cellspacing="0">

                          
                                <tr>
                                    <td align="center" style="padding-bottom: 25px; border-bottom: 1px solid rgba(255,255,255,0.07);">
                                        <div style="background: rgba(245,158,11,0.1); border: 1px solid rgba(245,158,11,0.3); border-radius: 50px; display:inline-block; padding: 10px 22px; margin-bottom: 15px;">
                                            <span style="color:#f59e0b; font-size:0.85rem; font-weight:600; letter-spacing:1px;">🔔 NOVO CHAMADO</span>
                                        </div>
                                        <h2 style="margin:0; color:#f8fafc; font-size:1.4rem;">Novo Chamado Aberto</h2>
                                        <p style="margin:10px 0 0; color:#94a3b8; font-size:0.95rem; line-height:1.6;">
                                            Um usuário abriu um novo chamado e aguarda sua resposta.
                                        </p>
                                    </td>
                                </tr>

                          
                                <tr>
                                    <td align="center" style="padding-top: 25px; padding-bottom: 20px;">
                                        <div style="background: rgba(0,210,255,0.06); border: 1px solid rgba(0,210,255,0.2); border-radius: 12px; padding: 15px 25px; display:inline-block;">
                                            <p style="margin:0; color:#94a3b8; font-size:0.75rem; text-transform:uppercase; letter-spacing:1px;">Número do Chamado</p>
                                            <p style="margin:5px 0 0; color:#00d2ff; font-size:1.6rem; font-weight:700;">#{chamado_id_novo}</p>
                                        </div>
                                    </td>
                                </tr>

    
                                <tr>
                                    <td style="padding-bottom: 20px;">
                                        <p style="margin:0 0 12px; color:#94a3b8; font-size:0.75rem; text-transform:uppercase; letter-spacing:1px; font-weight:600;">Detalhes do Chamado</p>
                                        <table width="100%" cellpadding="0" cellspacing="0">
                                            <tr>
                                                <td style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">👤 Aberto por</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">{nome_quem_abriu} <span style="color:#94a3b8; font-weight:400;">({user_type})</span></strong>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">📋 Palestra</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">{palestra['titulo']}</strong>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">📅 Data da Palestra</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">{palestra['data']}</strong>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">🏷️ Categoria</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">{CATEGORIAS[categoria]}</strong>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 10px 0;">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">📝 Descrição</span><br>
                                                    <span style="color:#cbd5e1; font-size:0.9rem; line-height:1.7;">{descricao}</span>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>


                                <tr>
                                    <td style="padding-bottom: 25px;">
                                        <div style="background: rgba(245,158,11,0.06); border-left: 3px solid #f59e0b; border-radius: 8px; padding: 12px 18px;">
                                            <p style="margin:0; color:#94a3b8; font-size:0.85rem; line-height:1.6;">
                                                ⚠️ Acesse o sistema para analisar e responder este chamado o quanto antes.
                                            </p>
                                        </div>
                                    </td>
                                </tr>


                                <tr>
                                    <td align="center" style="padding-bottom: 10px;">
                                        <a href="http://localhost:5000/administrador/suporte"
                                           style="display:inline-block; background: linear-gradient(135deg, #00d2ff, #0099cc); color:#000000; font-weight:700; font-size:0.95rem; text-decoration:none; padding: 14px 35px; border-radius: 10px;">
                                            Ver Chamados →
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
                                subject= f"""
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
                                        <div style="background: rgba(234,179,8,0.1); border: 1px solid rgba(234,179,8,0.3); border-radius: 50px; display:inline-block; padding: 10px 22px; margin-bottom: 15px;">
                                            <span style="color:#eab308; font-size:0.85rem; font-weight:600; letter-spacing:1px;">⭐ AVALIE O ATENDIMENTO</span>
                                        </div>
                                        <h2 style="margin:0; color:#f8fafc; font-size:1.4rem;">Olá, {quem_abriu['nome_completo']}!</h2>
                                        <p style="margin:10px 0 0; color:#94a3b8; font-size:0.95rem; line-height:1.6;">
                                            O chamado <strong style="color:#f8fafc;">#{chamado_id}</strong> foi marcado como resolvido!
                                        </p>
                                    </td>
                                </tr>

                                <tr>
                                    <td style="padding-top: 25px; padding-bottom: 20px;">
                                        <p style="margin:0 0 12px; color:#94a3b8; font-size:0.75rem; text-transform:uppercase; letter-spacing:1px; font-weight:600;">Chamado Resolvido</p>
                                        <div style="background: rgba(16,185,129,0.06); border-left: 3px solid #10b981; border-radius: 8px; padding: 15px 18px;">
                                            <p style="margin:0 0 4px; color:#94a3b8; font-size:0.85rem;">Palestra</p>
                                            <strong style="color:#f8fafc; font-size:0.95rem;">"{dados_chamado['titulo']}"</strong>
                                        </div>
                                    </td>
                                </tr>


                                <tr>
                                    <td align="center" style="padding-bottom: 20px;">
                                        <p style="margin:0 0 10px; color:#94a3b8; font-size:0.9rem; line-height:1.6;">
                                            Sua opinião é muito importante para continuarmos melhorando a plataforma!<br>
                                            A avaliação leva menos de 1 minuto. 😊
                                        </p>
                                        <p style="margin:0; font-size:1.8rem; letter-spacing:4px;">⭐⭐⭐⭐⭐</p>
                                    </td>
                                </tr>


                                <tr>
                                    <td style="padding-bottom: 25px;">
                                        <p style="margin:0 0 8px; color:#94a3b8; font-size:0.75rem; text-transform:uppercase; letter-spacing:1px; font-weight:600;">Ou copie o link abaixo</p>
                                        <div style="background: rgba(0,0,0,0.25); border-left: 3px solid #475569; border-radius: 8px; padding: 12px 18px; word-break: break-all;">
                                            <p style="margin:0; color:#94a3b8; font-size:0.8rem; line-height:1.6;">
                                                {link_avaliacao}
                                            </p>
                                        </div>
                                    </td>
                                </tr>

                                <tr>
                                    <td align="center" style="padding-bottom: 10px;">
                                        <a href="{link_avaliacao}"
                                           style="display:inline-block; background: linear-gradient(135deg, #eab308, #ca8a04); color:#000000; font-weight:700; font-size:0.95rem; text-decoration:none; padding: 14px 35px; border-radius: 10px;">
                                            ⭐ Avaliar Atendimento →
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
                            )
                conn.commit()

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
                    body=f"""
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
                                            <span style="color:#00d2ff; font-size:0.85rem; font-weight:600; letter-spacing:1px;">🔔 NOTIFICAÇÃO DO ADMIN</span>
                                        </div>
                                        <h2 style="margin:0; color:#f8fafc; font-size:1.4rem;">Olá, {nome_dest}!</h2>
                                        <p style="margin:10px 0 0; color:#94a3b8; font-size:0.95rem; line-height:1.6;">
                                            Você recebeu uma notificação referente ao chamado <strong style="color:#f8fafc;">#{chamado_id}</strong>.
                                        </p>
                                    </td>
                                </tr>


                                <tr>
                                    <td style="padding-top: 25px; padding-bottom: 20px;">
                                        <p style="margin:0 0 12px; color:#94a3b8; font-size:0.75rem; text-transform:uppercase; letter-spacing:1px; font-weight:600;">Detalhes do Chamado</p>
                                        <table width="100%" cellpadding="0" cellspacing="0">
                                            <tr>
                                                <td style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">📋 Palestra</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">{chamado['titulo']}</strong>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 10px 0;">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">🏷️ Categoria</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">{CATEGORIAS[chamado['categoria']]}</strong>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>


                                <tr>
                                    <td style="padding-bottom: 25px;">
                                        <p style="margin:0 0 10px; color:#94a3b8; font-size:0.75rem; text-transform:uppercase; letter-spacing:1px; font-weight:600;">Mensagem do Administrador</p>
                                        <div style="background: rgba(0,210,255,0.06); border-left: 3px solid #00d2ff; border-radius: 8px; padding: 15px 18px;">
                                            <p style="margin:0; color:#f8fafc; font-size:0.95rem; line-height:1.7;">
                                                {msg_notificacao}
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
                )
                cursor.execute("""
                    INSERT INTO mensagens_chamado (chamado_id, remetente_tipo, remetente_id, mensagem)
                    VALUES (%s, 'administrador', %s, %s)
                """, (chamado_id, user_id, "📧 O administrador enviou uma notificação para a outra parte. Uma providência está sendo tomada referente a este chamado."))
                conn.commit()
                flash(f"Notificação enviada para {nome_dest} por e-mail.", "success")

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
                    body= f"""
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
                        <td style="background: linear-gradient(135deg, #0f172a, #1e293b); border: 1px solid rgba(244,63,94,0.25); border-radius: 16px; padding: 35px;">
                            <table width="100%" cellpadding="0" cellspacing="0">

                   
                                <tr>
                                    <td align="center" style="padding-bottom: 25px; border-bottom: 1px solid rgba(255,255,255,0.07);">
                                        <div style="background: rgba(244,63,94,0.1); border: 1px solid rgba(244,63,94,0.3); border-radius: 50px; display:inline-block; padding: 10px 22px; margin-bottom: 15px;">
                                            <span style="color:#f43f5e; font-size:0.85rem; font-weight:600; letter-spacing:1px;">⚠️ AVISO FORMAL</span>
                                        </div>
                                        <h2 style="margin:0; color:#f8fafc; font-size:1.4rem;">Olá, {nome_dest}!</h2>
                                        <p style="margin:10px 0 0; color:#94a3b8; font-size:0.95rem; line-height:1.6;">
                                            Você recebeu um aviso formal da administração da plataforma.
                                        </p>
                                    </td>
                                </tr>

                                <tr>
                                    <td style="padding-top: 25px; padding-bottom: 20px;">
                                        <p style="margin:0 0 12px; color:#94a3b8; font-size:0.75rem; text-transform:uppercase; letter-spacing:1px; font-weight:600;">Referente ao Chamado</p>
                                        <table width="100%" cellpadding="0" cellspacing="0">
                                            <tr>
                                                <td style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">🔖 Chamado</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">#{chamado_id} — {CATEGORIAS[chamado['categoria']]}</strong>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 10px 0;">
                                                    <span style="color:#94a3b8; font-size:0.85rem;">📋 Palestra</span><br>
                                                    <strong style="color:#f8fafc; font-size:0.95rem;">{chamado['titulo']}</strong>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>

                                    <td style="padding-bottom: 20px;">
                                        <p style="margin:0 0 10px; color:#f43f5e; font-size:0.75rem; text-transform:uppercase; letter-spacing:1px; font-weight:600;">Aviso da Administração</p>
                                        <div style="background: rgba(244,63,94,0.06); border-left: 3px solid #f43f5e; border-radius: 8px; padding: 15px 18px;">
                                            <p style="margin:0; color:#f8fafc; font-size:0.95rem; line-height:1.7;">
                                                {msg_aviso}
                                            </p>
                                        </div>
                                    </td>
                                </tr>

                                <tr>
                                    <td style="padding-bottom: 25px;">
                                        <div style="background: rgba(245,158,11,0.06); border-left: 3px solid #f59e0b; border-radius: 8px; padding: 15px 18px;">
                                            <p style="margin:0 0 6px; color:#f59e0b; font-size:0.8rem; font-weight:600; text-transform:uppercase; letter-spacing:1px;">⚠️ Atenção</p>
                                            <p style="margin:0 0 6px; color:#94a3b8; font-size:0.85rem; line-height:1.6;">• Este aviso fica registrado em seu histórico na plataforma.</p>
                                            <p style="margin:0; color:#94a3b8; font-size:0.85rem; line-height:1.6;">• Reincidências poderão resultar em suspensão ou banimento.</p>
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
                )
                flash(f"Aviso formal emitido e enviado para {nome_dest}.", "success")


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
                        <td style="background: linear-gradient(135deg, #0f172a, #1e293b); border: 1px solid rgba(244,63,94,0.25); border-radius: 16px; padding: 35px;">
                            <table width="100%" cellpadding="0" cellspacing="0">

                                <tr>
                                    <td align="center" style="padding-bottom: 25px; border-bottom: 1px solid rgba(255,255,255,0.07);">
                                        <div style="background: rgba(244,63,94,0.1); border: 1px solid rgba(244,63,94,0.3); border-radius: 50px; display:inline-block; padding: 10px 22px; margin-bottom: 15px;">
                                            <span style="color:#f43f5e; font-size:0.85rem; font-weight:600; letter-spacing:1px;">
                                                {'🔒 CONTA SUSPENSA' if novo_status_usuario == 'suspenso' else '🚫 CONTA BANIDA'}
                                            </span>
                                        </div>
                                        <h2 style="margin:0; color:#f8fafc; font-size:1.4rem;">Olá, {nome_dest}!</h2>
                                        <p style="margin:10px 0 0; color:#94a3b8; font-size:0.95rem; line-height:1.6;">
                                            Sua conta foi <strong style="color:#f43f5e;">{'suspensa' if novo_status_usuario == 'suspenso' else 'banida permanentemente'}</strong> da plataforma.
                                        </p>
                                    </td>
                                </tr>

                                <tr>
                                    <td style="padding-top: 25px; padding-bottom: 20px;">
                                        <p style="margin:0 0 10px; color:#f43f5e; font-size:0.75rem; text-transform:uppercase; letter-spacing:1px; font-weight:600;">Motivo</p>
                                        <div style="background: rgba(244,63,94,0.06); border-left: 3px solid #f43f5e; border-radius: 8px; padding: 15px 18px;">
                                            <p style="margin:0; color:#f8fafc; font-size:0.95rem; line-height:1.7;">
                                                {motivo}
                                            </p>
                                        </div>
                                    </td>
                                </tr>

                                <tr>
                                    <td style="padding-bottom: 25px;">
                                        <div style="background: rgba(245,158,11,0.06); border-left: 3px solid #f59e0b; border-radius: 8px; padding: 15px 18px;">
                                            <p style="margin:0; color:#94a3b8; font-size:0.85rem; line-height:1.6;">
                                                {'⚠️ Entre em contato com a administração para mais informações sobre sua suspensão.' if novo_status_usuario == 'suspenso' else '🚫 Esta decisão é definitiva e não está sujeita a revisão.'}
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