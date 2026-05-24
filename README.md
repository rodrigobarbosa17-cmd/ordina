# 🧹 Sala Limpa — Sistema de Chat para Organização de Sala de Aula

## 📋 Descrição
Sistema web em Flask para auxiliar turmas com limpeza e organização da sala de aula.
Possui chatbox com IA, sistema de login com perfis ADM e Aluno, e gerenciamento de PDFs.

---

## 🚀 Como rodar

### 1. Instale o Flask
```bash
pip install flask werkzeug
```

### 2. (Opcional) Configure a API da Anthropic para IA real
```bash
# Linux/Mac
export ANTHROPIC_API_KEY="sua_chave_aqui"

# Windows
set ANTHROPIC_API_KEY=sua_chave_aqui
```
> Sem a chave, o sistema usa respostas pré-programadas inteligentes sobre limpeza.

### 3. Rode o sistema
```bash
python app.py
```

### 4. Acesse no navegador
```
http://localhost:5000
```

---

## 👑 Contas padrão

| Tipo  | Usuário | Senha  |
|-------|---------|--------|
| ADM   | adm     | adm123 |
| Aluno | aluno   | user123 |

> **Altere as senhas pelo perfil após o primeiro acesso!**

---

## 📁 Estrutura do projeto

```
sala_limpa/
├── app.py                  ← Aplicação principal Flask
├── database.db             ← Banco de dados SQLite (criado automaticamente)
├── uploads/                ← PDFs enviados pelo ADM
├── static/
│   └── css/
│       └── style.css       ← Estilos do site
└── templates/
    ├── base.html           ← Template base (navbar, flash, footer)
    ├── login.html          ← Página de login
    ├── registro.html       ← Página de cadastro
    ├── chat.html           ← Chat com IA
    ├── arquivos.html       ← Lista de arquivos
    ├── upload.html         ← Upload de PDF (ADM)
    ├── perfil.html         ← Editar perfil
    └── adm.html            ← Painel administrativo
```

---

## 🔧 Como personalizar

### Trocar a escola/turma no sistema
- Edite o `SYSTEM_PROMPT` em `app.py` para personalizar o comportamento da IA

### Adicionar mais palavras-chave para detectar pedido da escala
- Edite a lista `ESCALA_TRIGGER` em `app.py`

### Mudar cores do site
- Edite as variáveis CSS em `static/css/style.css` (seção `:root`)

### Adicionar novos avatares
- Edite a lista `avatares` na rota `/perfil` em `app.py`

### Mudar porta do servidor
- Edite `port=5000` na última linha de `app.py`

---

## ✨ Funcionalidades

| Funcionalidade | ADM | Aluno |
|---------------|-----|-------|
| Chat com IA sobre limpeza | ✅ | ✅ |
| Ver arquivos PDF | ✅ | ✅ |
| Baixar PDF | ✅ | ✅ |
| Enviar PDF | ✅ | ❌ |
| Excluir PDF | ✅ | ❌ |
| Editar perfil próprio | ✅ | ✅ |
| Ver painel ADM | ✅ | ❌ |
| Gerenciar usuários | ✅ | ❌ |
| Criar conta nova | ✅ | ✅ |

---

## 💡 Dicas de uso em sala

1. O ADM sobe a **Escala de Limpeza** em PDF
2. Os alunos perguntam ao chat: *"Preciso ver a escala de limpeza"*
3. O chat responde com o link para baixar o PDF mais recente
4. Novos PDFs substituem os antigos automaticamente no chat

---

## 🔐 Segurança
- Senhas são armazenadas com hash SHA-256
- Sessões protegidas por chave secreta Flask
- Upload restrito a arquivos PDF
- Rotas ADM verificam permissão no servidor
