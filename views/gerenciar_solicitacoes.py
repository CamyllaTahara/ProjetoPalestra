import os
from flask import Blueprint, render_template, request, redirect, send_file, url_for, flash, session
from utils import mail
from utils.security import login_required
import mysql.connector
from datetime import datetime, timedelta
from utils.mail import send_notification_email
from flask import current_app

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
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Buscar dados do palestrante
        cursor.execute("""
            SELECT id, nome_completo, ramo_atividade, anos_experiencia, email, telefone, curriculo_pdf,descricao,foto
            FROM palestrantes
            WHERE id = %s
        """, (palestrante_id,))
        
        palestrante = cursor.fetchone()
        
        if not palestrante:
            flash("Palestrante não encontrado", "danger")
            return redirect(url_for('gerenciar_solicitacoes.listar_palestrantes'))
        
        # Buscar disponibilidades do palestrante
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
        cursor.close()
        conn.close()
        
        return render_template("perfil_palestrante.html", 
                             palestrante=palestrante, 
                             disponibilidades=disponibilidades)
    
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
        
        # 1. Obter o NOME DO ARQUIVO do banco de dados
        cursor.execute("""
            SELECT nome_completo, curriculo_pdf
            FROM palestrantes
            WHERE id = %s
        """, (palestrante_id,))
        
        palestrante = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        # 2. Verificar se o currículo existe no registro do palestrante
        if not palestrante or not palestrante['curriculo_pdf']:
            flash("Currículo não encontrado ou não cadastrado.", "danger")
            return redirect(url_for('gerenciar_solicitacoes.perfil_palestrante', palestrante_id=palestrante_id))

        # 3. Montar o caminho completo do arquivo no servidor
        # O Flask procura o caminho a partir da pasta raiz do projeto.
        # Ajuste 'static/curriculos/' se o caminho for diferente.
        curriculo_pdf_nome = palestrante['curriculo_pdf']
        caminho_arquivo = os.path.join(
    current_app.root_path,
    "uploads_curriculos",
    curriculo_pdf_nome
)
        print(f"DEBUG: Tentando encontrar o arquivo em: {os.path.abspath(caminho_arquivo)}")
        
        # 4. Configurar o nome do arquivo para o download
        nome_download = f"Curriculo_{palestrante['nome_completo'].replace(' ', '_').replace('.', '')}.pdf"
        
        # 5. Enviar o arquivo.
        # Usa os.path.abspath() para garantir que o caminho absoluto seja passado para send_file
        # Embora o Flask geralmente resolva paths relativos à raiz, este é um bom padrão.
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
        
        # Validações
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
            
            # Verificar duplicação
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
            
            # Criar a solicitação
            sql = """
                INSERT INTO solicitacoes_palestras 
                (instituicao_id, palestrante_id, titulo, descricao, data_proposta, horario_proposta, status, endereco_palestra, prazo_expiracao)
                VALUES (%s, %s, %s, %s, %s, %s, 'pendente', %s, %s)
            """
            cursor.execute(sql, (instituicao_id, palestrante_id, titulo, descricao, data_proposta, horario_proposta, endereco_palestra, prazo_expiracao))
            conn.commit()  # ✅ SALVAR PRIMEIRO!
            
            # ============================================================
            # 📧 NOTIFICAÇÕES POR E-MAIL (AMBAS AS PARTES)
            # ============================================================
            
            # Buscar dados do PALESTRANTE
            cursor.execute("""
                SELECT email, nome_completo 
                FROM palestrantes 
                WHERE id = %s
            """, (palestrante_id,))
            palestrante = cursor.fetchone()
            
            # Buscar dados da INSTITUIÇÃO
            cursor.execute("""
                SELECT nome, email 
                FROM instituicoes 
                WHERE id = %s
            """, (instituicao_id,))
            instituicao = cursor.fetchone()
            
            # Formatar datas
            data_formatada = data_obj.strftime('%d/%m/%Y')
            data_expiracao_formatada = prazo_expiracao.strftime('%d/%m/%Y às %H:%M')
            
            from utils.mail import send_notification_email
            
            # ─────────────────────────────────────────────────────────
            # 1️⃣ E-MAIL PARA O PALESTRANTE (Notificação de Solicitação)
            # ─────────────────────────────────────────────────────────
            subject_palestrante = f"📬 Nova Solicitação de Palestra: {titulo}"
            body_palestrante = f"""Olá, {palestrante['nome_completo']}!

Você recebeu uma nova solicitação de palestra através do sistema.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 DETALHES DA SOLICITAÇÃO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🏢 Instituição: {instituicao['nome']}
📋 Título: {titulo}
📅 Data: {data_formatada}
🕐 Horário: {horario_proposta}
📍 Local: {endereco_palestra}

📝 Descrição:
{descricao}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ PRAZO DE RESPOSTA: 
Esta solicitação expira em: {data_expiracao_formatada}

Por favor, acesse o sistema para aceitar ou recusar esta solicitação.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Atenciosamente,
Sistema de Agendamento de Palestras
"""
            
            email_palestrante_enviado = send_notification_email(
                recipient=palestrante['email'],
                subject=subject_palestrante,
                body=body_palestrante
            )
            
            # ─────────────────────────────────────────────────────────
            # 2️⃣ E-MAIL PARA A INSTITUIÇÃO (Confirmação de Envio)
            # ─────────────────────────────────────────────────────────
            subject_instituicao = f"✅ Solicitação Enviada: {titulo}"
            body_instituicao = f"""Prezada {instituicao['nome']},

Sua solicitação de palestra foi enviada com sucesso!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 RESUMO DA SOLICITAÇÃO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 Palestrante: {palestrante['nome_completo']}
📋 Título: {titulo}
📅 Data Proposta: {data_formatada}
🕐 Horário: {horario_proposta}
📍 Local: {endereco_palestra}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏳ PRÓXIMOS PASSOS:

• O palestrante foi notificado e tem até {data_expiracao_formatada} para responder
• Você receberá um e-mail assim que ele aceitar ou recusar
• Você pode acompanhar o status no painel "Minhas Solicitações"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 DICA: Se a solicitação expirar sem resposta, você pode solicitar novamente.

Atenciosamente,
Sistema de Agendamento de Palestras
"""
            
            email_instituicao_enviado = send_notification_email(
                recipient=instituicao['email'],
                subject=subject_instituicao,
                body=body_instituicao
            )
            
            # ============================================================
            # FIM DAS NOTIFICAÇÕES
            # ============================================================
            
            cursor.close()
            conn.close()
            
            # Feedback personalizado baseado no sucesso dos e-mails
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
    
    # =========================================================
    # TRATAMENTO GET (MOSTRAR FORMULÁRIO)
    # =========================================================
    
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

# ============= ROTAS PARA PALESTRANTE =============

@gerenciar_solicitacoes_bp.route("/solicitacoes_recebidas", methods=["GET"])
@login_required("palestrante")
def solicitacoes_recebidas():
    """Lista as solicitações recebidas pelo palestrante."""
    palestrante_id = session['user_id']
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # --- 1. LÓGICA DE EXPIRAÇÃO (ANTES DE LISTAR) ---
        # Marca como 'expirada' toda solicitação 'pendente' cujo prazo já passou.
        cursor.execute("""
            UPDATE solicitacoes_palestras
            SET status = 'expirada'
            WHERE palestrante_id = %s 
            AND status = 'pendente' 
            AND prazo_expiracao < NOW()
        """, (palestrante_id,))
        conn.commit() # Confirma a atualização no banco de dados
        
        # --- 2. CONSULTA (SELECT COM NOVAS COLUNAS) ---
        cursor.execute("""
            SELECT sp.id, i.nome, sp.titulo, sp.descricao, sp.data_proposta, sp.horario_proposta, 
                   sp.status, sp.criada_em, sp.endereco_palestra, 
                   sp.prazo_expiracao,                -- <<< 1. Seleciona o prazo de expiração
                   i.nome AS nome_instituicao          -- <<< 2. Alias renomeado para maior clareza
            FROM solicitacoes_palestras sp
            JOIN instituicoes i ON sp.instituicao_id = i.id
            WHERE sp.palestrante_id = %s
            ORDER BY sp.criada_em DESC
        """, (palestrante_id,))
        
        solicitacoes = cursor.fetchall()
        cursor.close()
        
        conn.close()
        
        # --- 3. RENDERIZAÇÃO ---
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
        
        # 1. BUSCAR DADOS DA SOLICITAÇÃO
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

        # Desempacota os dados
        data_proposta = solicitacao['data_proposta']
        horario_proposta = solicitacao['horario_proposta']
        titulo = solicitacao['titulo']
        nome_palestrante = solicitacao['nome_palestrante']
        nome_instituicao = solicitacao['nome_instituicao']
        email_instituicao = solicitacao['email_instituicao']
        
        body_recusa = ""
        
        # =========================================================
        # TRATAMENTO DE ACEITE
        # =========================================================
        if resposta == 'aceita':
            
            # 2. CHECAGEM DE CONFLITO DE AGENDA
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
                
            # 3. CRIAÇÃO DA PALESTRA CONFIRMADA
            cursor.execute("""
                INSERT INTO palestras_confirmadas 
                (solicitacao_id, palestrante_id, instituicao_id, titulo, descricao, 
                 data, horario, status, endereco_palestra)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'agendada', %s)
            """, (solicitacao_id, palestrante_id, solicitacao['instituicao_id'], 
                  titulo, solicitacao['descricao'], data_proposta, 
                  horario_proposta, solicitacao['endereco_palestra']))
            
            # ============================================================
            # 🆕 4. REMOVER DISPONIBILIDADE (NOVO!)
            # ============================================================
            print("\n" + "="*60)
            print("🗑️  REMOVENDO DISPONIBILIDADE ACEITA")
            print("="*60)
            print(f"Palestrante ID: {palestrante_id}")
            print(f"Data: {data_proposta}")
            print(f"Horário: {horario_proposta}")
            
            # Buscar a disponibilidade específica que corresponde ao horário aceito
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
                
                # Deletar a disponibilidade
                cursor.execute("""
                    DELETE FROM disponibilidade_palestrantes 
                    WHERE id = %s
                """, (disponibilidade['id'],))
                
                print(f"✅ Disponibilidade ID {disponibilidade['id']} removida!")
            else:
                print("⚠️  Nenhuma disponibilidade correspondente encontrada")
                print("   (Pode ser que a solicitação foi feita sem usar uma disponibilidade específica)")
            
            print("="*60 + "\n")
            # ============================================================
            # FIM DA REMOÇÃO DE DISPONIBILIDADE
            # ============================================================
        
        # =========================================================
        # TRATAMENTO DE RECUSA
        # =========================================================
        elif resposta == 'recusada':
            motivo=request.form.get('motivo_recusa','').strip()
            body_recusa = f"\nMotivo da Recusa: {motivo}" if motivo else "\nMotivo da Recusa: Não especificado pelo palestrante."
        
        # 5. ATUALIZAR STATUS DA SOLICITAÇÃO
        cursor.execute("""
            UPDATE solicitacoes_palestras
            SET status = %s, respondida_em = NOW(), motivo_recusa=%s
            WHERE id = %s
        """, (resposta, motivo if resposta == 'recusada' else None, solicitacao_id))
        
        conn.commit()  # ✅ COMMIT DE TUDO (palestra + remoção + atualização)
        
        # 6. PREPARAR E ENVIAR E-MAIL
        data_formatada = data_proposta.strftime('%d/%m/%Y')
        
        if resposta == 'aceita':
            subject = f"✅ Confirmação: Palestra '{titulo}' Aceita!"
            body = f"""Prezada {nome_instituicao},

O palestrante {nome_palestrante} aceitou a solicitação para a palestra:
Título: {titulo}
Data: {data_formatada}
Horário: {horario_proposta}

Detalhes logísticos podem ser acertados diretamente com o palestrante.

Atenciosamente,
Sua Plataforma"""
        else:
            subject = f"❌ Resposta: Palestra '{titulo}' Recusada"
            body = f"""Prezada {nome_instituicao},

Lamentamos informar que o palestrante {nome_palestrante} recusou a solicitação para a palestra:
Título: {titulo}
Data Proposta: {data_formatada}
Horário: {horario_proposta}
{body_recusa}

Agradecemos sua compreensão.

Atenciosamente,
Sua Plataforma"""
        
        # ENVIAR E-MAIL
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