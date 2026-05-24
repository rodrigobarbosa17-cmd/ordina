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

### 2. Rode o sistema
```bash
python app.py
```

### 3. Acesse no navegador
```
http://localhost:5000
```

---

## 👑 Contas padrão

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
