import os
import re
import sqlite3
import json
import hashlib
import urllib.request
import urllib.error
from datetime import datetime
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, send_from_directory, abort
)
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
load_dotenv()

# ─── Configuração ────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
DB_PATH    = os.path.join(BASE_DIR, 'database.db')
ALLOWED    = {'pdf'}

app = Flask(__name__)
app.secret_key = 'sala_limpa_secret_2024'
app.config['UPLOAD_FOLDER'] = UPLOAD_DIR
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

os.makedirs(UPLOAD_DIR, exist_ok=True)

# ─── Banco de dados ───────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            password      TEXT NOT NULL,
            role          TEXT NOT NULL DEFAULT 'user',
            nome          TEXT,
            turma         TEXT,
            avatar        TEXT DEFAULT '🎓'
        );
        CREATE TABLE IF NOT EXISTS arquivos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            filename      TEXT NOT NULL,
            original_name TEXT NOT NULL,
            descricao     TEXT,
            uploaded_at   TEXT NOT NULL,
            uploader_id   INTEGER
        );
        CREATE TABLE IF NOT EXISTS mensagens (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            role          TEXT NOT NULL,
            content       TEXT NOT NULL,
            created_at    TEXT NOT NULL
        );
    ''')

    pwd_adm  = hashlib.sha256('adm123'.encode()).hexdigest()
    pwd_user = hashlib.sha256('user123'.encode()).hexdigest()

    c.execute(
        "INSERT OR IGNORE INTO users (username, password, role, nome, avatar) "
        "VALUES (?, ?, 'adm', 'Administrador', '👑')",
        ('adm', pwd_adm)
    )
    c.execute(
        "INSERT OR IGNORE INTO users (username, password, role, nome, turma, avatar) "
        "VALUES (?, ?, 'user', 'Estudante Demo', 'Turma A', '🎓')",
        ('aluno', pwd_user)
    )
    conn.commit()
    conn.close()

# ─── Helpers gerais ───────────────────────────────────────────────────────────
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED

def hash_pwd(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Faça login para continuar.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def adm_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Faça login para continuar.', 'warning')
            return redirect(url_for('login'))
        if session.get('role') != 'adm':
            flash('Acesso restrito ao administrador.', 'danger')
            return redirect(url_for('chat'))
        return f(*args, **kwargs)
    return decorated

def get_user(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return user

def get_arquivos():
    conn = get_db()
    arqs = conn.execute(
        "SELECT * FROM arquivos ORDER BY uploaded_at DESC"
    ).fetchall()
    conn.close()
    return arqs

def get_historico(user_id, limit=40):
    """
    Retorna as últimas mensagens em ordem cronológica (antiga → nova).
    Subconsulta pega as últimas N por id DESC, depois reordena ASC,
    garantindo que a mensagem do usuário sempre precede a resposta da IA.
    """
    conn = get_db()
    msgs = conn.execute(
        """SELECT * FROM (
                SELECT * FROM mensagens
                WHERE user_id=?
                ORDER BY id DESC
                LIMIT ?
           ) ORDER BY id ASC""",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return msgs

def salvar_msg(user_id, role, content):
    conn = get_db()
    # Usa microsegundos no timestamp para garantir ordenação correta
    # (usuário sempre salvo antes da IA, e o ID autoincrement preserva a sequência)
    conn.execute(
        "INSERT INTO mensagens (user_id, role, content, created_at) VALUES (?,?,?,?)",
        (user_id, role, content, datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'))
    )
    conn.commit()
    conn.close()

# ─── Conversão de texto para HTML (sem asteriscos) ────────────────────────────
def texto_para_html(texto):
    """
    Converte marcações de texto simples para HTML semântico.
    Remove asteriscos e usa <strong>, <em> e estrutura HTML limpa.
    Nunca deixa asteriscos aparecerem para o usuário.
    """
    import html as html_mod

    linhas = texto.split('\n')
    saida  = []
    lista_aberta = False

    for linha in linhas:
        # Escapar HTML perigoso primeiro, preservando tags que já virarem HTML
        # (links do sistema são gerados por nós, não pelo usuário)
        # Não escapamos aqui pois o conteúdo vem do nosso sistema/IA controlada.

        # Detectar itens de lista: •, -, 1. 2. etc.
        item_lista = re.match(r'^(\s*)(•|-|\d+\.)\s+(.+)$', linha)

        if item_lista:
            if not lista_aberta:
                saida.append('<ul class="msg-list">')
                lista_aberta = True
            conteudo = item_lista.group(3)
            conteudo = formatar_inline(conteudo)
            saida.append(f'  <li>{conteudo}</li>')
        else:
            if lista_aberta:
                saida.append('</ul>')
                lista_aberta = False

            linha_strip = linha.strip()
            if not linha_strip:
                saida.append('<br>')
                continue

            linha_fmt = formatar_inline(linha_strip)
            saida.append(f'<p class="msg-p">{linha_fmt}</p>')

    if lista_aberta:
        saida.append('</ul>')

    return '\n'.join(saida)


def formatar_inline(texto):
    """
    Converte marcações inline em tags HTML.
    **texto** → <strong>texto</strong>
    *texto*   → <em>texto</em>
    [label](url) → <a href="url">label</a>
    Remove quaisquer asteriscos restantes.
    """
    # Negrito: **texto**
    texto = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', texto)
    # Itálico: *texto* (apenas se não sobrou asterisco duplo)
    texto = re.sub(r'\*([^*]+?)\*', r'<em>\1</em>', texto)
    # Links markdown: [label](url)
    texto = re.sub(
        r'\[([^\]]+)\]\((https?://[^\)]+)\)',
        r'<a href="\2" class="msg-link" target="_blank">\1</a>',
        texto
    )
    # Links internos sem http (rotas Flask já geradas):
    texto = re.sub(
        r'\[([^\]]+)\]\((/[^\)]*)\)',
        r'<a href="\2" class="msg-link">\1</a>',
        texto
    )
    # Remover asteriscos restantes (segurança extra)
    texto = texto.replace('*', '')
    return texto


# ─── IA via GroqCloud API ──────────────────────────────────────────────────────
SYSTEM_PROMPT = """Você é o Assistente da Ordina, um ajudante amigável e didático para estudantes do ensino fundamental e médio.

Sua missão é ajudar exclusivamente com:
- Dicas práticas de limpeza da sala de aula
- Organização do espaço (carteiras, armários, quadro, etc.)
- Sugestões de comportamentos para manter o ambiente harmônico
- Informações sobre a Escala de Limpeza quando solicitado
- Incentivar o respeito ao espaço coletivo

NÃO responda perguntas sobre outros assuntos (matemática, história, etc.).
Se perguntarem algo fora do tema, diga gentilmente que você só pode ajudar com limpeza e organização da sala.

FORMATAÇÃO OBRIGATÓRIA:
- Nunca use asteriscos (*) nas respostas
- Para destacar palavras importantes, escreva normalmente — o sistema cuidará da formatação
- Use listas com hífen (- item) quando listar dicas
- Seja direto, claro e encorajador
- Use emojis com moderação

Tom: amigável, simples, como um colega mais experiente falando com estudantes.
Responda sempre em português brasileiro."""

ESCALA_TRIGGER = [
    'escala', 'escala de limpeza', 'escala limpeza', 'cronograma limpeza',
    'quem limpa', 'vez de limpar', 'responsável limpeza', 'pdf', 'arquivo',
    'documento', 'baixar'
]

def detectar_escala(texto):
    t = texto.lower()
    return any(k in t for k in ESCALA_TRIGGER)

def chamar_ia(historico_msgs, nova_msg):
    """
    Chama a API do GroqCloud (formato OpenAI-compatível).
    Cole sua chave entre as aspas vazias abaixo.
    """
    api_key = os.environ.get('GROQ_API_KEY', '')

    if not api_key or api_key == 'COLE_SUA_CHAVE_AQUI':
        print("[AVISO] Chave da API não configurada — usando respostas offline.")
        return resposta_offline(nova_msg)

    # Monta o histórico no formato OpenAI (role + content)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in historico_msgs[-10:]:
        messages.append({"role": m['role'], "content": m['content']})
    messages.append({"role": "user", "content": nova_msg})

    payload = json.dumps({
        "model": "llama-3.3-70b-versatile",
        "max_tokens": 1024,
        "messages": messages
    }).encode('utf-8')

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            resposta = data['choices'][0]['message']['content']
            print("[IA] Resposta recebida do GroqCloud com sucesso.")
            return resposta
    except urllib.error.HTTPError as e:
        erro = e.read().decode('utf-8')
        print(f"[ERRO] GroqCloud retornou HTTP {e.code}: {erro}")
        return resposta_offline(nova_msg)
    except Exception as e:
        print(f"[ERRO] Falha ao chamar GroqCloud: {e}")
        return resposta_offline(nova_msg)

def resposta_offline(msg):
    """
    Respostas pré-definidas para quando a API key não está configurada.
    Sem asteriscos — usa marcação que será convertida para HTML.
    """
    msg_l = msg.lower()

    if any(k in msg_l for k in ['escala', 'pdf', 'arquivo', 'documento', 'cronograma', 'baixar']):
        return (
            "📋 Vou buscar a Escala de Limpeza para você!\n"
            "Verifique os arquivos disponíveis clicando em Arquivos da Sala no menu.\n"
            "O ADM anexa a escala atualizada por lá."
        )

    if any(k in msg_l for k in ['lixo', 'jogar', 'descart']):
        return (
            "🗑️ Dica de descarte correto:\n\n"
            "- Sempre use a lixeira — nunca jogue no chão!\n"
            "- Papéis vão no lixo comum 📄\n"
            "- Garrafas plásticas, na coleta seletiva ♻️\n"
            "- Se não houver lixeira perto, guarde até encontrar uma.\n\n"
            "Pequenas atitudes fazem grande diferença! 💪"
        )

    if any(k in msg_l for k in ['carteira', 'mesa', 'organiz', 'arrum']):
        return (
            "🪑 Organização das carteiras:\n\n"
            "- Ao final da aula, empurre a cadeira para dentro da mesa\n"
            "- Recolha qualquer papel ou material esquecido\n"
            "- Deixe a fileira alinhada — facilita a próxima turma!\n"
            "- Combine com a turma um padrão de organização fixo\n\n"
            "Uma sala organizada melhora a concentração de todos! 📚"
        )

    if any(k in msg_l for k in ['quadro', 'lousa', 'apag']):
        return (
            "📋 Cuidados com o quadro e a lousa:\n\n"
            "- Apague completamente ao final da aula\n"
            "- Use apenas marcadores próprios para quadro branco\n"
            "- Avise o professor se o apagador estiver muito sujo\n"
            "- Não escreva com caneta comum na lousa branca!\n\n"
            "O responsável pelo quadro pode ser incluído na escala de limpeza! 🖊️"
        )

    if any(k in msg_l for k in ['comportamento', 'respeito', 'barulho', 'silencio', 'colega', 'harmonico', 'harmônico']):
        return (
            "🤝 Comportamentos para um ambiente harmônico:\n\n"
            "- Fale em tom moderado — respeite quem está concentrado\n"
            "- Peça licença ao passar entre as carteiras\n"
            "- Não mova carteiras sem necessidade\n"
            "- Combine regras com a turma no início do semestre\n"
            "- Valorize o esforço de quem limpou a sala!\n\n"
            "Harmonia começa com pequenos gestos diários 🌱"
        )

    if any(k in msg_l for k in ['oi', 'olá', 'ola', 'hello', 'bom dia', 'boa tarde', 'boa noite', 'tudo bem']):
        return (
            "👋 Olá! Sou o Assistente da Ordina.\n\n"
            "Posso te ajudar com:\n"
            "- 🧹 Dicas de limpeza\n"
            "- 📦 Organização da sala\n"
            "- 🤝 Comportamentos harmônicos\n"
            "- 📋 Escala de limpeza\n\n"
            "Como posso te ajudar hoje?"
        )

    if any(k in msg_l for k in ['limpeza', 'limpar', 'limpo', 'sujo', 'sujeira', 'varr', 'pó', 'poeira']):
        return (
            "🧹 Dicas de limpeza da sala:\n\n"
            "- Varrer o chão ao final de cada aula (especialmente sextas!)\n"
            "- Limpar as carteiras com pano úmido uma vez por semana\n"
            "- Manter o lixo sempre tampado para evitar cheiros\n"
            "- Designar um responsável diferente a cada semana — assim todos participam!\n\n"
            "Com uma boa escala de limpeza, ninguém fica sobrecarregado 😊"
        )

    return (
        "🧹 Estou aqui para ajudar com limpeza e organização da sala de aula!\n\n"
        "Você pode me perguntar sobre:\n"
        "- Como limpar e organizar a sala\n"
        "- Comportamentos para manter o ambiente agradável\n"
        "- A escala de limpeza da turma\n\n"
        "Tente ser mais específico e terei ótimas dicas para você 😊"
    )

# ─── Rotas ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('chat'))
    return redirect(url_for('login'))

# — Login / Logout —
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('chat'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, hash_pwd(password))
        ).fetchone()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session['role']    = user['role']
            session['nome']    = user['nome'] or user['username']
            session['avatar']  = user['avatar'] or '🎓'
            flash(f"Bem-vindo(a), {session['nome']}! 👋", 'success')
            return redirect(url_for('chat'))
        else:
            flash('Usuário ou senha incorretos.', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Você saiu com sucesso.', 'info')
    return redirect(url_for('login'))

# — Chat —
@app.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():
    user_id   = session['user_id']
    arquivos  = get_arquivos()

    if request.method == 'POST':
        msg_user = request.form.get('mensagem', '').strip()
        if not msg_user:
            return redirect(url_for('chat'))

        # Salva mensagem do usuário
        salvar_msg(user_id, 'user', msg_user)

        # Gera resposta da IA
        if detectar_escala(msg_user) and arquivos:
            arq = arquivos[0]  # mais recente
            url_dl = url_for('download_arquivo', arquivo_id=arq['id'])
            resposta_raw = (
                f"📋 Encontrei a escala para você!\n\n"
                f"Arquivo: {arq['original_name']}\n"
                f"{arq['descricao'] or 'Escala de limpeza da turma'}\n\n"
                f"[⬇️ Clique aqui para baixar]({url_dl})\n\n"
                f"Atualizado em: {arq['uploaded_at'][:10]}"
            )
        else:
            historico_atual = get_historico(user_id, limit=10)
            resposta_raw = chamar_ia(historico_atual, msg_user)

        # Converte para HTML limpo (sem asteriscos)
        resposta_html = texto_para_html(resposta_raw)
        salvar_msg(user_id, 'assistant', resposta_html)
        return redirect(url_for('chat'))

    historico = get_historico(user_id)
    user      = get_user(user_id)
    return render_template('chat.html',
        historico=historico,
        arquivos=arquivos,
        user=user
    )

@app.route('/limpar_chat', methods=['POST'])
@login_required
def limpar_chat():
    conn = get_db()
    conn.execute("DELETE FROM mensagens WHERE user_id=?", (session['user_id'],))
    conn.commit()
    conn.close()
    flash('Conversa apagada com sucesso.', 'info')
    return redirect(url_for('chat'))

# — Arquivos —
@app.route('/arquivos')
@login_required
def listar_arquivos():
    arquivos = get_arquivos()
    return render_template('arquivos.html', arquivos=arquivos)

@app.route('/arquivos/upload', methods=['GET', 'POST'])
@adm_required
def upload_arquivo():
    if request.method == 'POST':
        descricao = request.form.get('descricao', '').strip()
        file = request.files.get('arquivo')

        if not file or not file.filename:
            flash('Selecione um arquivo PDF.', 'warning')
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash('Apenas arquivos PDF são permitidos.', 'danger')
            return redirect(request.url)

        original_name = secure_filename(file.filename)
        timestamp     = datetime.now().strftime('%Y%m%d_%H%M%S_')
        filename      = timestamp + original_name
        file.save(os.path.join(UPLOAD_DIR, filename))

        conn = get_db()
        conn.execute(
            "INSERT INTO arquivos (filename, original_name, descricao, uploaded_at, uploader_id) "
            "VALUES (?,?,?,?,?)",
            (filename, original_name, descricao,
             datetime.now().strftime('%Y-%m-%d %H:%M:%S'), session['user_id'])
        )
        conn.commit()
        conn.close()

        flash(f'Arquivo "{original_name}" enviado com sucesso! 📄', 'success')
        return redirect(url_for('listar_arquivos'))

    return render_template('upload.html')

@app.route('/arquivos/download/<int:arquivo_id>')
@login_required
def download_arquivo(arquivo_id):
    conn = get_db()
    arq = conn.execute("SELECT * FROM arquivos WHERE id=?", (arquivo_id,)).fetchone()
    conn.close()

    if not arq:
        abort(404)

    return send_from_directory(
        UPLOAD_DIR,
        arq['filename'],
        as_attachment=True,
        download_name=arq['original_name']
    )

@app.route('/arquivos/excluir/<int:arquivo_id>', methods=['POST'])
@adm_required
def excluir_arquivo(arquivo_id):
    conn = get_db()
    arq = conn.execute("SELECT * FROM arquivos WHERE id=?", (arquivo_id,)).fetchone()

    if arq:
        filepath = os.path.join(UPLOAD_DIR, arq['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)
        conn.execute("DELETE FROM arquivos WHERE id=?", (arquivo_id,))
        conn.commit()
        flash('Arquivo excluído.', 'info')

    conn.close()
    return redirect(url_for('listar_arquivos'))

# — Perfil —
@app.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    user_id  = session['user_id']
    user     = get_user(user_id)
    avatares = ['🎓', '📚', '✏️', '🌟', '🧠', '🎒', '🌻', '🦋', '🐬', '🚀',
                '👑', '🏅', '🎨', '🎵', '⚽', '🌈', '🦁', '🐺', '🦅', '🌙']

    if request.method == 'POST':
        nome     = request.form.get('nome', '').strip()
        turma    = request.form.get('turma', '').strip()
        avatar   = request.form.get('avatar', '🎓')
        senha    = request.form.get('senha', '')
        confirma = request.form.get('confirma', '')

        if not nome:
            flash('O nome não pode ficar vazio.', 'warning')
            return redirect(url_for('perfil'))

        conn = get_db()

        if senha:
            if senha != confirma:
                flash('As senhas não coincidem.', 'danger')
                conn.close()
                return redirect(url_for('perfil'))
            conn.execute(
                "UPDATE users SET nome=?, turma=?, avatar=?, password=? WHERE id=?",
                (nome, turma, avatar, hash_pwd(senha), user_id)
            )
        else:
            conn.execute(
                "UPDATE users SET nome=?, turma=?, avatar=? WHERE id=?",
                (nome, turma, avatar, user_id)
            )

        conn.commit()
        conn.close()

        session['nome']   = nome
        session['avatar'] = avatar
        flash('Perfil atualizado com sucesso! ✅', 'success')
        return redirect(url_for('perfil'))

    return render_template('perfil.html', user=user, avatares=avatares)

# — Painel ADM —
@app.route('/adm')
@adm_required
def painel_adm():
    conn = get_db()
    usuarios   = conn.execute("SELECT * FROM users WHERE role='user'").fetchall()
    arquivos   = get_arquivos()
    total_msgs = conn.execute("SELECT COUNT(*) FROM mensagens").fetchone()[0]
    conn.close()
    return render_template('adm.html',
        usuarios=usuarios, arquivos=arquivos, total_msgs=total_msgs
    )

@app.route('/adm/usuario/<int:uid>/excluir', methods=['POST'])
@adm_required
def excluir_usuario(uid):
    if uid == session['user_id']:
        flash('Você não pode excluir sua própria conta.', 'danger')
        return redirect(url_for('painel_adm'))
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.execute("DELETE FROM mensagens WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()
    flash('Usuário removido.', 'info')
    return redirect(url_for('painel_adm'))

# — Registro —
@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        nome     = request.form.get('nome', '').strip()
        turma    = request.form.get('turma', '').strip()
        senha    = request.form.get('senha', '')
        confirma = request.form.get('confirma', '')

        if not username or not senha or not nome:
            flash('Preencha todos os campos obrigatórios.', 'warning')
            return redirect(url_for('registro'))

        if senha != confirma:
            flash('As senhas não coincidem.', 'danger')
            return redirect(url_for('registro'))

        if len(senha) < 4:
            flash('A senha deve ter pelo menos 4 caracteres.', 'warning')
            return redirect(url_for('registro'))

        conn = get_db()
        existing = conn.execute(
            "SELECT id FROM users WHERE username=?", (username,)
        ).fetchone()

        if existing:
            flash('Este nome de usuário já está em uso.', 'danger')
            conn.close()
            return redirect(url_for('registro'))

        conn.execute(
            "INSERT INTO users (username, password, role, nome, turma, avatar) "
            "VALUES (?,?,?,?,?,?)",
            (username, hash_pwd(senha), 'user', nome, turma, '🎓')
        )
        conn.commit()
        conn.close()

        flash('Conta criada com sucesso! Faça login. 🎉', 'success')
        return redirect(url_for('login'))

    return render_template('registro.html')

# ─── Inicialização ────────────────────────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    print("\n🧹 Ordina — Sistema iniciado!")
    print("📌 Acesse: http://localhost:5000")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))