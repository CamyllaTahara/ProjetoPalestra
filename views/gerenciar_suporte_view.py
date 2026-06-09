from flask import Blueprint, request, redirect, url_for, flash, session, render_template
import mysql.connector
from flask_mail import Message
from datetime import datetime, timedelta
from utils.mail import send_notification_email
from flask import current_app
from flask_mail import Mail

gerenciar_suporte = Blueprint('gerenciar_suporte', __name__)

@gerenciar_suporte.route('/suporte/novo', methods=['POST'])
def criar_chamado():
    mensagem_usuario = request.form.get('mensagem')
    
    usuario_id = session.get('user_id') or session.get('palestrante_id') or session.get('instituicao_id')
    usuario_nome = session.get('user_name') or "Usuário do Sistema"
    usuario_tipo = session.get('user_role', 'palestrante') 

    if not usuario_id:
        flash('Você precisa estar logado para enviar uma mensagem ao suporte.', 'danger')
        return redirect(request.referrer or url_for('index'))

    try:
        
        conexao = mysql.connector.connect(
            host="localhost",
            user="root",        
            password="",        
            database="palestra" 
        )
        
        cursor = conexao.cursor()
        
        comando_sql = """
            INSERT INTO chamados_suporte (usuario_id, usuario_nome, usuario_tipo, mensagem, status)
            VALUES (%s, %s, %s, %s, 'Pendente')
        """
        dados = (usuario_id, usuario_nome, usuario_tipo, mensagem_usuario)
        
        cursor.execute(comando_sql, dados)
        conexao.commit()
        
        cursor.close()
        conexao.close() 
        
        flash('Sua solicitação de suporte foi enviada ao administrador com sucesso! 🎉', 'success')
        
    except Exception as e:
        print(f"Erro ao salvar chamado no MySQL: {e}")
        flash('Ocorreu um erro ao conectar com o banco de dados do suporte.', 'danger')

    return redirect(request.referrer or url_for('index'))


@gerenciar_suporte.route('/administrador/suporte', methods=['GET'])
def listar_chamados_admin():

    if session.get('user_type') != 'administrador':
        print("SESSION COMPLETA:", dict(session))  
        flash('Acesso restrito apenas para administradores.', 'danger')
        return redirect(url_for('index'))
        
    try:
        conexao = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="palestra"
        )
        cursor = conexao.cursor()
        
        cursor.execute("""
            SELECT id, usuario_id, usuario_nome, usuario_tipo, mensagem, resposta, status, data_criacao 
            FROM chamados_suporte 
            ORDER BY FIELD(status, 'Pendente', 'Resolvido'), data_criacao DESC
        """)
        
        colunas = [col[0] for col in cursor.description]
        chamados = [dict(zip(colunas, row)) for row in cursor.fetchall()]
        
        cursor.close()
        conexao.close()
        
        return render_template('central_suporte.html', chamados=chamados)
    
    except Exception as e:
        print(f"Erro ao buscar chamados no MySQL: {e}")
        flash('Não foi possível carregar a lista de suporte técnico.', 'danger')
        return redirect(url_for('index'))
    
@gerenciar_suporte.route('/suporte/historico', methods=['GET'])
def historico_suporte():
    usuario_id = session.get('user_id') or session.get('palestrante_id') or session.get('instituicao_id')
    if not usuario_id:
        return {"chamados": []}, 401

    try:
        conexao = mysql.connector.connect(
            host="localhost", user="root", password="", database="palestra"
        )
        cursor = conexao.cursor()

        cursor.execute("""
            SELECT mensagem, resposta, status, DATE_FORMAT(data_criacao, '%d/%m %H:%i') 
            FROM chamados_suporte 
            WHERE usuario_id = %s 
            ORDER BY data_criacao DESC LIMIT 5
        """, (usuario_id,))
        
        chamados = [{"mensagem": r[0], "resposta": r[1], "status": r[2], "data": r[3]} for r in cursor.fetchall()]
        cursor.close()
        conexao.close()
        return {"chamados": chamados}, 200
    except Exception as e:
        print(e)
        return {"chamados": []}, 500
    


@gerenciar_suporte.route('/administrador/suporte/responder/<int:chamado_id>', methods=['POST'])
def responder_chamado(chamado_id):
    if session.get('user_type') != 'administrador':
        flash('Acesso restrito apenas para administradores.', 'danger')
        return redirect(url_for('index'))

    resposta_admin = request.form.get('resposta')

    try:
        conexao = mysql.connector.connect(
            host="localhost", user="root", password="", database="palestra"
        )
        cursor = conexao.cursor()

        # Tenta buscar palestrante
        cursor.execute("""
            SELECT c.mensagem, p.email, p.nome_completo
            FROM chamados_suporte c
            JOIN palestrantes p ON c.usuario_id = p.id
            WHERE c.id = %s
        """, (chamado_id,))
        resultado = cursor.fetchone()

        # Se não achou, tenta instituição
        if not resultado:
            cursor.execute("""
                SELECT c.mensagem, i.email, i.nome
                FROM chamados_suporte c
                JOIN instituicoes i ON c.usuario_id = i.id
                WHERE c.id = %s
            """, (chamado_id,))
            resultado = cursor.fetchone()

        if resultado:
            mensagem_original, email_usuario, usuario_nome = resultado

   
            cursor.execute("""
                UPDATE chamados_suporte 
                SET resposta = %s, status = 'Resolvido', data_resposta = NOW() 
                WHERE id = %s
            """, (resposta_admin, chamado_id))
            conexao.commit()

          
            html_body = f"""
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
                            <p style="margin:6px 0 0; color:#94a3b8; font-size:0.85rem;">Central de Suporte Técnico</p>
                        </td>
                    </tr>

            
                    <tr>
                        <td style="background: linear-gradient(135deg, #0f172a, #1e293b); border: 1px solid rgba(0,210,255,0.15); border-radius: 16px; padding: 35px;">
                            <table width="100%" cellpadding="0" cellspacing="0">

                           
                                <tr>
                                    <td align="center" style="padding-bottom: 25px; border-bottom: 1px solid rgba(255,255,255,0.07);">
                                        <div style="background: rgba(0,210,255,0.1); border: 1px solid rgba(0,210,255,0.3); border-radius: 50px; display:inline-block; padding: 10px 22px; margin-bottom: 15px;">
                                            <span style="color:#00d2ff; font-size:0.85rem; font-weight:600; letter-spacing:1px;">✔ SUPORTE RESPONDIDO</span>
                                        </div>
                                        <h2 style="margin:0; color:#f8fafc; font-size:1.4rem;">Olá, {usuario_nome}!</h2>
                                        <p style="margin:10px 0 0; color:#94a3b8; font-size:0.95rem; line-height:1.6;">
                                            Sua solicitação foi analisada e respondida.
                                        </p>
                                    </td>
                                </tr>

                                <tr>
                                    <td style="padding-top: 25px; padding-bottom: 15px;">
                                        <p style="margin:0 0 10px; color:#94a3b8; font-size:0.75rem; text-transform:uppercase; letter-spacing:1px; font-weight:600;">Sua mensagem</p>
                                        <div style="background: rgba(0,0,0,0.25); border-left: 3px solid #475569; border-radius: 8px; padding: 15px 18px;">
                                            <p style="margin:0; color:#cbd5e1; font-size:0.95rem; line-height:1.7; font-style:italic;">
                                                "{mensagem_original}"
                                            </p>
                                        </div>
                                    </td>
                                </tr>

                            
                                <tr>
                                    <td style="padding-bottom: 30px;">
                                        <p style="margin:0 0 10px; color:#00d2ff; font-size:0.75rem; text-transform:uppercase; letter-spacing:1px; font-weight:600;">Resposta do Suporte</p>
                                        <div style="background: rgba(0,210,255,0.06); border-left: 3px solid #00d2ff; border-radius: 8px; padding: 15px 18px;">
                                            <p style="margin:0; color:#f8fafc; font-size:0.95rem; line-height:1.7;">
                                                {resposta_admin}
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
                                Este e-mail foi enviado automaticamente pelo sistema PalestraApp.<br>
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
            send_notification_email(
                recipient=email_usuario,
                subject="✔ Sua solicitação de suporte foi respondida!",
                body=html_body,
                is_html=True
            )

            flash('Resposta enviada e e-mail de notificação despachado!', 'success')
        else:
            flash('Usuário do chamado não encontrado.', 'warning')

        cursor.close()
        conexao.close()

    except Exception as e:
        import traceback
        traceback.print_exc()
        flash('Erro ao salvar resposta ou enviar e-mail.', 'danger')

    return redirect(url_for('gerenciar_suporte.listar_chamados_admin'))