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

        # Atualiza automaticamente para realizada se a data passou (Sua lógica padrão)
        cursor.execute("""
        UPDATE palestras_confirmadas
        SET status = 'realizada' 
        WHERE data < CURDATE()
            AND status = 'agendada'
            AND palestrante_id = %s """,(palestrante_id,))
        
        conn.commit()

        # 1. PALESTRAS AGENDADAS (ATUALIZADA COM LEFT JOIN) 🌟
        cursor.execute("""
            SELECT pc.id, pc.titulo, pc.descricao, pc.data, pc.horario, pc.status, 
                   pc.criada_em, pc.endereco_palestra, i.nome, i.email, i.telefone,
                   IF(av.id IS NOT NULL, 1, 0) AS ja_avaliou
            FROM palestras_confirmadas pc
            JOIN instituicoes i ON pc.instituicao_id = i.id
            LEFT JOIN avaliacoes_palestras av 
                ON (av.solicitacao_id = pc.id OR av.solicitacao_id = pc.solicitacao_id)
                AND av.avaliador_tipo = 'palestrante' 
                AND av.avaliador_id = %s
            WHERE pc.palestrante_id = %s
            AND pc.status = 'agendada'
            AND pc.data >= CURDATE()
            ORDER BY pc.data, pc.horario           
        """, (palestrante_id, palestrante_id))
        
        palestras_agendadas = cursor.fetchall()
        
        for palestra in palestras_agendadas:
            if palestra.get('horario') and not isinstance(palestra['horario'], str):
                h, m = divmod(int(palestra['horario'].total_seconds()), 3600)
                m = m // 60
                palestra['horario'] = f"{h:02d}:{m:02d}"

        # 2. HISTÓRICO DE PALESTRAS (ATUALIZADA COM LEFT JOIN) 🌟
        cursor.execute("""
            SELECT pc.id, pc.titulo, pc.descricao, pc.data, pc.horario, pc.status, 
                   pc.criada_em, pc.endereco_palestra, i.nome, i.email, i.telefone,
                   IF(av.id IS NOT NULL, 1, 0) AS ja_avaliou
            FROM palestras_confirmadas pc
            JOIN instituicoes i ON pc.instituicao_id = i.id
            LEFT JOIN avaliacoes_palestras av 
                ON (av.solicitacao_id = pc.id OR av.solicitacao_id = pc.solicitacao_id)
                AND av.avaliador_tipo = 'palestrante' 
                AND av.avaliador_id = %s
            WHERE pc.palestrante_id = %s
            AND (pc.status IN ('realizada', 'cancelada', 'avaliada') OR (pc.status = 'agendada' AND pc.data < CURDATE()))
            ORDER BY pc.data DESC, pc.horario DESC
        """, (palestrante_id, palestrante_id))
        
        historico = cursor.fetchall()
        
        for palestra in historico:
            if palestra.get('horario') and not isinstance(palestra['horario'], str):
                h, m = divmod(int(palestra['horario'].total_seconds()), 3600)
                m = m // 60
                palestra['horario'] = f"{h:02d}:{m:02d}"

        cursor.close()
        conn.close()

        return render_template("minhas_palestras_palestrante.html",
                                palestras_agendadas=palestras_agendadas,
                                historico=historico, today=date.today())
    
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
    
from datetime import date

@gerenciar_palestras_bp.route("/palestras_instituicao", methods=["GET"])
@login_required("instituicao")
def palestras_instituicao():
    instituicao_id = session['user_id']

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Palestras Agendadas (Continua igual)
        cursor.execute("""
            SELECT pc.id, pc.titulo, pc.descricao, pc.data, pc.horario, pc.status, 
                   pc.criada_em, p.nome_completo, p.email, p.telefone
            FROM palestras_confirmadas pc
            JOIN palestrantes p ON pc.palestrante_id = p.id
            WHERE pc.instituicao_id = %s
            AND pc.status = 'agendada'
            AND pc.data >= CURDATE()
            ORDER BY pc.data, pc.horario            
        """, (instituicao_id,))
        
        palestras_agendadas = cursor.fetchall()
        
        for palestra in palestras_agendadas:
            if palestra.get('horario') and not isinstance(palestra['horario'], str):
                h, m = divmod(int(palestra['horario'].total_seconds()), 3600)
                m = m // 60
                palestra['horario'] = f"{h:02d}:{m:02d}"

        # 2. Histórico de Palestras (ATUALIZADA COM LEFT JOIN) 🌟
        # Trazemos uma coluna nova chamada 'ja_avaliou' (1 se achou avaliação da instituição, 0 se não)
        cursor.execute("""
            SELECT pc.id, pc.titulo, pc.descricao, pc.data, pc.horario, pc.status, 
                   pc.criada_em, p.nome_completo,
                   IF(av.id IS NOT NULL, 1, 0) AS ja_avaliou
            FROM palestras_confirmadas pc
            JOIN palestrantes p ON pc.palestrante_id = p.id
            LEFT JOIN avaliacoes_palestras av 
                ON (av.solicitacao_id = pc.id OR av.solicitacao_id = pc.solicitacao_id)
                AND av.avaliador_tipo = 'instituicao' 
                AND av.avaliador_id = %s
            WHERE pc.instituicao_id = %s
            AND (pc.status IN ('realizada','cancelada', 'avaliada') OR (pc.status='agendada' AND pc.data < CURDATE()))
            ORDER BY pc.data DESC, pc.horario DESC
        """, (instituicao_id, instituicao_id)) # Passamos o ID duas vezes (uma para o JOIN e outra para o WHERE)
        
        historico = cursor.fetchall()
        
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
    





@gerenciar_palestras_bp.route('/instituicao/avaliar/<int:solicitacao_id>', methods=['POST'])
def instituicao_avaliar(solicitacao_id):
    # Pegando os valores do formulário
    nota_conduta = request.form.get('nota_conduta')
    nota_conteudo = request.form.get('nota_conteudo')
    nota_combinado = request.form.get('nota_combinado')
    comentario = request.form.get('comentario')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)

    try:
       
        cursor.execute("""
            SELECT id FROM avaliacoes
            WHERE solicitacao_id = %s AND avaliador_tipo = 'instituicao'
        """, (solicitacao_id,))
        
        if cursor.fetchone():
            flash('Você já avaliou este palestrante.', 'warning')
            return redirect(url_for('gerenciar_palestras.palestras_instituicao'))


        cursor.execute("""
            INSERT INTO avaliacoes
            (solicitacao_id, avaliador_tipo, nota_conduta, nota_conteudo, nota_combinado, comentario)
            VALUES (%s, 'instituicao', %s, %s, %s, %s)
        """, (solicitacao_id, nota_conduta, nota_conteudo, nota_combinado, comentario))

    
        cursor.execute("""
            UPDATE palestras_confirmadas
            SET status = 'avaliada'
            WHERE id = %s
        """, (solicitacao_id,))

     
        linhas_afetadas = cursor.rowcount
        print(f"DEBUG: Tentando atualizar palestra ID {solicitacao_id}. Linhas afetadas: {linhas_afetadas}")

        if linhas_afetadas == 0:
           
            print("AVISO: Nenhuma linha foi atualizada! Verifique se o ID enviado está correto.")
            conn.rollback() 
            flash('Erro ao atualizar o status da palestra. ID não encontrado.', 'danger')
        else:
            conn.commit()
            flash('Palestrante avaliado com sucesso!', 'success')

    except Exception as e:
        conn.rollback()
        print(f"ERRO NO BANCO DE DADOS: {e}")
        flash(f'Erro interno ao processar avaliação: {e}', 'danger')
        
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('gerenciar_palestras.palestras_instituicao'))

@gerenciar_palestras_bp.route('/solicitacao/<int:solicitacao_id>/avaliar', methods=['GET', 'POST'])
def avaliar_solicitacao(solicitacao_id):
    user_id = session.get('user_id')
    user_type = session.get('user_type')

    if not user_id or user_type not in ('palestrante', 'instituicao'):
        return redirect(url_for('login_palestrante.login_palestrante'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)

    # 🛠️ AQUI ESTÁ A MUDANÇA: 
    # Vamos buscar tanto por 'id' quanto por 'solicitacao_id' para garantir compatibilidade,
    # independente de qual ID veio do seu HTML.
    cursor.execute("""
        SELECT id, titulo, palestrante_id, instituicao_id 
        FROM palestras_confirmadas 
        WHERE (id = %s OR solicitacao_id = %s) 
          AND (palestrante_id = %s OR instituicao_id = %s)
    """, (solicitacao_id, solicitacao_id, user_id, user_id))
    
    solicitacao = cursor.fetchone()

    # Se mesmo assim não achar, ele entra aqui (que é o modal que você viu)
    if not solicitacao:
        cursor.close()
        conn.close()
        flash("Palestra não encontrada ou você não tem permissão para avaliá-la.", "danger")
        return redirect(url_for('gerenciar_palestras.minhas_palestras'))

    # ✅ CORREÇÃO 3: Verifica se ESTE usuário específico já avaliou ESTA palestra específica
    cursor.execute("""
        SELECT id FROM avaliacoes_palestras 
        WHERE solicitacao_id = %s AND avaliador_tipo = %s AND avaliador_id = %s
    """, (solicitacao_id, user_type, user_id))
    ja_avaliou = cursor.fetchone()

    if request.method == 'POST':
        if ja_avaliou:
            flash("Você já enviou uma avaliação para esta palestra!", "warning")
            return redirect(url_for('gerenciar_palestras.minhas_palestras'))

        nota_conduta = request.form.get('nota_conduta')
        nota_pontualidade = request.form.get('nota_pontualidade')
        nota_respeito = request.form.get('nota_respeito')
        comentario = request.form.get('comentario', '').strip()

        if not nota_conduta or not nota_pontualidade or not nota_respeito:
            flash("Por favor, avalie todos os itens.", "danger")
        else:
            # ✅ CORREÇÃO 4: Quantidade correta de colunas e placeholders (%s) no INSERT
            cursor.execute("""
                INSERT INTO avaliacoes_palestras
                (solicitacao_id, avaliador_tipo, avaliador_id, nota_conduta, nota_pontualidade, nota_respeito, comentario)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (solicitacao_id, user_type, user_id, nota_conduta, nota_pontualidade, nota_respeito, comentario or None))
            
            conn.commit()
            flash("Avaliação enviada! Obrigado pelo feedback. 😊", "success")
            
            cursor.close()
            conn.close()

            # ✅ CORREÇÃO 5: Rota correta pós-avaliação (minhas_palestras)
            if user_type == 'palestrante':
                return redirect(url_for('gerenciar_palestras.minhas_palestras'))
            else:
                return redirect(url_for('gerenciar_palestras.palestras_instituicao'))

    cursor.close()
    conn.close()
    return render_template('avaliar_palestra.html', solicitacao=solicitacao, ja_avaliou=ja_avaliou)

@gerenciar_palestras_bp.route('/palestrante/minhas-avaliacoes')
def minhas_avaliacoes_palestrante():
    user_id = session.get('user_id')
    user_type = session.get('user_type')

    if not user_id or user_type != 'palestrante':
        return redirect(url_for('login_palestrante.login_palestrante'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT av.nota_conduta, av.nota_pontualidade, av.nota_respeito, av.comentario, av.criado_em,
               pc.titulo AS palestra_titulo,
               i.nome AS instituicao_nome
        FROM palestra.avaliacoes_palestras av
        JOIN palestras_confirmadas pc ON av.solicitacao_id = pc.id
        JOIN instituicoes i ON av.avaliador_id = i.id
        WHERE pc.palestrante_id = %s          -- A palestra pertence a este palestrante
          AND av.avaliador_tipo = 'instituição' -- Quem avaliou foi uma instituição
        ORDER BY av.criado_em DESC
    """, (user_id,))
    avaliacoes = cursor.fetchall()

    cursor.execute("""
        SELECT
            ROUND(AVG(av.nota_conduta), 1) AS media_conduta,
            ROUND(AVG(av.nota_pontualidade), 1) AS media_pontualidade,
            ROUND(AVG(av.nota_respeito), 1) AS media_respeito,
            COUNT(*) AS total
        FROM palestra.avaliacoes_palestras av
        JOIN palestras_confirmadas pc ON av.solicitacao_id = pc.id
        WHERE pc.palestrante_id = %s 
          AND av.avaliador_tipo = 'instituição'
    """, (user_id,))
    medias = cursor.fetchone()

    cursor.close()
    conn.close()
    
    return render_template('minhas_avaliacoes_palestrantes.html', avaliacoes=avaliacoes, medias=medias)

@gerenciar_palestras_bp.route('/instituicao/minhas-avaliacoes')
def minhas_avaliacoes_instituicao():
    user_id = session.get('user_id')
    user_type = session.get('user_type')

    if not user_id or user_type != 'instituicao':
        return redirect(url_for('login_instituicao.login')) 

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

   
    cursor.execute("""
        SELECT av.nota_conduta, av.nota_pontualidade, av.nota_respeito, av.comentario, av.criado_em,
               pc.titulo AS palestra_titulo,
               p.nome_completo AS palestrante_nome
        FROM palestra.avaliacoes_palestras av
        JOIN palestras_confirmadas pc ON av.solicitacao_id = pc.id
        JOIN palestrantes p ON av.avaliador_id = p.id
        WHERE pc.instituicao_id = %s          -- A palestra/evento foi da instituição logada
          AND av.avaliador_tipo = 'palestrante' -- Quem avaliou foi um palestrante
        ORDER BY av.criado_em DESC
    """, (user_id,))
    avaliacoes = cursor.fetchall()

  
    cursor.execute("""
        SELECT
            ROUND(AVG(av.nota_conduta), 1) AS media_conduta,
            ROUND(AVG(av.nota_pontualidade), 1) AS media_pontualidade,
            ROUND(AVG(av.nota_respeito), 1) AS media_respeito,
            COUNT(*) AS total
        FROM palestra.avaliacoes_palestras av
        JOIN palestras_confirmadas pc ON av.solicitacao_id = pc.id
        WHERE pc.instituicao_id = %s 
          AND av.avaliador_tipo = 'palestrante'
    """, (user_id,))
    medias = cursor.fetchone()

    cursor.close()
    conn.close()
    
    return render_template('minhas_avaliacoes_instituicao.html', avaliacoes=avaliacoes, medias=medias)

@gerenciar_palestras_bp.route('/solicitacao/<int:solicitacao_id>/concluir', methods=['POST'])
def concluir_palestra(solicitacao_id):
    user_id = session.get('user_id')
    user_type = session.get('user_type')

    # Segurança: Apenas o palestrante dono da palestra pode concluí-la
    if not user_id or user_type != 'palestrante':
        flash("Acesso negado.", "danger")
        return redirect(url_for('login_palestrante.login_palestrante'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Primeiro, vamos buscar o id real da solicitação se o parâmetro 'solicitacao_id' for o ID da tabela 'palestras_confirmadas'
    # Se o parâmetro da rota JÁ FOR o id da palestra_confirmada, precisamos do solicitacao_id para a rota de avaliação.
    cursor.execute("""
        SELECT solicitacao_id FROM palestras_confirmadas 
        WHERE id = %s AND palestrante_id = %s
    """, (solicitacao_id, user_id))
    resultado = cursor.fetchone()

    if not resultado:
        cursor.close()
        conn.close()
        flash("Palestra não encontrada ou você não tem permissão para alterá-la.", "danger")
        return redirect(url_for('gerenciar_palestras.minhas_palestras'))

    id_da_solicitacao_real = resultado[0] # Aqui temos o ID correto que a página de avaliação espera!

    # 2. Agora atualizamos o status para realizada usando o ID da confirmação
    cursor.execute("""
        UPDATE palestras_confirmadas 
        SET status = 'realizada' 
        WHERE id = %s AND palestrante_id = %s
    """, (solicitacao_id, user_id))
    
    conn.commit()
    cursor.close()
    conn.close()

    flash("Parabéns pela conclusão da palestra! 🎓 Que tal deixar uma avaliação sobre a instituição?", "success")
    
    # 3. REDIRECIONAMENTO CORRETO: Passando o ID da solicitação que o HTML de avaliação precisa para buscar o título, etc.
    return redirect(url_for('gerenciar_palestras.avaliar_solicitacao', solicitacao_id=id_da_solicitacao_real))