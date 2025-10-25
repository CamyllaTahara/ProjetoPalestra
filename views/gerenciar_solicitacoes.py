import os
from flask import Blueprint, render_template, request, redirect, send_file, url_for, flash, session
from utils.security import login_required
import mysql.connector
from datetime import datetime, timedelta

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
            SELECT id, nome_completo, ramo_atividade, anos_experiencia, email, telefone, curriculo_pdf
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
        caminho_arquivo = curriculo_pdf_nome
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

@gerenciar_solicitacoes_bp.route("/solicitar_palestra/<int:palestrante_id>", methods=["GET", "POST"])
@login_required("instituicao")
def solicitar_palestra(palestrante_id):
    """Cria uma solicitação de palestra para um palestrante."""
    instituicao_id = session['user_id']
    
    # =========================================================
    # 1. TRATAMENTO POST (ENVIO DO FORMULÁRIO)
    # Este bloco permanece o mesmo por enquanto.
    # =========================================================
    
    if request.method == "POST":
        titulo = request.form.get('titulo')
        descricao = request.form.get('descricao')
        endereco_palestra = request.form.get('endereco_palestra')
        data_proposta = request.form.get('data_proposta')
        horario_proposta = request.form.get('horario_proposta')

        
        # Validações
        if not titulo or not descricao:
            flash("Título, e descrição são obrigatórios", "danger")
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
            
            # Verificar se já existe solicitação duplicada
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
                VALUES (%s, %s, %s, %s, %s, %s,'pendente', %s, %s )
            """
            cursor.execute(sql, (instituicao_id, palestrante_id, titulo, descricao, data_proposta, horario_proposta, endereco_palestra,prazo_expiracao))
            conn.commit()
            cursor.close()
            conn.close()
            
            flash("Solicitação enviada com sucesso!", "success")
            return redirect(url_for('gerenciar_solicitacoes.minhas_solicitacoes'))
        
        except Exception as e:
            flash(f"Erro ao criar solicitação: {e}", "danger")
            return redirect(url_for('gerenciar_solicitacoes.solicitar_palestra', palestrante_id=palestrante_id))
    
    # =========================================================
    # 2. TRATAMENTO GET (MOSTRAR FORMULÁRIO) - ATUALIZADO
    # =========================================================
    
    # 1. RECEBER OS PARÂMETROS DA URL (GET parameters)
    # Usamos request.args para ler os dados enviados pelo link do perfil.
    data_pre = request.args.get('data') 
    horario_inicio_pre = request.args.get('horario_inicio')
    horario_fim_pre = request.args.get('horario_fim') # Enviado do link, mas não usado no POST atual
    
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
        
        # 2. ENVIAR TODOS OS DADOS PARA O TEMPLATE
        # data_pre, horario_inicio_pre e horario_fim_pre serão usados para preencher os campos.
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
    
@gerenciar_solicitacoes_bp.route("/responder_solicitacao/<int:solicitacao_id>/<resposta>", methods=["POST"])
@login_required("palestrante")
def responder_solicitacao(solicitacao_id, resposta):
    """Responde uma solicitação de palestra (aceita ou recusa)."""
    palestrante_id = session['user_id']
    
    if resposta not in ['aceita', 'recusada']:
        flash("Resposta inválida", "danger")
        return redirect(url_for('gerenciar_solicitacoes.solicitacoes_recebidas'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Verificar se a solicitação pertence ao palestrante
        cursor.execute("""
            SELECT sp.id, sp.instituicao_id, sp.data_proposta, sp.horario_proposta
            FROM solicitacoes_palestras sp
            WHERE sp.id = %s AND sp.palestrante_id = %s
        """, (solicitacao_id, palestrante_id))
        
        solicitacao = cursor.fetchone()
        
        if not solicitacao:
            flash("Solicitação não encontrada", "danger")
            cursor.close()
            conn.close()
            return redirect(url_for('gerenciar_solicitacoes.solicitacoes_recebidas'))
        
        if resposta == 'aceita':
            # Verificar se já não tem outra palestra no mesmo horário
            cursor.execute("""
                SELECT id FROM palestras_confirmadas
                WHERE palestrante_id = %s 
                AND data = %s 
                AND horario = %s
                AND status != 'cancelada'
            """, (palestrante_id, solicitacao['data_proposta'], solicitacao['horario_proposta']))
            
            if cursor.fetchone():
                flash("Você já tem uma palestra confirmada nesse horário", "danger")
                cursor.close()
                conn.close()
                return redirect(url_for('gerenciar_solicitacoes.solicitacoes_recebidas'))
            
            # Criar palestra confirmada
            cursor.execute("""
                INSERT INTO palestras_confirmadas 
                (solicitacao_id, palestrante_id, instituicao_id, titulo, descricao, data, horario, status, endereco_palestra)
                SELECT id, palestrante_id, instituicao_id, titulo, descricao, data_proposta, horario_proposta,endereco_palestra, 'agendada'
                FROM solicitacoes_palestras
                WHERE id = %s
            """, (solicitacao_id,))
        
        # Atualizar status da solicitação
        cursor.execute("""
            UPDATE solicitacoes_palestras
            SET status = %s, respondida_em = NOW()
            WHERE id = %s
        """, (resposta, solicitacao_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        mensagem = "Palestra aceita!" if resposta == 'aceita' else "Palestra recusada!"
        flash(mensagem, "success")
        return redirect(url_for('gerenciar_solicitacoes.solicitacoes_recebidas'))
    
    except Exception as e:
        flash(f"Erro ao responder solicitação: {e}", "danger")
        return redirect(url_for('gerenciar_solicitacoes.solicitacoes_recebidas'))
