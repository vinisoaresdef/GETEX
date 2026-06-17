#!/usr/bin/env python3
"""
getex  — Editor de texto modal para terminal, estilo Vim.

Uso:
  getex              → abre o editor
  getex get all      → navegador de arquivos salvos

Seleção de texto (modo inserção):
  Shift+Setas             → seleciona caractere a caractere
  Ctrl+Shift+← / →        → seleciona palavra inteira
  Ctrl+Shift+↑ / ↓        → seleciona linha inteira (para cima/baixo)
  Shift+Home / Shift+End  → seleciona até início/fim da linha
  Ctrl+A                  → seleciona tudo

  Ctrl+C  → copiar seleção (clipboard interno)
  Ctrl+K  → recortar seleção  (Ctrl+X foi substituído: conflita com terminal)
  Ctrl+V  → colar
  Delete / Backspace (com seleção ativa) → apagar seleção
"""

import curses
import os
import sys
import json
import time
import uuid
import socket
import hashlib
import secrets
import datetime
import calendar

# ─── Constantes ─────────────────────────────────────────────────────────────
CONFIG_FILE = os.path.expanduser("~/.getex_config")
ESC_KEY     = 27
MAX_FILE_SIZE = 1024 * 1024  # 1 MB - limite para carregar arquivo inteiro

# ─── Firebase / paths ────────────────────────────────────────────────────────
GETEX_HOME     = os.path.expanduser("~/.getex")
FB_CRED_DIR    = os.path.join(GETEX_HOME, "firebase")
SESSION_FILE   = os.path.join(GETEX_HOME, "session.json")
SYNC_DIR       = os.path.join(GETEX_HOME, "sync")
TOMBSTONE_FILE = os.path.join(SYNC_DIR, "tombstones.json")

# Usuário "convidado" usado quando o Firebase não está configurado:
# mantém o getex 100% funcional em modo local, sem exigir login.
LOCAL_GUEST = {
    "uid": "local", "email": "local", "name": "local",
    "workspace_id": "local", "salt": "", "password_hash": "",
}

DEFAULT_CONFIG = {
    "folder_name": "GetexDocs",
    "ai_provider": "gemini",
    "api_key":     "",
    "theme":       "default",
}

THEMES = {
    "default": {
        "bg_fg":     (-1, -1),
        "insert":    (curses.COLOR_BLACK, curses.COLOR_CYAN),
        "command":   (curses.COLOR_BLACK, curses.COLOR_YELLOW),
        "error":     (curses.COLOR_WHITE, curses.COLOR_RED),
        "linenum":   (curses.COLOR_CYAN, -1),
        "cmdbar":    (curses.COLOR_WHITE, curses.COLOR_BLUE),
        "info":      (curses.COLOR_GREEN, -1),
        "listsel":   (curses.COLOR_BLACK, curses.COLOR_WHITE),
        "title":     (curses.COLOR_YELLOW, -1),
        "header":    (curses.COLOR_WHITE, curses.COLOR_MAGENTA),
        "selection": (curses.COLOR_BLACK, curses.COLOR_CYAN),
        "aishortcut":(curses.COLOR_BLACK, curses.COLOR_GREEN),
        "mk_g_line": (curses.COLOR_WHITE, curses.COLOR_GREEN),
        "mk_r_line": (curses.COLOR_WHITE, curses.COLOR_RED),
        "mk_g_num":  (curses.COLOR_BLACK, curses.COLOR_GREEN),
        "mk_r_num":  (curses.COLOR_WHITE, curses.COLOR_RED),
    },
    "dark": {
        "bg_fg":     (curses.COLOR_WHITE, curses.COLOR_BLACK),
        "insert":    (curses.COLOR_BLACK, curses.COLOR_CYAN),
        "command":   (curses.COLOR_BLACK, curses.COLOR_YELLOW),
        "error":     (curses.COLOR_WHITE, curses.COLOR_RED),
        "linenum":   (curses.COLOR_CYAN, curses.COLOR_BLACK),
        "cmdbar":    (curses.COLOR_WHITE, curses.COLOR_BLUE),
        "info":      (curses.COLOR_GREEN, curses.COLOR_BLACK),
        "listsel":   (curses.COLOR_BLACK, curses.COLOR_WHITE),
        "title":     (curses.COLOR_YELLOW, curses.COLOR_BLACK),
        "header":    (curses.COLOR_WHITE, curses.COLOR_MAGENTA),
        "selection": (curses.COLOR_BLACK, curses.COLOR_CYAN),
        "aishortcut":(curses.COLOR_BLACK, curses.COLOR_GREEN),
        "mk_g_line": (curses.COLOR_WHITE, curses.COLOR_GREEN),
        "mk_r_line": (curses.COLOR_WHITE, curses.COLOR_RED),
        "mk_g_num":  (curses.COLOR_BLACK, curses.COLOR_GREEN),
        "mk_r_num":  (curses.COLOR_WHITE, curses.COLOR_RED),
    },
    "light": {
        "bg_fg":     (curses.COLOR_BLACK, curses.COLOR_WHITE),
        "insert":    (curses.COLOR_WHITE, curses.COLOR_BLUE),
        "command":   (curses.COLOR_WHITE, curses.COLOR_MAGENTA),
        "error":     (curses.COLOR_WHITE, curses.COLOR_RED),
        "linenum":   (curses.COLOR_BLUE, curses.COLOR_WHITE),
        "cmdbar":    (curses.COLOR_WHITE, curses.COLOR_BLACK),
        "info":      (curses.COLOR_BLUE, curses.COLOR_WHITE),
        "listsel":   (curses.COLOR_WHITE, curses.COLOR_BLUE),
        "title":     (curses.COLOR_MAGENTA, curses.COLOR_WHITE),
        "header":    (curses.COLOR_BLACK, curses.COLOR_CYAN),
        "selection": (curses.COLOR_WHITE, curses.COLOR_BLUE),
        "aishortcut":(curses.COLOR_WHITE, curses.COLOR_BLUE),
        "mk_g_line": (curses.COLOR_WHITE, curses.COLOR_GREEN),
        "mk_r_line": (curses.COLOR_WHITE, curses.COLOR_RED),
        "mk_g_num":  (curses.COLOR_BLACK, curses.COLOR_GREEN),
        "mk_r_num":  (curses.COLOR_WHITE, curses.COLOR_RED),
    },
    "hacker": {
        "bg_fg":     (curses.COLOR_GREEN, curses.COLOR_BLACK),
        "insert":    (curses.COLOR_BLACK, curses.COLOR_GREEN),
        "command":   (curses.COLOR_BLACK, curses.COLOR_GREEN),
        "error":     (curses.COLOR_BLACK, curses.COLOR_RED),
        "linenum":   (curses.COLOR_WHITE, curses.COLOR_BLACK),
        "cmdbar":    (curses.COLOR_BLACK, curses.COLOR_GREEN),
        "info":      (curses.COLOR_WHITE, curses.COLOR_BLACK),
        "listsel":   (curses.COLOR_BLACK, curses.COLOR_GREEN),
        "title":     (curses.COLOR_GREEN, curses.COLOR_BLACK),
        "header":    (curses.COLOR_BLACK, curses.COLOR_GREEN),
        "selection": (curses.COLOR_BLACK, curses.COLOR_GREEN),
        "aishortcut":(curses.COLOR_BLACK, curses.COLOR_GREEN),
        "mk_g_line": (curses.COLOR_BLACK, curses.COLOR_CYAN),
        "mk_r_line": (curses.COLOR_WHITE, curses.COLOR_RED),
        "mk_g_num":  (curses.COLOR_BLACK, curses.COLOR_CYAN),
        "mk_r_num":  (curses.COLOR_WHITE, curses.COLOR_RED),
    },
    "ocean": {
        "bg_fg":     (curses.COLOR_WHITE, curses.COLOR_BLUE),
        "insert":    (curses.COLOR_BLUE, curses.COLOR_CYAN),
        "command":   (curses.COLOR_BLUE, curses.COLOR_CYAN),
        "error":     (curses.COLOR_WHITE, curses.COLOR_RED),
        "linenum":   (curses.COLOR_CYAN, curses.COLOR_BLUE),
        "cmdbar":    (curses.COLOR_BLUE, curses.COLOR_WHITE),
        "info":      (curses.COLOR_CYAN, curses.COLOR_BLUE),
        "listsel":   (curses.COLOR_BLUE, curses.COLOR_WHITE),
        "title":     (curses.COLOR_CYAN, curses.COLOR_BLUE),
        "header":    (curses.COLOR_BLUE, curses.COLOR_WHITE),
        "selection": (curses.COLOR_BLUE, curses.COLOR_CYAN),
        "aishortcut":(curses.COLOR_BLUE, curses.COLOR_CYAN),
        "mk_g_line": (curses.COLOR_WHITE, curses.COLOR_GREEN),
        "mk_r_line": (curses.COLOR_WHITE, curses.COLOR_RED),
        "mk_g_num":  (curses.COLOR_BLUE, curses.COLOR_GREEN),
        "mk_r_num":  (curses.COLOR_WHITE, curses.COLOR_RED),
    }
}

# ─── Config ──────────────────────────────────────────────────────────────────
def load_env_file():
    """Carrega variáveis de um arquivo .env na pasta do projeto."""
    env_path = os.path.expanduser(f"~/.getex/.env")
    if not os.path.exists(env_path):
        return {}
    env_vars = {}
    try:
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    env_vars[key.strip()] = value.strip().strip('"').strip("'")
    except Exception:
        pass
    return env_vars

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
                env_vars = load_env_file()
                if "GETEX_API_KEY" in env_vars:
                    cfg["api_key"] = env_vars["GETEX_API_KEY"]
                return cfg
        except Exception:
            pass
    return None

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

def first_run_setup():
    print("\n╔══════════════════════════════════════╗")
    print("║   getex — Configuração Inicial       ║")
    print("╚══════════════════════════════════════╝\n")
    cfg = DEFAULT_CONFIG.copy()
    folder = input("Nome da pasta na Área de Trabalho para os documentos? [GetexDocs]: ").strip()
    cfg["folder_name"] = folder or "GetexDocs"
    provider = input("Provedor de IA? (gemini/openai) [gemini]: ").strip().lower()
    cfg["ai_provider"] = provider if provider in ("gemini", "openai") else "gemini"
    key = input(f"Chave de API ({cfg['ai_provider']}) [deixe em branco para depois]: ").strip()
    cfg["api_key"] = key
    save_config(cfg)
    print(f"\n✓ Config salva em {CONFIG_FILE}")
    print(f"✓ Documentos em ~/Desktop/{cfg['folder_name']}/\n")
    input("Pressione Enter para abrir o editor...")
    return cfg

# ─── Helpers de tecla ────────────────────────────────────────────────────────
def is_enter(k):
    return k in ("\n", "\r") or k == curses.KEY_ENTER

def is_backspace(k):
    return k in (curses.KEY_BACKSPACE, 127, "\x7f")

def is_esc(k):
    return k == ESC_KEY or k == "\x1b"

# ─── IA ──────────────────────────────────────────────────────────────────────
def _make_ai_request(prompt, cfg, timeout=30):
    """Helper interno para chamadas de API (elimina duplicação)."""
    import urllib.request
    import json as _json

    api_key  = cfg.get("api_key", "")
    if not api_key:
        return None, "[ERRO] Nenhuma chave de API configurada. Use :set key SUA_CHAVE"

    provider = cfg.get("ai_provider", "gemini")
    if provider == "gemini":
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.5-flash:generateContent?key={api_key}"
        )
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        req = urllib.request.Request(
            url, data=_json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = _json.loads(resp.read())
        return data["candidates"][0]["content"]["parts"][0]["text"].strip(), None
    else:
        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 500,
        }
        req = urllib.request.Request(
            url, data=_json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }, method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = _json.loads(resp.read())
        return data["choices"][0]["message"]["content"].strip(), None

def call_ai(text, cfg):
    try:
        prompt = (
            "Continue, melhore ou responda ao seguinte texto "
            "de forma útil e concisa:\n\n" + text
        )
        result, err = _make_ai_request(prompt, cfg, timeout=30)
        if err:
            return err
        return result
    except Exception as e:
        return f"[ERRO IA] {e}"

def call_ai_organizer(text, cfg):
    """
    Envia o texto bruto para a IA com um prompt especializado em
    estruturar/reorganizar documentos (requisitos, notas, etc.).
    Retorna o texto organizado como string.
    """
    prompt = (
        "Você é um especialista em documentação técnica e organização de textos.\n\n"
        "Analise o texto abaixo e reescreva-o de forma estruturada, clara e profissional. "
        "Identifique automaticamente o tipo de documento (requisitos, notas de reunião, "
        "ideias, relatório, etc.) e aplique a estrutura mais adequada para esse tipo.\n\n"
        "Regras obrigatórias:\n"
        "- Preserve TODAS as informações do original — nada pode ser removido ou omitido\n"
        "- Use títulos e seções quando fizer sentido\n"
        "- Agrupe itens relacionados\n"
        "- O texto será aberto dentro de um terminal, então use linguagem clara, sem asteriscos, hashtags\n"
        "- Se for separar tópicos importantes, utilize algo como: ════════════════════════════════════════════[TÓPICO]════════════════════════════════════════════\n"
        "- Corrija erros de português e melhore a clareza das frases\n"
        "- Se for uma lista de requisitos, numere-os e categorize-os\n"
        "- Seja o mais sucinto possível, sem perder informações, mas sendo resumido.\n"
        "- Use marcadores (- ou •) para listas de itens\n\n"
        "Texto original:\n\n"
        + text
    )
    result, err = _make_ai_request(prompt, cfg, timeout=60)
    if err:
        return err
    return result


# ─── Salvar documento ────────────────────────────────────────────────────────
def slugify(title):
    """Converte um título livre em parte segura para nome de arquivo."""
    import re
    title = title.strip()
    # remove caracteres proibidos em nomes de arquivo
    title = re.sub(r'[\\/:*?"<>|]', "", title)
    # colapsa espaços em underscore
    title = re.sub(r"\s+", "_", title)
    return title[:60]  # limita para não estourar PATH_MAX

def build_filepath(cfg, title=None):
    """
    Monta o caminho do arquivo.
    Formato: DOC_YYYY-MM-DD_HH-MM[_titulo].txt
    A hora é incluída para evitar colisão quando há múltiplos arquivos no dia.
    """
    folder_path = active_folder(cfg)
    now   = datetime.datetime.now()
    stamp = now.strftime("%Y-%m-%d_%H-%M")
    if title:
        fname = f"DOC_{stamp}_{slugify(title)}.txt"
    else:
        fname = f"DOC_{stamp}.txt"
    return os.path.join(folder_path, fname)

def save_document(lines, cfg, filepath=None, overwrite=False, title=None):
    """
    Salva o buffer em disco.
    - filepath=None   → gera novo arquivo com data+hora (e título se fornecido)
    - overwrite=False → se arquivo já existir, adiciona nova sessão com separador
    - overwrite=True  → sobrescreve o arquivo inteiro (usado ao editar existente)
    - title           → incluído no nome do arquivo quando filepath=None
    """
    content = "\n".join(lines)
    if filepath is None:
        filepath = build_filepath(cfg, title=title)
    if overwrite or not os.path.exists(filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
    else:
        ts  = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sep = f"\n\n{'─'*50}\n[Sessão adicionada em {ts}]\n{'─'*50}\n\n"
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(sep + content)
    return filepath

# ─── Utilitários de posição ──────────────────────────────────────────────────
def pos_lt(r1, c1, r2, c2):
    """True se (r1,c1) < (r2,c2)."""
    return (r1, c1) < (r2, c2)

def sel_ordered(ar, ac, cr, cc):
    """Retorna (start_row, start_col, end_row, end_col) normalizado."""
    if (ar, ac) <= (cr, cc):
        return ar, ac, cr, cc
    return cr, cc, ar, ac

def extract_selection(lines, sr, sc, er, ec):
    """Extrai o texto da seleção como lista de linhas."""
    if sr == er:
        return [lines[sr][sc:ec]]
    result = [lines[sr][sc:]]
    for r in range(sr + 1, er):
        result.append(lines[r])
    result.append(lines[er][:ec])
    return result

def delete_selection(lines, sr, sc, er, ec):
    """Remove a seleção do buffer e retorna (novas_linhas, row, col)."""
    before = lines[sr][:sc]
    after  = lines[er][ec:]
    new_lines = lines[:sr] + [before + after] + lines[er+1:]
    if not new_lines:
        new_lines = [""]
    return new_lines, sr, sc

# ═══════════════════════════════════════════════════════════════════════════════
# CORES
# ═══════════════════════════════════════════════════════════════════════════════
def init_colors(cfg=None):
    if cfg is None:
        cfg = {}
    theme_name = cfg.get("theme", "default")
    if theme_name not in THEMES:
        theme_name = "default"
    t = THEMES[theme_name]

    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1,  t["insert"][0],  t["insert"][1])
    curses.init_pair(2,  t["command"][0], t["command"][1])
    curses.init_pair(3,  t["error"][0],   t["error"][1])
    curses.init_pair(4,  t["linenum"][0], t["linenum"][1])
    curses.init_pair(5,  t["cmdbar"][0],  t["cmdbar"][1])
    curses.init_pair(6,  t["info"][0],    t["info"][1])
    curses.init_pair(7,  t["listsel"][0], t["listsel"][1])
    curses.init_pair(8,  t["title"][0],   t["title"][1])
    curses.init_pair(9,  t["header"][0],  t["header"][1])
    curses.init_pair(10, t["selection"][0], t["selection"][1])
    curses.init_pair(11, t["aishortcut"][0], t["aishortcut"][1])
    curses.init_pair(12, t["mk_g_line"][0], t["mk_g_line"][1])
    curses.init_pair(13, t["mk_r_line"][0], t["mk_r_line"][1])
    curses.init_pair(14, t["mk_g_num"][0], t["mk_g_num"][1])
    curses.init_pair(15, t["mk_r_num"][0], t["mk_r_num"][1])
    curses.init_pair(16, t["bg_fg"][0], t["bg_fg"][1])

# ─── Marcações de linha ────────────────────────────────────────────────────────
def marks_path(filepath):
    """Caminho do arquivo .marks paralelo ao .txt."""
    return filepath + ".marks"

def load_marks(filepath):
    """Carrega marcações do arquivo .marks. Retorna dict {int: str}."""
    mp = marks_path(filepath)
    if not os.path.exists(mp):
        return {}
    try:
        with open(mp, "r") as f:
            raw = json.load(f)
        return {int(k): v for k, v in raw.items()}
    except Exception:
        return {}

def save_marks(filepath, marks):
    """Persiste marcações no arquivo .marks."""
    if not filepath:
        return
    mp = marks_path(filepath)
    try:
        if marks:
            with open(mp, "w") as f:
                json.dump({str(k): v for k, v in marks.items()}, f)
        elif os.path.exists(mp):
            os.remove(mp)  # sem marcações → remove arquivo
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════════════════════
# FIREBASE  —  autenticação simples + sincronização offline/online
# ═══════════════════════════════════════════════════════════════════════════════
#
# Arquitetura (mantida deliberadamente simples para um app de terminal):
#
#  • As notas continuam sendo arquivos .txt em ~/Desktop/<pasta>/ (fonte local).
#  • Cada nota ganha um "sidecar" <arquivo>.txt.sync.json com os metadados de
#    sincronização: {id, workspace_id, owner_uid, updated_at, dirty, deleted}.
#  • Online  → empurra notas "dirty" e puxa as do workspace do usuário (Firestore).
#  • Offline → tudo funciona local; mudanças ficam "dirty" e sobem no próximo sync.
#  • Resolução de conflito: last-write-wins por updated_at (epoch).
#  • Login: coleção Firestore "users" (email + hash PBKDF2). O Admin SDK lê/grava.
#
# Coleções no Firestore:
#   users/{uid}        → {email, name, salt, password_hash, personal_workspace, ...}
#   workspaces/{wid}   → {name, owner_uid, members:[uid], personal, created_at}
#   notes/{noteid}     → {filename, title, content, marks, workspace_id, owner_uid,
#                         updated_at, deleted}
#
# Estado global do Firebase (evita passar db/user por todos os construtores).
_fb_state = {"db": None, "user": None, "reason": "", "online": False}

def fb_db():        return _fb_state["db"]
def fb_user():      return _fb_state["user"]
def fb_reason():    return _fb_state["reason"]
def fb_is_online(): return bool(_fb_state["online"] and _fb_state["db"] is not None)

def fb_is_real_user():
    """True se há um usuário Firebase logado (não o convidado local)."""
    u = _fb_state["user"]
    return bool(u and u.get("uid") and u.get("uid") != "local")

# ─── Localização da credencial (service account) ────────────────────────────
def find_credential():
    """Procura o JSON do service account em vários locais conhecidos."""
    env = os.environ.get("GETEX_FIREBASE_CRED")
    if env and os.path.exists(os.path.expanduser(env)):
        return os.path.expanduser(env)
    candidates = []
    if os.path.isdir(FB_CRED_DIR):
        preferred = os.path.join(FB_CRED_DIR, "service-account.json")
        if os.path.exists(preferred):
            return preferred
        candidates += [os.path.join(FB_CRED_DIR, f)
                       for f in sorted(os.listdir(FB_CRED_DIR)) if f.endswith(".json")]
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        local_dir = os.path.join(here, "firebase")
        if os.path.isdir(local_dir):
            candidates += [os.path.join(local_dir, f)
                           for f in sorted(os.listdir(local_dir)) if f.endswith(".json")]
    except Exception:
        pass
    return candidates[0] if candidates else None

def fb_init():
    """Inicializa o Firebase Admin SDK + cliente Firestore. Retorna db ou None.

    Importa firebase_admin de forma preguiçosa: se não houver credencial, nem
    sequer tentamos importar (mantém a inicialização rápida em modo local)."""
    cred_path = find_credential()
    if not cred_path:
        _fb_state["reason"] = "Sem credencial Firebase — modo local"
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except Exception:
        _fb_state["reason"] = "firebase-admin não instalado — modo local"
        return None
    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app(credentials.Certificate(cred_path))
        _fb_state["db"] = firestore.client()
        return _fb_state["db"]
    except Exception as e:
        _fb_state["reason"] = f"Falha ao iniciar Firebase: {e}"
        return None

def check_online():
    """Checagem rápida de conectividade (socket TCP até o Firestore)."""
    if _fb_state["db"] is None:
        _fb_state["online"] = False
        return False
    try:
        s = socket.create_connection(("firestore.googleapis.com", 443), timeout=3)
        s.close()
        _fb_state["online"] = True
    except Exception:
        _fb_state["online"] = False
    return _fb_state["online"]

def _friendly_fb_error(e):
    msg = str(e)
    if "SERVICE_DISABLED" in msg or "has not been used" in msg:
        return "Firestore não habilitado no projeto. Ative no console do Firebase."
    if "PERMISSION_DENIED" in msg:
        return "Permissão negada no Firestore (verifique a credencial)."
    return f"Erro Firestore: {msg[:60]}"

def _where(coll, field, op, value):
    """Filtro de consulta compatível com versões novas e antigas do SDK."""
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter
        return coll.where(filter=FieldFilter(field, op, value))
    except Exception:
        return coll.where(field, op, value)

# ─── Senhas (PBKDF2-HMAC-SHA256) ─────────────────────────────────────────────
def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                             bytes.fromhex(salt), 100_000)
    return salt, dk.hex()

def verify_password(password, salt, expected_hash):
    if not salt or not expected_hash:
        return False
    _, h = hash_password(password, salt)
    return secrets.compare_digest(h, expected_hash)

# ─── Workspaces ──────────────────────────────────────────────────────────────
# Modelo: o usuário escolhe um WORKSPACE (ex.: UMTI, PESSOAL) e tem uma conta
# DENTRO daquele workspace. A mesma pessoa pode ter contas em workspaces
# diferentes (logins separados). As notas pertencem ao workspace, então todos
# os membros de um workspace veem as mesmas notas.
#
# Firestore:
#   workspaces/{WID}              → {name, key_salt, key_hash, created_at, created_by}
#   workspaces/{WID}/users/{uid}  → {email, name, salt, password_hash, created_at}
#   notes/{noteid}                → {workspace_id: WID, owner_uid, author_email, ...}
#
# WID = nome normalizado do workspace (maiúsculas, sem espaços/símbolos), o que
# garante unicidade e serve de identificador digitável no login.
# Para criar/entrar num workspace é preciso a CHAVE do workspace (segredo) —
# é isso que mantém o PESSOAL privado e o UMTI restrito a quem tem a chave.

def normalize_ws(name):
    """Normaliza o nome do workspace para usar como ID do documento."""
    s = (name or "").strip().upper()
    out = []
    for ch in s:
        if ch.isalnum():
            out.append(ch)
        elif ch in (" ", "-", "_"):
            out.append("_")
        # demais caracteres são descartados
    return "".join(out)[:64]

def fb_find_workspace(db, wid):
    snap = db.collection("workspaces").document(wid).get()
    if snap.exists:
        w = snap.to_dict()
        w["id"] = wid
        return w
    return None

def fb_find_user_in_ws(db, wid, email):
    email = email.strip().lower()
    coll = db.collection("workspaces").document(wid).collection("users")
    for d in _where(coll, "email", "==", email).limit(1).stream():
        u = d.to_dict()
        u["uid"] = d.id
        return u
    return None

def _session_from(u, wid, ws_name):
    return {
        "uid": u["uid"], "email": u["email"], "name": u.get("name", ""),
        "workspace_id": wid, "workspace_name": ws_name,
        "salt": u.get("salt", ""), "password_hash": u.get("password_hash", ""),
    }

def _create_user_doc(db, wid, email, password, name):
    """Cria o documento de usuário dentro do workspace e devolve (uid, salt, hash)."""
    salt, h = hash_password(password)
    uid = uuid.uuid4().hex
    nm  = name.strip() or email.split("@")[0]
    db.collection("workspaces").document(wid).collection("users").document(uid).set({
        "email": email, "name": nm, "salt": salt, "password_hash": h,
        "created_at": time.time(),
    })
    return uid, salt, h, nm

def fb_create_workspace(db, ws_name, email, password, name=""):
    """Cria um NOVO workspace (o nome é a chave primária — não pode existir outro
    igual) e a conta do criador, que vira o administrador. Sem chave de acesso."""
    email = email.strip().lower()
    wid   = normalize_ws(ws_name)
    if not wid:
        return None, "Informe um nome de workspace válido"
    try:
        if fb_find_workspace(db, wid) is not None:
            return None, f"Workspace '{wid}' já existe — peça ao admin para te adicionar"
        uid, salt, h, nm = _create_user_doc(db, wid, email, password, name)
        db.collection("workspaces").document(wid).set({
            "name": wid, "created_at": time.time(),
            "created_by": email, "admin_uid": uid,
        })
        return _session_from({"uid": uid, "email": email, "name": nm,
                              "salt": salt, "password_hash": h}, wid, wid), None
    except Exception as e:
        return None, _friendly_fb_error(e)

def fb_add_member(db, wid, email, password, name=""):
    """Ação do ADMIN: cria a conta de um usuário dentro de um workspace existente."""
    email = email.strip().lower()
    try:
        if fb_find_workspace(db, wid) is None:
            return None, "Workspace não encontrado"
        if fb_find_user_in_ws(db, wid, email):
            return None, "Email já cadastrado neste workspace"
        _create_user_doc(db, wid, email, password, name)
        return True, None
    except Exception as e:
        return None, _friendly_fb_error(e)

def fb_login(db, ws_name, email, password):
    wid = normalize_ws(ws_name)
    if not wid:
        return None, "Informe o workspace"
    try:
        ws = fb_find_workspace(db, wid)
        if ws is None:
            return None, "Workspace não encontrado"
        u = fb_find_user_in_ws(db, wid, email)
    except Exception as e:
        return None, _friendly_fb_error(e)
    if not u:
        return None, "Usuário não encontrado neste workspace"
    if not verify_password(password, u.get("salt", ""), u.get("password_hash", "")):
        return None, "Senha incorreta"
    return _session_from(u, wid, ws.get("name", wid)), None

def offline_login(ws_name, email, password):
    s = load_session()
    if not s:
        return None, "Sem sessão local — conecte-se para o 1º login."
    if s.get("workspace_id", "") != normalize_ws(ws_name):
        return None, "Offline: só o último workspace usado está disponível."
    if s.get("email", "").lower() != email.strip().lower():
        return None, "Offline: apenas o último usuário pode entrar."
    if not verify_password(password, s.get("salt", ""), s.get("password_hash", "")):
        return None, "Senha incorreta"
    return s, None

# ─── Gestão de conta / membros do workspace ──────────────────────────────────
def fb_change_password(db, wid, uid, old_pw, new_pw):
    """Verifica a senha atual e grava a nova. Retorna ((salt,hash), None) ou (False, erro)."""
    try:
        ref  = db.collection("workspaces").document(wid).collection("users").document(uid)
        snap = ref.get()
        if not snap.exists:
            return False, "Conta não encontrada"
        u = snap.to_dict()
        if not verify_password(old_pw, u.get("salt", ""), u.get("password_hash", "")):
            return False, "Senha atual incorreta"
        salt, h = hash_password(new_pw)
        ref.update({"salt": salt, "password_hash": h})
        return (salt, h), None
    except Exception as e:
        return False, _friendly_fb_error(e)

def fb_list_members(db, wid):
    """Lista os usuários (membros) de um workspace."""
    out = []
    for d in db.collection("workspaces").document(wid).collection("users").stream():
        u = d.to_dict()
        out.append({"uid": d.id, "email": u.get("email", ""), "name": u.get("name", "")})
    out.sort(key=lambda m: m["email"])
    return out

def fb_remove_member(db, wid, uid):
    try:
        db.collection("workspaces").document(wid).collection("users").document(uid).delete()
        return True, None
    except Exception as e:
        return False, _friendly_fb_error(e)

def fb_workspace_creator(db, wid):
    """Email de quem criou o workspace (é o 'admin' que pode remover membros)."""
    ws = fb_find_workspace(db, wid)
    return (ws or {}).get("created_by", "")

# ─── Sessão local ────────────────────────────────────────────────────────────
def save_session(user):
    try:
        os.makedirs(GETEX_HOME, exist_ok=True)
        with open(SESSION_FILE, "w") as f:
            json.dump(user, f)
        os.chmod(SESSION_FILE, 0o600)
    except Exception:
        pass

def load_session():
    try:
        with open(SESSION_FILE) as f:
            return json.load(f)
    except Exception:
        return None

def clear_session():
    try:
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
    except Exception:
        pass

# ─── Sidecars de sincronização ───────────────────────────────────────────────
def sidecar_path(filepath):
    return filepath + ".sync.json"

def load_sidecar(filepath):
    try:
        with open(sidecar_path(filepath)) as f:
            return json.load(f)
    except Exception:
        return None

def save_sidecar(filepath, meta):
    try:
        with open(sidecar_path(filepath), "w") as f:
            json.dump(meta, f)
    except Exception:
        pass

def ensure_sidecar(filepath, workspace_id, owner_uid):
    """Garante metadados de sync (migra notas locais antigas marcando-as dirty)."""
    meta = load_sidecar(filepath)
    if meta is None:
        try:
            mtime = os.path.getmtime(filepath)
        except Exception:
            mtime = time.time()
        meta = {"id": uuid.uuid4().hex, "workspace_id": workspace_id,
                "owner_uid": owner_uid, "updated_at": mtime,
                "dirty": True, "deleted": False}
        save_sidecar(filepath, meta)
    return meta

def mark_note_dirty(filepath):
    """Chamado ao salvar: marca a nota para subir no próximo sync."""
    if not fb_is_real_user() or not filepath:
        return None  # modo local puro: não cria sidecar
    user = fb_user()
    meta = load_sidecar(filepath) or {
        "id": uuid.uuid4().hex, "workspace_id": user["workspace_id"],
        "owner_uid": user["uid"], "deleted": False,
    }
    meta.setdefault("workspace_id", user["workspace_id"])
    meta.setdefault("owner_uid", user["uid"])
    meta["updated_at"] = time.time()
    meta["dirty"] = True
    save_sidecar(filepath, meta)
    return meta

# ─── Empurrar / puxar / sincronizar ──────────────────────────────────────────
def fb_push_note(db, filepath):
    meta = load_sidecar(filepath)
    if not meta:
        return False
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception:
        return False
    marks = load_marks(filepath)
    db.collection("notes").document(meta["id"]).set({
        "filename":     os.path.basename(filepath),
        "title":        os.path.basename(filepath),
        "content":      content,
        "marks":        {str(k): v for k, v in marks.items()},
        "workspace_id": meta["workspace_id"],
        "owner_uid":    meta["owner_uid"],
        "updated_at":   meta["updated_at"],
        "deleted":      meta.get("deleted", False),
    })
    meta["dirty"] = False
    save_sidecar(filepath, meta)
    return True

def _norm_ts(v):
    """Converte timestamp do Firestore (ou epoch) em float comparável."""
    if hasattr(v, "timestamp"):
        try:
            return v.timestamp()
        except Exception:
            return 0.0
    try:
        return float(v)
    except Exception:
        return 0.0

def _write_remote_to_local(fp, data, nid, wid):
    with open(fp, "w", encoding="utf-8") as f:
        f.write(data.get("content", ""))
    marks = {}
    for k, v in (data.get("marks") or {}).items():
        try:
            marks[int(k)] = v
        except Exception:
            pass
    save_marks(fp, marks)
    save_sidecar(fp, {"id": nid, "workspace_id": wid,
                      "owner_uid": data.get("owner_uid", ""),
                      "updated_at": _norm_ts(data.get("updated_at", 0)),
                      "dirty": False, "deleted": False})

def _delete_local(fp):
    for p in (fp, marks_path(fp), sidecar_path(fp)):
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

def fb_pull_notes(db, user, folder):
    wid = user.get("workspace_id")
    if not wid:
        return 0
    local_by_id = {}
    for fn in os.listdir(folder):
        if fn.endswith(".txt"):
            fp = os.path.join(folder, fn)
            m = load_sidecar(fp)
            if m and m.get("id"):
                local_by_id[m["id"]] = (fp, m)
    pulled = 0
    for d in _where(db.collection("notes"), "workspace_id", "==", wid).stream():
        data = d.to_dict()
        nid  = d.id
        if data.get("deleted"):
            if nid in local_by_id:
                _delete_local(local_by_id[nid][0])
            continue
        remote_ts = _norm_ts(data.get("updated_at", 0))
        if nid in local_by_id:
            fp, m = local_by_id[nid]
            if m.get("dirty"):
                continue  # mudança local pendente → resolvida no push
            if remote_ts > m.get("updated_at", 0):
                _write_remote_to_local(fp, data, nid, wid)
                pulled += 1
        else:
            fname = data.get("filename") or f"DOC_remote_{nid[:8]}.txt"
            fp = os.path.join(folder, fname)
            if os.path.exists(fp):
                fp = os.path.join(folder, f"{nid[:8]}_{fname}")
            _write_remote_to_local(fp, data, nid, wid)
            pulled += 1
    return pulled

# ─── Tombstones (exclusões feitas offline) ───────────────────────────────────
def load_tombstones():
    try:
        with open(TOMBSTONE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def add_tombstone(note_id, workspace_id):
    os.makedirs(SYNC_DIR, exist_ok=True)
    t = load_tombstones()
    t[note_id] = workspace_id
    try:
        with open(TOMBSTONE_FILE, "w") as f:
            json.dump(t, f)
    except Exception:
        pass

def flush_tombstones(db):
    t = load_tombstones()
    if not t:
        return
    for nid in list(t.keys()):
        try:
            db.collection("notes").document(nid).set(
                {"deleted": True, "updated_at": time.time()}, merge=True)
            del t[nid]
        except Exception:
            pass
    try:
        with open(TOMBSTONE_FILE, "w") as f:
            json.dump(t, f)
    except Exception:
        pass

def sync_notes(folder):
    """Sincroniza a pasta com o Firestore. Retorna (enviadas, recebidas, status)."""
    db, user = fb_db(), fb_user()
    if db is None or not fb_is_real_user():
        return (0, 0, "offline")
    if not check_online():
        return (0, 0, "offline")
    pushed = 0
    try:
        flush_tombstones(db)
        for fn in os.listdir(folder):
            if fn.endswith(".txt"):
                fp = os.path.join(folder, fn)
                meta = ensure_sidecar(fp, user["workspace_id"], user["uid"])
                if meta.get("dirty"):
                    if fb_push_note(db, fp):
                        pushed += 1
        pulled = fb_pull_notes(db, user, folder)
        return (pushed, pulled, "ok")
    except Exception as e:
        return (pushed, 0, _friendly_fb_error(e))

def push_note_if_online(filepath):
    """Best-effort: empurra uma nota logo após salvar, se online."""
    if not fb_is_real_user() or not fb_is_online():
        return
    try:
        fb_push_note(fb_db(), filepath)
    except Exception:
        pass  # fica dirty, sobe no próximo :sync

def fb_status_tag():
    """Indicador curto de usuário/conexão para as barras de status."""
    if not fb_is_real_user():
        return ""
    dot = "●" if fb_is_online() else "○"
    u = fb_user()
    ws = u.get("workspace_name") or u.get("workspace_id", "")
    return f"{dot} {ws}/{u.get('email','')}"

def active_folder(cfg):
    """Pasta local das notas, isolada por workspace quando há login.

    - Usuário real  → ~/Desktop/<pasta>/<WORKSPACE>/  (notas separadas por ws)
    - Modo local    → ~/Desktop/<pasta>/               (comportamento clássico)
    """
    base = os.path.expanduser(f"~/Desktop/{cfg.get('folder_name','GetexDocs')}")
    u = fb_user()
    if u and u.get("uid") != "local" and u.get("workspace_id"):
        path = os.path.join(base, u["workspace_id"])
    else:
        path = base
    os.makedirs(path, exist_ok=True)
    return path

# ═══════════════════════════════════════════════════════════════════════════════
# EDITOR
# ═══════════════════════════════════════════════════════════════════════════════
class GetexEditor:
    MODE_CMD = "COMMAND"
    MODE_INS = "INSERT"

    def __init__(self, stdscr, cfg, initial_lines=None, source_file=None, title=None):
        self.stdscr    = stdscr
        self.cfg       = cfg
        self.mode      = self.MODE_CMD
        self.lines     = list(initial_lines) if initial_lines else [""]
        self.row       = 0
        self.col       = 0
        self.scroll    = 0
        self.status    = ""
        self.cmd_buf   = ""
        # source_file: caminho do arquivo que foi aberto (None = nova sessão)
        self.source_file = source_file
        # title: nome opcional dado pelo usuário (via CLI ou :rename)
        self.title = title if title else ""

        # ── Seleção ──────────────────────────────────────────────────────────
        # âncora: onde a seleção começou
        self.sel_anchor_row = None   # None = sem seleção ativa
        self.sel_anchor_col = None
        # clipboard interno (lista de strings = linhas)
        self.clipboard: list[str] = []

        # marks: dict {line_index: "green"|"red"}
        self.marks: dict = {}
        # carrega marcações persistidas se houver arquivo fonte
        if source_file:
            self.marks = load_marks(source_file)

        curses.set_escdelay(25)
        init_colors(self.cfg)
        self.stdscr.bkgd(' ', curses.color_pair(16))
        curses.curs_set(1)
        self.stdscr.keypad(True)

    # ── Helpers de seleção ────────────────────────────────────────────────────
    def has_sel(self):
        return self.sel_anchor_row is not None

    def sel_range(self):
        """Retorna (sr, sc, er, ec) normalizado."""
        return sel_ordered(
            self.sel_anchor_row, self.sel_anchor_col,
            self.row, self.col
        )

    def clear_sel(self):
        self.sel_anchor_row = None
        self.sel_anchor_col = None

    def start_sel(self):
        """Fixa âncora na posição atual (se ainda não há seleção)."""
        if not self.has_sel():
            self.sel_anchor_row = self.row
            self.sel_anchor_col = self.col

    def in_selection(self, r, c):
        """True se a posição (r,c) está dentro da seleção atual."""
        if not self.has_sel():
            return False
        sr, sc, er, ec = self.sel_range()
        if r < sr or r > er:
            return False
        if r == sr and c < sc:
            return False
        if r == er and c >= ec:
            return False
        return True

    # ── Reindexação de marcações ────────────────────────────────────────────────
    # As marcações (F2/F3) são guardadas por índice de linha. Sempre que linhas
    # são inseridas ou removidas, os índices abaixo do ponto de edição precisam
    # ser deslocados para que a marca continue "grudada" no conteúdo da linha.
    def _shift_marks_for_insert(self, at_row, count=1):
        """count linhas foram inseridas em at_row → marcas em idx >= at_row sobem +count."""
        if not self.marks or count <= 0:
            return
        self.marks = {
            (idx + count if idx >= at_row else idx): color
            for idx, color in self.marks.items()
        }

    def _shift_marks_for_delete(self, at_row, count=1):
        """count linhas a partir de at_row foram removidas → suas marcas somem; abaixo desce -count."""
        if not self.marks or count <= 0:
            return
        new_marks = {}
        for idx, color in self.marks.items():
            if idx < at_row:
                new_marks[idx] = color
            elif idx >= at_row + count:
                new_marks[idx - count] = color
            # at_row <= idx < at_row+count → linha removida, descarta a marca
        self.marks = new_marks

    # ── Operações de clipboard ────────────────────────────────────────────────
    def copy_sel(self):
        if not self.has_sel():
            return
        sr, sc, er, ec = self.sel_range()
        self.clipboard = extract_selection(self.lines, sr, sc, er, ec)
        self.status = f"✓ {sum(len(l) for l in self.clipboard)} chars copiados"

    def cut_sel(self):
        if not self.has_sel():
            return
        sr, sc, er, ec = self.sel_range()
        self.clipboard = extract_selection(self.lines, sr, sc, er, ec)
        self.lines, self.row, self.col = delete_selection(self.lines, sr, sc, er, ec)
        self._shift_marks_for_delete(sr + 1, er - sr)  # linhas sr+1..er foram fundidas em sr
        self.clear_sel()
        self.status = f"✓ Recortado para clipboard"

    def delete_sel(self):
        if not self.has_sel():
            return
        sr, sc, er, ec = self.sel_range()
        self.lines, self.row, self.col = delete_selection(self.lines, sr, sc, er, ec)
        self._shift_marks_for_delete(sr + 1, er - sr)  # linhas sr+1..er foram fundidas em sr
        self.clear_sel()

    def paste(self):
        if not self.clipboard:
            self.status = "[!] Clipboard vazio"
            return
        # Se há seleção, apaga primeiro
        if self.has_sel():
            self.delete_sel()
        if len(self.clipboard) == 1:
            ln = self.lines[self.row]
            self.lines[self.row] = ln[:self.col] + self.clipboard[0] + ln[self.col:]
            self.col += len(self.clipboard[0])
        else:
            self._shift_marks_for_insert(self.row + 1, len(self.clipboard) - 1)
            ln    = self.lines[self.row]
            head  = ln[:self.col] + self.clipboard[0]
            tail  = self.clipboard[-1] + ln[self.col:]
            mid   = self.clipboard[1:-1]
            new_lines = (
                self.lines[:self.row]
                + [head]
                + mid
                + [tail]
                + self.lines[self.row+1:]
            )
            self.lines = new_lines
            self.row  += len(self.clipboard) - 1
            self.col   = len(self.clipboard[-1])
        self.status = "✓ Colado"

    # ── Movimento de palavra ──────────────────────────────────────────────────
    def word_left(self):
        """Move cursor uma palavra para a esquerda."""
        if self.col > 0:
            ln = self.lines[self.row]
            c  = self.col - 1
            while c > 0 and not ln[c].isalnum():
                c -= 1
            while c > 0 and ln[c].isalnum():
                c -= 1
            self.col = c
        elif self.row > 0:
            self.row -= 1
            self.col  = len(self.lines[self.row])

    def word_right(self):
        """Move cursor uma palavra para a direita."""
        ln = self.lines[self.row]
        c  = self.col
        if c < len(ln):
            while c < len(ln) and not ln[c].isalnum():
                c += 1
            while c < len(ln) and ln[c].isalnum():
                c += 1
            self.col = c
        elif self.row < len(self.lines) - 1:
            self.row += 1
            self.col  = 0

    # ── Render ────────────────────────────────────────────────────────────────
    def render(self):
        self.stdscr.erase()
        h, w   = self.stdscr.getmaxyx()
        text_h = h - 2
        gutter = 5

        sel_pair = curses.color_pair(10) | curses.A_BOLD

        for sr in range(text_h):
            br = sr + self.scroll
            if br < len(self.lines):
                # cor de marcação da linha (None = sem marca)
                mark = self.marks.get(br)
                if mark == "green":
                    num_pair  = curses.color_pair(14) | curses.A_BOLD
                    line_pair = curses.color_pair(12)
                elif mark == "red":
                    num_pair  = curses.color_pair(15) | curses.A_BOLD
                    line_pair = curses.color_pair(13)
                else:
                    num_pair  = curses.color_pair(4)
                    line_pair = curses.color_pair(16)
                # número de linha
                try:
                    self.stdscr.addstr(sr, 0, f"{br+1:>4} ", num_pair)
                except curses.error:
                    pass
                # conteúdo da linha, char a char para highlight de seleção ou marcação
                ln   = self.lines[br]
                disp = ln[:w - gutter - 1]
                for ci, ch in enumerate(disp):
                    if self.in_selection(br, ci):
                        attr = sel_pair
                    else:
                        attr = line_pair
                    try:
                        self.stdscr.addch(sr, gutter + ci, ch, attr)
                    except curses.error:
                        pass
                # espaço após fim da linha
                end_attr = sel_pair if self.in_selection(br, len(ln)) else line_pair
                # preenche o resto da linha com a cor de marcação
                rest = w - gutter - len(disp) - 1
                if rest > 0 and line_pair:
                    try:
                        self.stdscr.addstr(sr, gutter + len(disp), " " * rest, line_pair)
                    except curses.error:
                        pass
                elif self.in_selection(br, len(ln)):
                    try:
                        self.stdscr.addch(sr, gutter + len(disp), " ", sel_pair)
                    except curses.error:
                        pass
            else:
                try:
                    self.stdscr.addstr(sr, 0, "~", curses.color_pair(4))
                except curses.error:
                    pass

        # Status bar
        sel_info = ""
        if self.has_sel():
            sr2, sc2, er2, ec2 = self.sel_range()
            nlines = er2 - sr2 + 1
            sel_info = f"  [SEL {nlines}L]"

        label = f" {self.mode} "
        pair  = curses.color_pair(1) if self.mode == self.MODE_INS else curses.color_pair(2)
        info  = f"  Ln {self.row+1}, Col {self.col+1}  |  {len(self.lines)} linhas{sel_info}"
        base  = self.title if self.title else "getex"
        utag  = fb_status_tag()
        rtag  = f"  {base} · {utag}  " if utag else f"  {base}  "
        pad   = w - len(label) - len(info) - len(rtag)
        sline = label + info + " " * max(0, pad) + rtag
        try:
            self.stdscr.addstr(h - 2, 0, sline[:w], pair)
        except curses.error:
            pass

        # Hint / cmd line
        if self.mode == self.MODE_CMD:
            if self.cmd_buf:
                disp_cmd = f":{self.cmd_buf}"
            elif self.status:
                disp_cmd = self.status
            else:
                disp_cmd = "  'i' inserir | F2/2 ● | F3/3 ● | ':help' | ':config' | ':sync' | ':' cmd"
            cpair = curses.color_pair(3) if self.status.startswith("[") else curses.color_pair(5)
        else:
            if self.has_sel():
                disp_cmd = "  SELEÇÃO  Ctrl+C copiar | Ctrl+K recortar | Ctrl+V colar | Del apagar | Esc cancela"
            else:
                disp_cmd = self.status or "  -- INSERÇÃO --  Esc → cmd | Ctrl+A selecionar tudo"
            cpair = curses.color_pair(6)
        try:
            self.stdscr.addstr(h - 1, 0, disp_cmd[:w].ljust(w - 1), cpair)
        except curses.error:
            pass

        # Cursor
        scr  = self.row - self.scroll
        scol = self.col + gutter
        try:
            self.stdscr.move(
                max(0, min(scr, text_h - 1)),
                max(0, min(scol, w - 1)),
            )
        except curses.error:
            pass
        self.stdscr.refresh()

    # ── Scroll ────────────────────────────────────────────────────────────────
    def sync_scroll(self):
        h, _ = self.stdscr.getmaxyx()
        th   = h - 2
        if self.row < self.scroll:
            self.scroll = self.row
        elif self.row >= self.scroll + th:
            self.scroll = self.row - th + 1

    # ── Executar comando ──────────────────────────────────────────────────────
    def run_cmd(self, cmd):
        cmd = cmd.strip()
        if cmd == "theme":
            original_theme = self.cfg.get("theme", "default")
            tm = ThemeMenu(self.stdscr, self.cfg)
            if not tm.run():
                self.cfg["theme"] = original_theme
            init_colors(self.cfg)
            self.stdscr.bkgd(' ', curses.color_pair(16))
            self.status = f"✓ Tema: {self.cfg.get('theme', 'default').capitalize()}"
            return "STAY", None
        if cmd in ("help", "h", "ajuda"):
            self.show_help_screen()
            return "STAY", None
        if cmd in ("config", "cfg", "settings"):
            cm = ConfigMenu(self.stdscr, self.cfg)
            cm.run()
            init_colors(self.cfg)
            self.stdscr.bkgd(' ', curses.color_pair(16))
            curses.curs_set(1)
            self.status = "✓ Configurações atualizadas"
            return "STAY", None
        if cmd in ("account", "conta", "passwd", "senha"):
            if not fb_is_real_user():
                self.status = "[!] Disponível apenas com login Firebase"
                return "STAY", None
            start = "passwd" if cmd in ("passwd", "senha") else "menu"
            am = AccountMenu(self.stdscr, self.cfg, start=start)
            am.run()
            init_colors(self.cfg)
            self.stdscr.bkgd(' ', curses.color_pair(16))
            curses.curs_set(1)
            self.status = am.status or "✓ Conta"
            return "STAY", None
        if cmd == "wq":
            if self.source_file:
                path = save_document(self.lines, self.cfg,
                                     filepath=self.source_file, overwrite=True)
            else:
                path = save_document(self.lines, self.cfg, title=self.title or None)
                self.source_file = path  # registra para salvar marks
            save_marks(self.source_file, self.marks)
            mark_note_dirty(self.source_file)
            push_note_if_online(self.source_file)
            tag = "  ☁" if fb_is_online() else ""
            return "QUIT", f"✓ Salvo em {path}{tag}"
        if cmd in ("sync", "s"):
            folder = active_folder(self.cfg)
            if not fb_is_real_user():
                self.status = "[!] Sem login Firebase — modo local"
                return "STAY", None
            self.status = "  ⏳ Sincronizando..."
            self.render()
            pushed, pulled, st = sync_notes(folder)
            if st == "offline":
                self.status = "[!] Offline — nada sincronizado"
            elif st == "ok":
                self.status = f"✓ Sincronizado: {pushed}↑ {pulled}↓"
            else:
                self.status = f"[!] {st}"
            return "STAY", None
        if cmd == "logout":
            clear_session()
            return "QUIT", "✓ Sessão encerrada. Reabra o getex para entrar."
        if cmd in ("whoami", "me"):
            if fb_is_real_user():
                u = fb_user()
                net = "online" if fb_is_online() else "offline"
                ws = u.get('workspace_name') or u.get('workspace_id','')
                self.status = f"  workspace: {ws} · {u.get('email')} · {net}"
            else:
                self.status = "  modo local (sem login Firebase)"
            return "STAY", None
        if cmd == "q!":
            return "QUIT", ""
        if cmd == "q":
            if any(l.strip() for l in self.lines):
                self.status = "[!] Use :wq para salvar ou :q! para descartar"
                return "STAY", None
            return "QUIT", ""
        if cmd == "ai":
            ctx = "\n".join(l for l in self.lines if l.strip())
            if not ctx:
                self.status = "[!] Buffer vazio"
                return "STAY", None
            self.status = "  ⏳ Aguardando IA..."
            self.render()
            resp  = call_ai(ctx[-20*80:], self.cfg)
            block = (
                ["", "── Resposta IA ──────────────────────────────"]
                + resp.splitlines()
                + ["─" * 45, ""]
            )
            ins = self.row + 1
            for i, rl in enumerate(block):
                self.lines.insert(ins + i, rl)
            self.row   = ins + len(block) - 1
            self.col   = 0
            self.status = "✓ Resposta inserida"
            return "STAY", None
        if cmd.startswith("set key "):
            self.cfg["api_key"] = cmd[8:].strip()
            save_config(self.cfg)
            self.status = "✓ Chave salva"
            return "STAY", None
        if cmd.startswith("rename ") or cmd.startswith("title "):
            # :rename Meu Titulo  ou  :title Meu Titulo
            new_title = cmd.split(None, 1)[1].strip()
            if self.source_file:
                # renomeia o arquivo físico já existente
                folder   = os.path.dirname(self.source_file)
                now      = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
                new_name = f"DOC_{now}_{slugify(new_title)}.txt"
                new_path = os.path.join(folder, new_name)
                os.rename(self.source_file, new_path)
                self.source_file = new_path
                self.title       = new_title
                self.status      = f"✓ Renomeado para {new_name}"
            else:
                # ainda não salvo — só guarda o título para usar no :wq
                self.title  = new_title
                self.status = f"✓ Título definido: {new_title}"
            return "STAY", None
        self.status = f"[!] Comando desconhecido: :{cmd}"
        return "STAY", None

    # ── Tela de ajuda ( :help ) ────────────────────────────────────────────────
    def show_help_screen(self):
        """Overlay rolável com a lista completa de comandos do getex."""
        help_lines = [
            "",
            "  ╔══════════════════════════════════════════════════════╗",
            "  ║              GETEX — Lista de Comandos               ║",
            "  ╚══════════════════════════════════════════════════════╝",
            "",
            "[ Modo de Comando ]  (pressione Esc para ativar)",
            "  i               Inserir na posição do cursor",
            "  a               Inserir após o cursor",
            "  o               Abrir nova linha abaixo e inserir",
            "  h j k l         Mover cursor (←  ↓  ↑  →)",
            "  ← ↑ → ↓         Mover cursor",
            "  g / G           Ir para a primeira / última linha",
            "  dd              Apagar a linha atual",
            "  F2  ou  2       Marcar/desmarcar a linha em verde ●",
            "  F3  ou  3       Marcar/desmarcar a linha em vermelho ●",
            "                  (use 2/3 no Mac, onde F2/F3 pedem Fn)",
            "  :               Abrir a barra de comandos",
            "",
            "[ Barra de Comandos ( : ) ]",
            "  :wq             Salvar o documento e sair",
            "  :q              Sair (bloqueia se houver texto não salvo)",
            "  :q!             Sair descartando as alterações",
            "  :ai             Enviar o texto para a IA continuar/responder",
            "  :config         Abrir as configurações do sistema",
            "  :theme          Trocar o tema de cores",
            "  :rename <nome>  Renomear o arquivo / definir título",
            "  :title <nome>   (igual a :rename)",
            "  :set key <ch>   Definir a chave de API de IA",
            "  :sync           Sincronizar as notas com o Firebase",
            "  :account        Conta: trocar senha / ver/remover membros",
            "  :passwd         Trocar a sua senha",
            "  :whoami         Mostrar usuário/workspace e status de conexão",
            "  :logout         Encerrar a sessão (pede login na próxima vez)",
            "  :help           Mostrar esta tela de ajuda",
            "",
            "[ Modo de Inserção ]",
            "  Esc             Voltar ao modo de comando",
            "  Ctrl+A          Selecionar todo o texto",
            "  Ctrl+C          Copiar a seleção",
            "  Ctrl+K          Recortar (Ctrl+X é usado pelo terminal)",
            "  Ctrl+V          Colar",
            "  Shift+setas     Selecionar texto",
            "  Ctrl+Shift+←/→  Selecionar palavra inteira",
            "  Shift+Home/End  Selecionar até o início/fim da linha",
            "  Del / Backspace Apagar a seleção ou um caractere",
            "",
            "[ Navegador de Arquivos ]  (getex get all)",
            "  ↑ ↓  /  j k     Navegar pela lista de arquivos",
            "  n               Criar uma nova nota (pede o nome e abre o editor)",
            "  Enter           Abrir o arquivo no editor",
            "  c               Mostrar/ocultar o calendário",
            "  ← →  /  h l     Trocar de dia (com calendário ativo)",
            "  r               Reorganizar o arquivo com IA",
            "  d               Deletar o arquivo selecionado",
            "  PgUp / PgDn     Rolar o preview",
            "  q / Esc         Sair do navegador",
            "",
        ]
        curses.curs_set(0)
        top = 0
        while True:
            self.stdscr.erase()
            h, w = self.stdscr.getmaxyx()
            view_h  = h - 1
            max_top = max(0, len(help_lines) - view_h)
            top = max(0, min(top, max_top))
            for i in range(view_h):
                li = top + i
                if li >= len(help_lines):
                    break
                line = help_lines[li]
                if line.startswith("["):
                    pair = curses.color_pair(8) | curses.A_BOLD
                elif any(c in line for c in ("╔", "║", "╚")):
                    pair = curses.color_pair(6) | curses.A_BOLD
                else:
                    pair = curses.color_pair(16)
                try:
                    self.stdscr.addstr(i, 0, line[:w-1], pair)
                except curses.error:
                    pass
            footer = " ↑↓ rolar │ PgUp/PgDn │ q/Esc/Enter fechar "
            if max_top > 0:
                footer += f"│ {top+1}-{min(top+view_h, len(help_lines))}/{len(help_lines)} "
            try:
                self.stdscr.addstr(h - 1, 0, footer[:w].ljust(w - 1), curses.color_pair(5))
            except curses.error:
                pass
            self.stdscr.refresh()
            k = self.stdscr.get_wch()
            if is_esc(k) or is_enter(k) or k in ("q", "Q"):
                break
            elif k in (curses.KEY_UP, "k"):
                top -= 1
            elif k in (curses.KEY_DOWN, "j"):
                top += 1
            elif k == curses.KEY_PPAGE:
                top -= view_h
            elif k == curses.KEY_NPAGE:
                top += view_h
            elif k == curses.KEY_HOME:
                top = 0
            elif k == curses.KEY_END:
                top = max_top
        curses.curs_set(1)

    def capture_command(self):
        self.cmd_buf = ""
        while True:
            self.render()
            k = self.stdscr.get_wch()
            if is_enter(k):
                result, msg = self.run_cmd(self.cmd_buf)
                self.cmd_buf = ""
                if result == "QUIT":
                    return msg
                return None
            elif is_backspace(k):
                if self.cmd_buf:
                    self.cmd_buf = self.cmd_buf[:-1]
                else:
                    self.cmd_buf = ""
                    return None
            elif is_esc(k):
                self.cmd_buf = ""
                return None
            elif isinstance(k, str) and ord(k) >= 32:
                self.cmd_buf += k

    # ── Loop principal ────────────────────────────────────────────────────────
    def run(self):
        while True:
            self.sync_scroll()
            self.render()
            try:
                k = self.stdscr.get_wch()
            except curses.error:
                continue

            # ══ MODO INSERÇÃO ══════════════════════════════════════════════
            if self.mode == self.MODE_INS:

                # ── ESC: volta ao modo comando, cancela seleção ───────────
                if is_esc(k):
                    self.mode    = self.MODE_CMD
                    self.cmd_buf = ""
                    self.col     = max(0, self.col - 1)
                    self.clear_sel()
                    self.status  = ""
                    continue

                # ── Ctrl+A: selecionar tudo ───────────────────────────────
                if k == "\x01":
                    self.sel_anchor_row = 0
                    self.sel_anchor_col = 0
                    self.row = len(self.lines) - 1
                    self.col = len(self.lines[self.row])
                    self.status = "✓ Tudo selecionado"
                    continue

                # ── Ctrl+C: copiar ────────────────────────────────────────
                if k == "\x03":
                    if self.has_sel():
                        self.copy_sel()
                    continue

                # ── Ctrl+K: recortar ─────────────────────────────────────
                # (Ctrl+X foi removido: o terminal intercepta antes do curses)
                if k == "\x0b":
                    if self.has_sel():
                        self.cut_sel()
                    continue

                # ── Ctrl+V: colar ─────────────────────────────────────────
                if k == "\x16":
                    self.paste()
                    continue

                # ── Delete com seleção ────────────────────────────────────
                if k == curses.KEY_DC:
                    if self.has_sel():
                        self.delete_sel()
                        self.status = ""
                    else:
                        ln = self.lines[self.row]
                        if self.col < len(ln):
                            self.lines[self.row] = ln[:self.col] + ln[self.col+1:]
                        elif self.row < len(self.lines) - 1:
                            self.lines[self.row] = ln + self.lines[self.row+1]
                            self.lines.pop(self.row+1)
                            self._shift_marks_for_delete(self.row + 1, 1)
                    continue

                # ── Backspace com seleção ─────────────────────────────────
                if is_backspace(k):
                    self.status = ""
                    if self.has_sel():
                        self.delete_sel()
                    elif self.col > 0:
                        ln = self.lines[self.row]
                        self.lines[self.row] = ln[:self.col-1] + ln[self.col:]
                        self.col -= 1
                    elif self.row > 0:
                        prev = self.lines[self.row - 1]
                        self.col = len(prev)
                        self.lines[self.row-1] = prev + self.lines[self.row]
                        self.lines.pop(self.row)
                        self._shift_marks_for_delete(self.row, 1)
                        self.row -= 1
                    continue

                # ── Enter: cancela seleção e insere nova linha ────────────
                if is_enter(k):
                    if self.has_sel():
                        self.delete_sel()
                    self._shift_marks_for_insert(self.row + 1, 1)
                    ln = self.lines[self.row]
                    self.lines[self.row] = ln[:self.col]
                    self.lines.insert(self.row + 1, ln[self.col:])
                    self.row += 1
                    self.col  = 0
                    self.clear_sel()
                    continue

                # ─────────────────────────────────────────────────────────
                # NAVEGAÇÃO COM SHIFT = SELEÇÃO
                # curses reporta Shift+seta como KEY_SR/SF/SLEFT/SRIGHT e
                # Ctrl+Shift como sequências de escape específicas do terminal.
                # Mapeamos os códigos mais comuns aqui.
                # ─────────────────────────────────────────────────────────

                # ── Shift+↑ ───────────────────────────────────────────────
                if k == curses.KEY_SR:          # Shift+Up
                    self.start_sel()
                    if self.row > 0:
                        self.row -= 1
                        self.col = min(self.col, len(self.lines[self.row]))
                    continue

                # ── Shift+↓ ───────────────────────────────────────────────
                if k == curses.KEY_SF:          # Shift+Down
                    self.start_sel()
                    if self.row < len(self.lines) - 1:
                        self.row += 1
                        self.col = min(self.col, len(self.lines[self.row]))
                    continue

                # ── Shift+← ───────────────────────────────────────────────
                if k == curses.KEY_SLEFT:
                    self.start_sel()
                    if self.col > 0:
                        self.col -= 1
                    elif self.row > 0:
                        self.row -= 1
                        self.col = len(self.lines[self.row])
                    continue

                # ── Shift+→ ───────────────────────────────────────────────
                if k == curses.KEY_SRIGHT:
                    self.start_sel()
                    if self.col < len(self.lines[self.row]):
                        self.col += 1
                    elif self.row < len(self.lines) - 1:
                        self.row += 1
                        self.col = 0
                    continue

                # ── Shift+Home ────────────────────────────────────────────
                if k == curses.KEY_SHOME:
                    self.start_sel()
                    self.col = 0
                    continue

                # ── Shift+End ─────────────────────────────────────────────
                if k == curses.KEY_SEND:
                    self.start_sel()
                    self.col = len(self.lines[self.row])
                    continue

                # ── Ctrl+Shift+← (word left + seleção) ───────────────────
                # Terminais enviam \x1b[1;6D  ou  \x1b[1;2D dependendo do emulador
                if k == "\x1b":
                    # lemos o resto da sequência com timeout curto
                    self.stdscr.nodelay(True)
                    seq = ""
                    while True:
                        try:
                            nk = self.stdscr.get_wch()
                            if isinstance(nk, str):
                                seq += nk
                            else:
                                break
                        except curses.error:
                            break
                    self.stdscr.nodelay(False)

                    # Ctrl+Shift+← / → / ↑ / ↓
                    if seq in ("[1;6D", "[1;2D"):   # Ctrl+Shift+←
                        self.start_sel()
                        self.word_left()
                    elif seq in ("[1;6C", "[1;2C"):  # Ctrl+Shift+→
                        self.start_sel()
                        self.word_right()
                    elif seq in ("[1;6A", "[1;2A"):  # Ctrl+Shift+↑
                        self.start_sel()
                        if self.row > 0:
                            self.sel_anchor_col = 0
                            self.row -= 1
                            self.col = 0
                    elif seq in ("[1;6B", "[1;2B"):  # Ctrl+Shift+↓
                        self.start_sel()
                        if self.row < len(self.lines) - 1:
                            self.sel_anchor_col = len(self.lines[self.sel_anchor_row])
                            self.row += 1
                            self.col = len(self.lines[self.row])
                    # Ctrl+← / Ctrl+→ (sem shift — só move, não seleciona)
                    elif seq in ("[1;5D", "[5D", "b"):
                        self.clear_sel()
                        self.word_left()
                    elif seq in ("[1;5C", "[5C", "f"):
                        self.clear_sel()
                        self.word_right()
                    # Qualquer outra coisa: ignora
                    continue

                # ── Setas normais: movem cursor, CANCELAM seleção ─────────
                if k == curses.KEY_UP:
                    self.clear_sel()
                    if self.row > 0:
                        self.row -= 1
                        self.col = min(self.col, len(self.lines[self.row]))
                    continue
                if k == curses.KEY_DOWN:
                    self.clear_sel()
                    if self.row < len(self.lines) - 1:
                        self.row += 1
                        self.col = min(self.col, len(self.lines[self.row]))
                    continue
                if k == curses.KEY_LEFT:
                    self.clear_sel()
                    if self.col > 0:
                        self.col -= 1
                    elif self.row > 0:
                        self.row -= 1
                        self.col = len(self.lines[self.row])
                    continue
                if k == curses.KEY_RIGHT:
                    self.clear_sel()
                    if self.col < len(self.lines[self.row]):
                        self.col += 1
                    elif self.row < len(self.lines) - 1:
                        self.row += 1
                        self.col = 0
                    continue
                if k == curses.KEY_HOME:
                    self.clear_sel()
                    self.col = 0
                    continue
                if k == curses.KEY_END:
                    self.clear_sel()
                    self.col = len(self.lines[self.row])
                    continue

                # ── Caractere normal ──────────────────────────────────────
                if isinstance(k, str) and len(k) == 1 and ord(k) >= 32:
                    # Se havia seleção, apaga antes de digitar
                    if self.has_sel():
                        self.delete_sel()
                    self.status = ""
                    ln = self.lines[self.row]
                    self.lines[self.row] = ln[:self.col] + k + ln[self.col:]
                    self.col += 1

            # ══ MODO COMANDO ═══════════════════════════════════════════════
            else:
                self.status = ""

                if k == "i":
                    self.mode = self.MODE_INS
                elif k == "a":
                    self.mode = self.MODE_INS
                    if self.col < len(self.lines[self.row]):
                        self.col += 1
                elif k == "o":
                    self._shift_marks_for_insert(self.row + 1, 1)
                    self.lines.insert(self.row + 1, "")
                    self.row += 1
                    self.col  = 0
                    self.mode = self.MODE_INS
                elif k == "G":
                    self.row = len(self.lines) - 1
                    self.col = len(self.lines[self.row])
                elif k == "g":
                    self.row = 0
                    self.col = 0
                elif k in (curses.KEY_UP, "k"):
                    if self.row > 0:
                        self.row -= 1
                        self.col = min(self.col, len(self.lines[self.row]))
                elif k in (curses.KEY_DOWN, "j"):
                    if self.row < len(self.lines) - 1:
                        self.row += 1
                        self.col = min(self.col, len(self.lines[self.row]))
                elif k in (curses.KEY_LEFT, "h"):
                    if self.col > 0:
                        self.col -= 1
                elif k in (curses.KEY_RIGHT, "l"):
                    if self.col < len(self.lines[self.row]):
                        self.col += 1
                elif k == ":":
                    result = self.capture_command()
                    if isinstance(result, str):
                        return result
                elif k == "d":
                    nk = self.stdscr.get_wch()
                    if nk == "d":
                        if len(self.lines) > 1:
                            self.lines.pop(self.row)
                            self._shift_marks_for_delete(self.row, 1)
                            self.row = min(self.row, len(self.lines) - 1)
                        else:
                            self.lines[0] = ""
                            self.marks.pop(0, None)
                        self.col = 0

                # ── F2 ou 2: marca verde / desmarca ───────────────────
                # ("2"/"3" são alternativas ao F2/F3 — no Mac as teclas de
                #  função muitas vezes exigem segurar Fn.)
                elif k == curses.KEY_F2 or k == "2":
                    if self.marks.get(self.row) == "green":
                        del self.marks[self.row]          # desmarca
                        self.status = "  Marcação removida"
                    else:
                        self.marks[self.row] = "green"    # marca verde
                        self.status = "  ● Linha marcada em verde"

                # ── F3 ou 3: marca vermelho / desmarca ────────────────
                elif k == curses.KEY_F3 or k == "3":
                    if self.marks.get(self.row) == "red":
                        del self.marks[self.row]          # desmarca
                        self.status = "  Marcação removida"
                    else:
                        self.marks[self.row] = "red"      # marca vermelha
                        self.status = "  ● Linha marcada em vermelho"


# ═══════════════════════════════════════════════════════════════════════════════
# NAVEGADOR DE ARQUIVOS  — getex get all
# ═══════════════════════════════════════════════════════════════════════════════
def list_docs(cfg):
    folder = active_folder(cfg)
    if not os.path.isdir(folder):
        return []
    files = []
    for fname in os.listdir(folder):
        if fname.endswith(".txt"):
            fpath = os.path.join(folder, fname)
            mtime = os.path.getmtime(fpath)
            files.append((fpath, fname, mtime))
    files.sort(key=lambda x: x[2], reverse=True)
    return files


class FilesBrowser:
    def __init__(self, stdscr, cfg):
        self.stdscr   = stdscr
        self.cfg      = cfg
        self.all_files = list_docs(cfg)
        
        self.show_calendar = False
        self.cal_date      = datetime.date.today()
        self.dates_with_files = set()
        
        self.files    = self.all_files
        self.sel      = 0
        self.v_scroll = 0
        self.p_scroll = 0
        
        self._update_dates_with_files()

        curses.set_escdelay(25)
        init_colors(self.cfg)
        self.stdscr.bkgd(' ', curses.color_pair(16))
        curses.curs_set(0)
        self.stdscr.keypad(True)

    def _update_dates_with_files(self):
        self.dates_with_files.clear()
        for f in self.all_files:
            dt = datetime.datetime.fromtimestamp(f[2]).date()
            self.dates_with_files.add(dt)

    def update_files_list(self):
        self.all_files = list_docs(self.cfg)
        self._update_dates_with_files()
        if self.show_calendar:
            self.files = [f for f in self.all_files if datetime.datetime.fromtimestamp(f[2]).date() == self.cal_date]
        else:
            self.files = self.all_files
        if self.sel >= len(self.files):
            self.sel = max(0, len(self.files) - 1)

    def load_preview(self):
        if not self.files:
            return [], {}
        fpath = self.files[self.sel][0]
        try:
            fsize = os.path.getsize(fpath)
            if fsize > MAX_FILE_SIZE:
                return [f"[Arquivo grande - abra para editar]"], {}
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
        except Exception as e:
            return [f"[Erro: {e}]"], {}
        marks = load_marks(fpath)
        return lines, marks

    def render(self):
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()

        folder = self.cfg.get("folder_name", "GetexDocs")
        utag   = fb_status_tag()
        usuffix = f"  │  {utag}" if utag else ""
        header = f"  getex get all  │  ~/Desktop/{folder}/  │  {len(self.files)} arquivo(s){usuffix}"
        try:
            self.stdscr.addstr(0, 0, header[:w].ljust(w - 1),
                               curses.color_pair(9) | curses.A_BOLD)
        except curses.error:
            pass

        content_h = h - 3
        list_w    = min(44, w // 2)
        prev_x    = list_w + 1
        prev_w    = w - prev_x - 1

        for row in range(1, h - 2):
            try:
                self.stdscr.addch(row, list_w, curses.ACS_VLINE, curses.color_pair(4))
            except curses.error:
                pass

        visible = content_h
        if self.sel < self.v_scroll:
            self.v_scroll = self.sel
        elif self.sel >= self.v_scroll + visible:
            self.v_scroll = self.sel - visible + 1

        for i in range(visible):
            fi  = i + self.v_scroll
            row = i + 1
            if fi >= len(self.files):
                break
            fpath, fname, mtime = self.files[fi]
            dt = datetime.datetime.fromtimestamp(mtime).strftime("%d/%m/%y %H:%M")
            try:
                size  = os.path.getsize(fpath)
                szstr = f"{size//1024}K" if size >= 1024 else f"{size}B"
            except Exception:
                szstr = "?"
            arrow  = "▶" if fi == self.sel else " "
            meta   = f" {dt} {szstr:>5} "
            max_fn = list_w - len(meta) - 3
            label  = fname if len(fname) <= max_fn else fname[:max_fn-1] + "…"
            line   = f" {arrow} {label}".ljust(list_w - len(meta)) + meta
            pair   = curses.color_pair(7) | curses.A_BOLD if fi == self.sel else curses.color_pair(16)
            try:
                self.stdscr.addstr(row, 0, line[:list_w], pair)
            except curses.error:
                pass

        prev_lines, prev_marks = self.load_preview()
        
        calendar.setfirstweekday(calendar.SUNDAY)
        cal_offset = 0
        if self.show_calendar:
            cal_offset = 9
            year = self.cal_date.year
            month = self.cal_date.month
            meses = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
            month_name = f"{meses[month]} {year}"
            
            try:
                self.stdscr.addstr(1, prev_x + 1, f" {month_name} ".center(20), curses.color_pair(8) | curses.A_BOLD)
                self.stdscr.addstr(2, prev_x + 1, "Do Se Te Qu Qu Se Sa".ljust(prev_w), curses.color_pair(4))
            except curses.error:
                pass
                
            weeks = calendar.monthcalendar(year, month)
            day_y = 3
            for week in weeks:
                if sum(week) == 0: continue
                for c_idx, day in enumerate(week):
                    if day == 0:
                        continue
                    day_date = datetime.date(year, month, day)
                    has_file = day_date in self.dates_with_files
                    is_selected = (day_date == self.cal_date)
                    
                    attr = curses.color_pair(16)
                    if is_selected:
                        attr = curses.color_pair(7) | curses.A_BOLD
                    elif has_file:
                        attr = curses.color_pair(12) | curses.A_BOLD
                        
                    x_pos = prev_x + 1 + c_idx * 3
                    try:
                        self.stdscr.addstr(day_y, x_pos, f"{day:>2}", attr)
                        if has_file:
                            self.stdscr.addstr(day_y, x_pos+2, "•", curses.color_pair(12) | curses.A_BOLD)
                    except curses.error:
                        pass
                day_y += 1

        if not self.files:
            try:
                self.stdscr.addstr(2 + cal_offset, prev_x + 2, "Nenhum arquivo encontrado.",
                                   curses.color_pair(3))
            except curses.error:
                pass
        else:
            fname = self.files[self.sel][1]
            try:
                self.stdscr.addstr(1 + cal_offset, prev_x + 1,
                    f" {fname} "[:prev_w], curses.color_pair(8) | curses.A_BOLD)
            except curses.error:
                pass
            for pi in range(content_h - 1 - cal_offset):
                li  = pi + self.p_scroll
                row = pi + 2 + cal_offset
                if li < len(prev_lines):
                    mark = prev_marks.get(li)
                    if mark == "green":
                        pair = curses.color_pair(12) | curses.A_BOLD
                    elif mark == "red":
                        pair = curses.color_pair(13) | curses.A_BOLD
                    else:
                        pair = curses.color_pair(16)
                    try:
                        line_text = prev_lines[li][:prev_w - 1]
                        if mark:
                            line_text = line_text.ljust(prev_w - 1)
                        self.stdscr.addstr(row, prev_x + 1, line_text, pair)
                    except curses.error:
                        pass

        hints = " ↑↓ navegar │ n nova │ c calendário │ r organizar IA │ s sync │ d deletar │ Enter editar │ q sair "
        try:
            self.stdscr.addstr(h - 2, 0, hints[:w].ljust(w - 1), curses.color_pair(5))
        except curses.error:
            pass
        if prev_lines:
            pinfo = f" preview linha {self.p_scroll+1}/{len(prev_lines)} "
            try:
                self.stdscr.addstr(h - 1, 0, pinfo[:w].ljust(w - 1), curses.color_pair(4))
            except curses.error:
                pass

        self.stdscr.refresh()

    def ai_organize(self):
        """
        Tecla r no navegador:
        - Lê o arquivo selecionado
        - Envia para a IA com prompt de organização
        - Sobrescreve o arquivo original com o resultado
        """
        if not self.files:
            return

        fpath, fname, _ = self.files[self.sel]

        # Lê o conteúdo original
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                original_text = f.read()
        except Exception as e:
            self._show_msg(f" [ERRO] Leitura: {e} ", curses.color_pair(3), wait=True)
            return

        if not original_text.strip():
            self._show_msg(" [!] Arquivo vazio — nada para organizar. ", curses.color_pair(3), wait=True)
            return

        # ── Feedback: limpa tela e mostra spinner ─────────────────────────
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        lines_msg = [
            "",
            "  ╔══════════════════════════════════════════╗",
            "  ║                                          ║",
            "  ║   ⏳  Organizando documento com IA...   ║",
            "  ║                                          ║",
            f"  ║   Arquivo: {fname[:30]:<30}  ║",
            "  ║                                          ║",
            "  ║   Aguarde — isso pode levar até 30s.    ║",
            "  ║                                          ║",
            "  ╚══════════════════════════════════════════╝",
        ]
        start_row = max(0, h // 2 - len(lines_msg) // 2)
        for i, ln in enumerate(lines_msg):
            try:
                self.stdscr.addstr(start_row + i, 0, ln[:w],
                                   curses.color_pair(11) | curses.A_BOLD)
            except curses.error:
                pass
        self.stdscr.refresh()

        # ── Chamada à IA ──────────────────────────────────────────────────
        organized = call_ai_organizer(original_text, self.cfg)

        if organized.startswith("[ERRO"):
            self._show_msg(f" {organized[:w-4]} ", curses.color_pair(3), wait=True)
            return

        # ── Sobrescreve o arquivo atual ───────────────────────────────────
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(organized)
        except Exception as e:
            self._show_msg(f" [ERRO] Salvar: {e} ", curses.color_pair(3), wait=True)
            return

        # ── Recarrega lista mantendo seleção no mesmo arquivo ─────────────
        cur_sel = self.sel
        self.update_files_list()
        self.sel      = min(cur_sel, max(0, len(self.files) - 1)) if self.files else 0
        self.p_scroll = 0

        # redesenha a lista
        self.render()

        self._show_msg(
            f" ✓  Documento organizado e salvo: {fname}  — pressione qualquer tecla ",
            curses.color_pair(11) | curses.A_BOLD,
            wait=True
        )

    def _show_msg(self, msg, pair, wait=False):
        """Exibe mensagem temporária na última linha do navegador."""
        h, w = self.stdscr.getmaxyx()
        try:
            self.stdscr.addstr(h - 1, 0, msg[:w].ljust(w - 1), pair)
        except curses.error:
            pass
        self.stdscr.refresh()
        if wait:
            self.stdscr.get_wch()  # aguarda qualquer tecla

    def confirm_delete(self, fname):
        h, w = self.stdscr.getmaxyx()
        msg  = f" Deletar '{fname}'? (s/n) "
        try:
            self.stdscr.addstr(h - 1, 0, msg[:w].ljust(w - 1),
                               curses.color_pair(3) | curses.A_BOLD)
        except curses.error:
            pass
        self.stdscr.refresh()
        while True:
            k = self.stdscr.get_wch()
            if k in ("s", "S", "y", "Y"):
                return True
            if k in ("n", "N") or is_esc(k):
                return False

    def open_file(self, fpath):
        try:
            fsize = os.path.getsize(fpath)
            if fsize > MAX_FILE_SIZE:
                initial = [f"[ERRO] Arquivo muito grande ({fsize//1024}KB). Máximo: {MAX_FILE_SIZE//1024}KB]"]
            else:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    initial = f.read().splitlines()
        except Exception as e:
            initial = [f"[Erro: {e}]"]

        def _edit(stdscr):
            # source_file=fpath garante que :wq sobrescreve em vez de fazer append
            ed = GetexEditor(stdscr, self.cfg, initial_lines=initial or [""], source_file=fpath)
            return ed.run()

        curses.wrapper(_edit)

    def prompt_new_name(self):
        """Pede o nome da nova nota na base da tela. Retorna str ou None (Esc)."""
        buf = ""
        curses.curs_set(1)
        while True:
            h, w = self.stdscr.getmaxyx()
            prompt = f" Nome da nova nota (Enter confirma, Esc cancela): {buf}"
            try:
                self.stdscr.addstr(h - 1, 0, prompt[:w].ljust(w - 1), curses.color_pair(2))
                self.stdscr.move(h - 1, min(len(prompt), w - 1))
            except curses.error:
                pass
            self.stdscr.refresh()
            try:
                k = self.stdscr.get_wch()
            except curses.error:
                continue
            if is_enter(k):
                break
            elif is_esc(k):
                buf = None
                break
            elif is_backspace(k):
                buf = buf[:-1]
            elif isinstance(k, str) and len(k) == 1 and ord(k) >= 32:
                buf += k
        curses.curs_set(0)
        return buf

    def open_new(self, title):
        """Abre o editor com um buffer novo; ao salvar (:wq) vira DOC_..._<titulo>.txt."""
        def _edit(stdscr):
            ed = GetexEditor(stdscr, self.cfg, title=title)
            return ed.run()
        curses.wrapper(_edit)

    def run(self):
        while True:
            self.p_scroll = max(0, self.p_scroll)
            self.render()
            try:
                k = self.stdscr.get_wch()
            except curses.error:
                continue

            if k in (curses.KEY_UP, "k"):
                if self.sel > 0:
                    self.sel     -= 1
                    self.p_scroll = 0
            elif k in (curses.KEY_DOWN, "j"):
                if self.sel < len(self.files) - 1:
                    self.sel     += 1
                    self.p_scroll = 0
            elif k in ("c", "C"):
                self.show_calendar = not self.show_calendar
                self.update_files_list()
                self.v_scroll = 0
            elif k in (curses.KEY_LEFT, "h"):
                if self.show_calendar:
                    self.cal_date -= datetime.timedelta(days=1)
                    self.update_files_list()
                    self.v_scroll = 0
                    self.p_scroll = 0
                else:
                    self._show_msg("  Pressione 'c' para ativar o calendário ", curses.color_pair(5))
            elif k in (curses.KEY_RIGHT, "l"):
                if self.show_calendar:
                    self.cal_date += datetime.timedelta(days=1)
                    self.update_files_list()
                    self.v_scroll = 0
                    self.p_scroll = 0
            elif is_enter(k):
                if self.files:
                    current_fpath = self.files[self.sel][0]
                    self.open_file(current_fpath)
                    self.update_files_list()
                    if self.files:
                        new_idx = next(
                            (i for i, f in enumerate(self.files) if f[0] == current_fpath),
                            self.sel
                        )
                        self.sel = new_idx
            elif k == curses.KEY_PPAGE:
                self.p_scroll = max(0, self.p_scroll - 10)
            elif k == curses.KEY_NPAGE:
                prev, _ = self.load_preview()
                h, _ = self.stdscr.getmaxyx()
                self.p_scroll = min(self.p_scroll + 10, max(0, len(prev) - (h - 4)))
            elif k == curses.KEY_HOME:
                self.p_scroll = 0
            elif k == curses.KEY_END:
                prev, _ = self.load_preview()
                h, _ = self.stdscr.getmaxyx()
                self.p_scroll = max(0, len(prev) - (h - 4))
            elif k == "d":
                if self.files:
                    fpath = self.files[self.sel][0]
                    fname = self.files[self.sel][1]
                    if self.confirm_delete(fname):
                        meta = load_sidecar(fpath)
                        if meta and meta.get("id"):
                            # propaga a exclusão para o Firestore (ou enfileira)
                            if fb_is_online():
                                try:
                                    fb_db().collection("notes").document(meta["id"]).set(
                                        {"deleted": True, "updated_at": time.time()}, merge=True)
                                except Exception:
                                    add_tombstone(meta["id"], meta.get("workspace_id"))
                            else:
                                add_tombstone(meta["id"], meta.get("workspace_id"))
                        _delete_local(fpath)
                        self.update_files_list()
                        self.p_scroll = 0
            elif k in ("n", "N"):
                before = {f[0] for f in self.all_files}
                name = self.prompt_new_name()
                if name and name.strip():
                    self.open_new(name.strip())
                    self.update_files_list()
                    novos = [i for i, f in enumerate(self.files) if f[0] not in before]
                    if novos:
                        self.sel      = novos[0]
                        self.v_scroll = 0
                    self.p_scroll = 0
            elif k in ("r", "R"):
                self.ai_organize()
                self.p_scroll = 0
            elif k in ("s", "S"):
                if not fb_is_real_user():
                    self._show_msg("  Sem login Firebase — modo local ", curses.color_pair(5))
                else:
                    self._show_msg("  ⏳ Sincronizando... ", curses.color_pair(6))
                    folder = active_folder(self.cfg)
                    pushed, pulled, st = sync_notes(folder)
                    self.update_files_list()
                    if st == "ok":
                        self._show_msg(f"  ✓ Sincronizado: {pushed}↑ {pulled}↓ ", curses.color_pair(6))
                    elif st == "offline":
                        self._show_msg("  [!] Offline — nada sincronizado ", curses.color_pair(3))
                    else:
                        self._show_msg(f"  [!] {st} ", curses.color_pair(3))
            elif is_esc(k) or k in ("q", "Q"):
                return


# ═══════════════════════════════════════════════════════════════════════════════
# MENU DE TEMAS
# ═══════════════════════════════════════════════════════════════════════════════
class ThemeMenu:
    def __init__(self, stdscr, cfg):
        self.stdscr = stdscr
        self.cfg    = cfg
        self.themes = list(THEMES.keys())
        current = self.cfg.get("theme", "default")
        try:
            self.sel = self.themes.index(current)
        except ValueError:
            self.sel = 0

    def render(self):
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()

        title = " :: Escolha o Tema :: "
        try:
            self.stdscr.addstr(2, max(0, w//2 - len(title)//2), title, curses.color_pair(8) | curses.A_BOLD)
        except curses.error:
            pass

        start_y = 5
        for i, tname in enumerate(self.themes):
            prefix = "▶ " if i == self.sel else "  "
            display_name = prefix + tname.capitalize()
            pair = curses.color_pair(7) | curses.A_BOLD if i == self.sel else curses.color_pair(16)
            x_pos = max(0, w//2 - 10)
            try:
                self.stdscr.addstr(start_y + i, x_pos, display_name.ljust(20), pair)
            except curses.error:
                pass

        hint = " ↑↓ navegar │ Enter selecionar │ Esc cancelar "
        try:
            self.stdscr.addstr(h - 2, 0, hint[:w].ljust(w - 1), curses.color_pair(5))
        except curses.error:
            pass

        self.stdscr.refresh()

    def run(self):
        original_theme = self.cfg.get("theme", "default")
        while True:
            self.render()
            try:
                k = self.stdscr.get_wch()
            except curses.error:
                continue

            if k in (curses.KEY_UP, "k"):
                if self.sel > 0:
                    self.sel -= 1
                init_colors({"theme": self.themes[self.sel]})
                self.stdscr.bkgd(' ', curses.color_pair(16))
            elif k in (curses.KEY_DOWN, "j"):
                if self.sel < len(self.themes) - 1:
                    self.sel += 1
                init_colors({"theme": self.themes[self.sel]})
                self.stdscr.bkgd(' ', curses.color_pair(16))
            elif is_enter(k):
                self.cfg["theme"] = self.themes[self.sel]
                save_config(self.cfg)
                return True
            elif is_esc(k) or k in ("q", "Q"):
                init_colors({"theme": original_theme})
                self.stdscr.bkgd(' ', curses.color_pair(16))
                return False

# ═══════════════════════════════════════════════════════════════════════════════
# MENU DE CONFIGURAÇÕES  ( :config )
# ═══════════════════════════════════════════════════════════════════════════════
class ConfigMenu:
    """Menu interativo para ajustar e persistir as configurações do getex."""

    LABELS = {
        "folder":   "Pasta dos documentos",
        "theme":    "Tema de cores",
        "provider": "Provedor de IA",
        "api_key":  "Chave de API",
    }

    def __init__(self, stdscr, cfg):
        self.stdscr  = stdscr
        self.cfg     = cfg
        self.entries = ["folder", "theme", "provider", "api_key"]
        self.sel     = 0
        self.status  = ""

    def _value(self, key):
        if key == "folder":
            return f"~/Desktop/{self.cfg.get('folder_name', 'GetexDocs')}"
        if key == "theme":
            return self.cfg.get("theme", "default").capitalize()
        if key == "provider":
            return self.cfg.get("ai_provider", "gemini")
        if key == "api_key":
            return "•••••••• (definida)" if self.cfg.get("api_key", "") else "(não definida)"
        return ""

    def render(self):
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()

        title = " :: Configurações do getex :: "
        try:
            self.stdscr.addstr(2, max(0, w//2 - len(title)//2), title,
                               curses.color_pair(8) | curses.A_BOLD)
        except curses.error:
            pass

        x0 = max(2, w//2 - 30)
        for i, key in enumerate(self.entries):
            prefix = "▶ " if i == self.sel else "  "
            label  = self.LABELS[key]
            value  = self._value(key)
            pair   = curses.color_pair(7) | curses.A_BOLD if i == self.sel else curses.color_pair(16)
            line   = f"{prefix}{label:<22}: {value}"
            try:
                self.stdscr.addstr(5 + i * 2, x0, line[:w - x0 - 1], pair)
            except curses.error:
                pass

        cfg_loc = f" Config salva em: {CONFIG_FILE} "
        try:
            self.stdscr.addstr(5 + len(self.entries) * 2 + 1, x0, cfg_loc[:w - x0 - 1],
                               curses.color_pair(4))
        except curses.error:
            pass

        if self.status:
            try:
                self.stdscr.addstr(h - 3, 0, self.status[:w].ljust(w - 1),
                                   curses.color_pair(6) | curses.A_BOLD)
            except curses.error:
                pass

        hint = " ↑↓ navegar │ Enter alterar │ Esc/q voltar "
        try:
            self.stdscr.addstr(h - 2, 0, hint[:w].ljust(w - 1), curses.color_pair(5))
        except curses.error:
            pass

        self.stdscr.refresh()

    def prompt_text(self, label, default="", mask=False):
        """Captura uma linha de texto na base da tela. Retorna None se cancelado (Esc)."""
        buf = default
        curses.curs_set(1)
        while True:
            h, w = self.stdscr.getmaxyx()
            shown  = ("•" * len(buf)) if mask else buf
            prompt = f" {label}: {shown}"
            try:
                self.stdscr.addstr(h - 1, 0, prompt[:w].ljust(w - 1), curses.color_pair(2))
                self.stdscr.move(h - 1, min(len(prompt), w - 1))
            except curses.error:
                pass
            self.stdscr.refresh()
            k = self.stdscr.get_wch()
            if is_enter(k):
                break
            elif is_esc(k):
                buf = None
                break
            elif is_backspace(k):
                buf = buf[:-1]
            elif isinstance(k, str) and len(k) == 1 and ord(k) >= 32:
                buf += k
        curses.curs_set(0)
        return buf

    def activate(self, key):
        if key == "folder":
            val = self.prompt_text("Nome da pasta (em ~/Desktop)",
                                   self.cfg.get("folder_name", "GetexDocs"))
            if val is not None and val.strip():
                self.cfg["folder_name"] = val.strip()
                try:
                    os.makedirs(os.path.expanduser(f"~/Desktop/{val.strip()}"), exist_ok=True)
                except Exception:
                    pass
                save_config(self.cfg)
                self.status = f"✓ Pasta definida: {val.strip()}"
        elif key == "theme":
            tm = ThemeMenu(self.stdscr, self.cfg)
            tm.run()  # ThemeMenu já persiste a escolha e reverte no Esc
            init_colors(self.cfg)
            self.stdscr.bkgd(' ', curses.color_pair(16))
            curses.curs_set(0)
            self.status = f"✓ Tema: {self.cfg.get('theme', 'default').capitalize()}"
        elif key == "provider":
            cur = self.cfg.get("ai_provider", "gemini")
            self.cfg["ai_provider"] = "openai" if cur == "gemini" else "gemini"
            save_config(self.cfg)
            self.status = f"✓ Provedor de IA: {self.cfg['ai_provider']}"
        elif key == "api_key":
            val = self.prompt_text("Nova chave de API (vazio cancela)", "", mask=True)
            if val is not None and val.strip():
                self.cfg["api_key"] = val.strip()
                save_config(self.cfg)
                self.status = "✓ Chave de API salva"

    def run(self):
        curses.curs_set(0)
        while True:
            self.render()
            try:
                k = self.stdscr.get_wch()
            except curses.error:
                continue

            if k in (curses.KEY_UP, "k"):
                if self.sel > 0:
                    self.sel -= 1
            elif k in (curses.KEY_DOWN, "j"):
                if self.sel < len(self.entries) - 1:
                    self.sel += 1
            elif is_enter(k):
                self.activate(self.entries[self.sel])
            elif is_esc(k) or k in ("q", "Q"):
                return

# ═══════════════════════════════════════════════════════════════════════════════
# MENU DE CONTA / MEMBROS DO WORKSPACE  ( :account / :passwd )
# ═══════════════════════════════════════════════════════════════════════════════
class AccountMenu:
    """Gestão de conta: trocar senha, ver membros do workspace e (se você for o
    criador do workspace) remover membros."""

    def __init__(self, stdscr, cfg, start="menu"):
        self.stdscr   = stdscr
        self.cfg      = cfg
        self.user     = fb_user() or {}
        self.wid      = self.user.get("workspace_id", "")
        self.ws_name  = self.user.get("workspace_name") or self.wid
        self.status   = ""
        self.start    = start
        self.is_admin = False
        db = fb_db()
        if db is not None and fb_is_online():
            try:
                creator = fb_workspace_creator(db, self.wid)
                self.is_admin = bool(creator) and creator.lower() == self.user.get("email", "").lower()
            except Exception:
                pass
        self.actions = ["passwd", "members"]
        if self.is_admin:
            self.actions += ["add", "remove"]
        self.sel = 0
        curses.set_escdelay(25)
        init_colors(cfg)
        self.stdscr.bkgd(' ', curses.color_pair(16))
        curses.curs_set(0)
        self.stdscr.keypad(True)

    LABELS = {
        "passwd":  "Trocar minha senha",
        "members": "Ver membros do workspace",
        "add":     "Adicionar usuário (admin)",
        "remove":  "Remover usuário (admin)",
    }

    # ── helpers de UI ─────────────────────────────────────────────────────────
    def _header(self, h, w):
        net = "● online" if fb_is_online() else "○ offline"
        title = f" :: Conta — workspace {self.ws_name} :: "
        try:
            self.stdscr.addstr(2, max(0, w // 2 - len(title) // 2), title,
                               curses.color_pair(8) | curses.A_BOLD)
            sub = f"{self.user.get('email','')}   {net}" + ("   [admin]" if self.is_admin else "")
            self.stdscr.addstr(3, max(0, w // 2 - len(sub) // 2), sub,
                               curses.color_pair(6) if fb_is_online() else curses.color_pair(3))
        except curses.error:
            pass

    def prompt_text(self, label, mask=False):
        """Captura texto na base da tela. Retorna None se cancelado (Esc)."""
        buf = ""
        curses.curs_set(1)
        while True:
            h, w = self.stdscr.getmaxyx()
            shown  = ("•" * len(buf)) if mask else buf
            prompt = f" {label}: {shown}"
            try:
                self.stdscr.addstr(h - 1, 0, prompt[:w].ljust(w - 1), curses.color_pair(2))
                self.stdscr.move(h - 1, min(len(prompt), w - 1))
            except curses.error:
                pass
            self.stdscr.refresh()
            k = self.stdscr.get_wch()
            if is_enter(k):
                break
            elif is_esc(k):
                buf = None
                break
            elif is_backspace(k):
                buf = buf[:-1]
            elif isinstance(k, str) and len(k) == 1 and ord(k) >= 32:
                buf += k
        curses.curs_set(0)
        return buf

    def render(self):
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        self._header(h, w)
        x0 = max(2, w // 2 - 20)
        for i, a in enumerate(self.actions):
            prefix = "▶ " if i == self.sel else "  "
            pair   = curses.color_pair(7) | curses.A_BOLD if i == self.sel else curses.color_pair(16)
            try:
                self.stdscr.addstr(6 + i * 2, x0, f"{prefix}{self.LABELS[a]}"[:w - x0 - 1].ljust(34), pair)
            except curses.error:
                pass
        if self.status:
            try:
                self.stdscr.addstr(h - 3, 0, self.status[:w].ljust(w - 1),
                                   curses.color_pair(6) | curses.A_BOLD)
            except curses.error:
                pass
        hint = " ↑↓ navegar │ Enter selecionar │ Esc/q voltar "
        try:
            self.stdscr.addstr(h - 2, 0, hint[:w].ljust(w - 1), curses.color_pair(5))
        except curses.error:
            pass
        self.stdscr.refresh()

    # ── ações ───────────────────────────────────────────────────────────────
    def change_password(self):
        if not fb_is_online() or fb_db() is None:
            self.status = "[!] Precisa estar online para trocar a senha"
            return
        old = self.prompt_text("Senha atual", mask=True)
        if not old:
            return
        new = self.prompt_text("Nova senha (mín. 4)", mask=True)
        if not new:
            return
        if len(new) < 4:
            self.status = "[!] Senha muito curta (mín. 4 caracteres)"
            return
        conf = self.prompt_text("Confirmar nova senha", mask=True)
        if conf is None:
            return
        if new != conf:
            self.status = "[!] As senhas não conferem"
            return
        res, err = fb_change_password(fb_db(), self.wid, self.user["uid"], old, new)
        if err:
            self.status = f"[!] {err}"
            return
        salt, h = res
        self.user["salt"] = salt
        self.user["password_hash"] = h
        _fb_state["user"] = self.user
        save_session(self.user)
        self.status = "✓ Senha alterada com sucesso"

    def _fetch_members(self):
        if not fb_is_online() or fb_db() is None:
            self.status = "[!] Offline — não dá para listar membros"
            return None
        try:
            return fb_list_members(fb_db(), self.wid)
        except Exception as e:
            self.status = f"[!] {_friendly_fb_error(e)}"
            return None

    def show_members(self):
        members = self._fetch_members()
        if members is None:
            return
        creator = ""
        try:
            creator = fb_workspace_creator(fb_db(), self.wid).lower()
        except Exception:
            pass
        top = 0
        while True:
            self.stdscr.erase()
            h, w = self.stdscr.getmaxyx()
            title = f" Membros de {self.ws_name}  ({len(members)}) "
            try:
                self.stdscr.addstr(1, max(0, w // 2 - len(title) // 2), title,
                                   curses.color_pair(8) | curses.A_BOLD)
            except curses.error:
                pass
            view = h - 4
            for i in range(view):
                mi = top + i
                if mi >= len(members):
                    break
                m = members[mi]
                tags = []
                if m["email"].lower() == self.user.get("email", "").lower():
                    tags.append("você")
                if m["email"].lower() == creator:
                    tags.append("criador")
                suffix = f"  ({', '.join(tags)})" if tags else ""
                line = f"  • {m['email']:<32} {m['name']}{suffix}"
                try:
                    self.stdscr.addstr(3 + i, 2, line[:w - 3], curses.color_pair(16))
                except curses.error:
                    pass
            try:
                self.stdscr.addstr(h - 1, 0, " Esc/Enter/q: voltar ".ljust(w - 1), curses.color_pair(5))
            except curses.error:
                pass
            self.stdscr.refresh()
            k = self.stdscr.get_wch()
            if is_esc(k) or is_enter(k) or k in ("q", "Q"):
                break
            elif k in (curses.KEY_DOWN, "j"):
                top = min(top + 1, max(0, len(members) - view))
            elif k in (curses.KEY_UP, "k"):
                top = max(0, top - 1)

    def remove_member(self):
        members = self._fetch_members()
        if members is None:
            return
        creator = ""
        try:
            creator = fb_workspace_creator(fb_db(), self.wid).lower()
        except Exception:
            pass
        me = self.user.get("email", "").lower()
        # não dá para remover a si mesmo nem o criador do workspace
        cand = [m for m in members if m["email"].lower() not in (me, creator)]
        if not cand:
            self.status = "Nenhum membro removível (só você/criador)"
            return
        sel = 0
        while True:
            self.stdscr.erase()
            h, w = self.stdscr.getmaxyx()
            title = f" Remover membro de {self.ws_name} "
            try:
                self.stdscr.addstr(1, max(0, w // 2 - len(title) // 2), title,
                                   curses.color_pair(8) | curses.A_BOLD)
            except curses.error:
                pass
            for i, m in enumerate(cand):
                prefix = "▶ " if i == sel else "  "
                pair   = curses.color_pair(7) | curses.A_BOLD if i == sel else curses.color_pair(16)
                line   = f"{prefix}{m['email']:<32} {m['name']}"
                try:
                    self.stdscr.addstr(3 + i, 2, line[:w - 3], pair)
                except curses.error:
                    pass
            try:
                self.stdscr.addstr(h - 1, 0, " ↑↓ escolher │ Enter remover │ Esc cancelar ".ljust(w - 1),
                                   curses.color_pair(5))
            except curses.error:
                pass
            self.stdscr.refresh()
            k = self.stdscr.get_wch()
            if is_esc(k) or k in ("q", "Q"):
                return
            elif k in (curses.KEY_DOWN, "j"):
                sel = min(sel + 1, len(cand) - 1)
            elif k in (curses.KEY_UP, "k"):
                sel = max(0, sel - 1)
            elif is_enter(k):
                m = cand[sel]
                conf = self.prompt_text(f"Remover {m['email']}? (s/n)")
                if conf and conf.strip().lower() in ("s", "sim", "y"):
                    ok, err = fb_remove_member(fb_db(), self.wid, m["uid"])
                    self.status = "✓ Membro removido" if ok else f"[!] {err}"
                    return

    def add_member(self):
        if not fb_is_online() or fb_db() is None:
            self.status = "[!] Precisa estar online para adicionar usuário"
            return
        email = self.prompt_text("Email do novo usuário")
        if not email:
            return
        nm = self.prompt_text("Nome (opcional)")
        if nm is None:
            return
        pw = self.prompt_text("Senha inicial (mín. 4)", mask=True)
        if not pw:
            return
        if len(pw) < 4:
            self.status = "[!] Senha muito curta (mín. 4 caracteres)"
            return
        ok, err = fb_add_member(fb_db(), self.wid, email, pw, nm)
        if err:
            self.status = f"[!] {err}"
        else:
            self.status = f"✓ Usuário {email.strip().lower()} adicionado ao {self.ws_name}"

    def activate(self, action):
        if action == "passwd":
            self.change_password()
        elif action == "members":
            self.show_members()
        elif action == "add":
            self.add_member()
        elif action == "remove":
            self.remove_member()

    def run(self):
        if self.start == "passwd":
            self.change_password()
            try:
                self.sel = self.actions.index("passwd")
            except ValueError:
                self.sel = 0
        while True:
            self.render()
            try:
                k = self.stdscr.get_wch()
            except curses.error:
                continue
            if k in (curses.KEY_UP, "k"):
                self.sel = max(0, self.sel - 1)
            elif k in (curses.KEY_DOWN, "j"):
                self.sel = min(len(self.actions) - 1, self.sel + 1)
            elif is_enter(k):
                self.activate(self.actions[self.sel])
            elif is_esc(k) or k in ("q", "Q"):
                return

# ═══════════════════════════════════════════════════════════════════════════════
# TELA DE LOGIN  (email + senha)
# ═══════════════════════════════════════════════════════════════════════════════
class LoginScreen:
    """Login/cadastro simples por email e senha. Retorna a sessão ou None (sair)."""

    LABELS = {"name": "Nome", "email": "Email", "senha": "Senha", "password": "Senha"}

    def __init__(self, stdscr, cfg, online):
        self.stdscr = stdscr
        self.cfg    = cfg
        self.online = online
        self.mode   = "login"     # ou "register"
        self.fields = {"workspace": "", "name": "", "email": "", "password": ""}
        last = load_session()
        if last:
            self.fields["workspace"] = last.get("workspace_name") or last.get("workspace_id", "")
            self.fields["email"]     = last.get("email", "")
        # começa no 1º campo vazio
        self.idx = 0
        for i, f in enumerate(self._order()):
            if not self.fields[f]:
                self.idx = i
                break
        self.msg = ""
        curses.set_escdelay(25)
        init_colors(cfg)
        self.stdscr.bkgd(' ', curses.color_pair(16))
        curses.curs_set(1)
        self.stdscr.keypad(True)

    def _order(self):
        if self.mode == "register":
            return ["workspace", "name", "email", "password"]
        return ["workspace", "email", "password"]

    def render(self):
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        cx = max(2, w // 2 - 24)
        order = self._order()

        title = "G E T E X" if self.mode == "login" else "G E T E X  —  Criar workspace"
        try:
            self.stdscr.addstr(2, max(0, w // 2 - len(title) // 2), title,
                               curses.color_pair(8) | curses.A_BOLD)
        except curses.error:
            pass

        stat  = "● online" if self.online else "○ offline (apenas local)"
        spair = curses.color_pair(6) if self.online else curses.color_pair(3)
        try:
            self.stdscr.addstr(3, max(0, w // 2 - len(stat) // 2), stat, spair | curses.A_BOLD)
        except curses.error:
            pass

        labels = {"workspace": "Workspace",
                  "name": "Nome", "email": "Email", "password": "Senha"}
        masked = ("password",)
        y = 6
        for f in order:
            val    = self.fields[f]
            shown  = "•" * len(val) if f in masked else val
            marker = "▶ " if f == order[self.idx] else "  "
            line   = f"{marker}{labels[f]:<9}: {shown}"
            pair   = curses.color_pair(7) | curses.A_BOLD if f == order[self.idx] else curses.color_pair(16)
            try:
                self.stdscr.addstr(y, cx, line[:w - cx - 1].ljust(44), pair)
            except curses.error:
                pass
            y += 2

        # Linha contextual
        if self.mode == "login":
            tip = "› Para criar um NOVO workspace, pressione F2."
        else:
            tip = "› Para entrar em um workspace existente, pressione F2."
        try:
            self.stdscr.addstr(y, cx, tip[:w - cx - 1], curses.color_pair(4))
        except curses.error:
            pass
        if self.mode == "register":
            try:
                self.stdscr.addstr(y + 1, cx,
                    "  (entrar em workspace já criado é o admin que adiciona você)"[:w - cx - 1],
                    curses.color_pair(4))
            except curses.error:
                pass

        if self.msg:
            try:
                self.stdscr.addstr(y + 3, cx, self.msg[:w - cx - 1],
                                   curses.color_pair(3) | curses.A_BOLD)
            except curses.error:
                pass

        if self.mode == "login":
            hint = " Enter: entrar │ Tab/↑↓: campo │ F2: criar workspace │ Esc: sair "
        else:
            hint = " Enter: criar workspace │ Tab/↑↓: campo │ F2: voltar │ Esc: sair "
        try:
            self.stdscr.addstr(h - 2, 0, hint[:w].ljust(w - 1), curses.color_pair(5))
        except curses.error:
            pass

        # posiciona o cursor no fim do campo ativo
        cur = order[self.idx]
        cur_y = 6 + order.index(cur) * 2
        shown_len = len(self.fields[cur])
        try:
            self.stdscr.move(cur_y, min(cx + 13 + shown_len, w - 1))
        except curses.error:
            pass
        self.stdscr.refresh()

    def submit(self):
        ws    = self.fields["workspace"].strip()
        email = self.fields["email"].strip()
        pw    = self.fields["password"]
        if not ws or not email or not pw:
            self.msg = "Preencha workspace, email e senha."
            return None
        db = fb_db()
        if self.mode == "register":
            if not self.online or db is None:
                self.msg = "Precisa estar online para criar workspace."
                return None
            user, err = fb_create_workspace(db, ws, email, pw, self.fields["name"])
            if err:
                self.msg = err
                return None
            save_session(user)
            _fb_state["user"] = user
            return user
        # login
        if self.online and db is not None:
            user, err = fb_login(db, ws, email, pw)
            if err:
                self.msg = err
                return None
            save_session(user)
            _fb_state["user"] = user
            return user
        user, err = offline_login(ws, email, pw)
        if err:
            self.msg = err
            return None
        _fb_state["user"] = user
        return user

    def run(self):
        while True:
            self.render()
            try:
                k = self.stdscr.get_wch()
            except curses.error:
                continue
            order = self._order()
            cur   = order[self.idx]

            if is_esc(k):
                return None
            elif k == curses.KEY_F2:
                self.mode = "register" if self.mode == "login" else "login"
                self.idx  = 0
                self.msg  = ""
            elif k in (curses.KEY_DOWN, "\t"):
                self.idx = (self.idx + 1) % len(order)
            elif k == curses.KEY_UP:
                self.idx = (self.idx - 1) % len(order)
            elif is_enter(k):
                if self.idx < len(order) - 1:
                    self.idx += 1
                else:
                    res = self.submit()
                    if res is not None:
                        return res
            elif is_backspace(k):
                self.fields[cur] = self.fields[cur][:-1]
            elif isinstance(k, str) and len(k) == 1 and ord(k) >= 32:
                self.fields[cur] += k


# ═══════════════════════════════════════════════════════════════════════════════
# PONTO DE ENTRADA
# ═══════════════════════════════════════════════════════════════════════════════
def show_help():
    help_text = """
╔══════════════════════════════════════════════════════════════════════════╗
║                                GETEX - AJUDA                             ║
╚══════════════════════════════════════════════════════════════════════════╝
getex é um editor de texto modal para terminal focado em produtividade 
e integração com Inteligência Artificial.

[ Uso Básico ]
  getex                  Abre um novo documento no editor.
  getex <título>         Abre um novo documento com o título especificado.
  getex get all          Abre o navegador de arquivos (Explorador).
  getex --help, -h       Exibe esta tela de ajuda.

[ Editor - Modo de Comando ] (Pressione Esc para ativar)
  i, a, o                Entrar no modo de Inserção para digitar.
  h, j, k, l             Navegar o cursor (Esquerda, Baixo, Cima, Direita).
  Setas Direcionais      Navegar o cursor.
  g / G                  Ir para a primeira linha / última linha do arquivo.
  dd                     Apagar a linha atual inteira.
  F2 / F3  (ou 2 / 3)    Marcar a linha atual com bolinha Verde (F2/2) ou Vermelha (F3/3).
  :                      Abrir barra de comandos (veja os comandos abaixo).

[ Editor - Comandos da Barra ( : ) ]
  :wq                    Salvar o documento e sair.
  :q!                    Sair descartando as alterações.
  :q                     Sair (bloqueia caso haja texto não salvo).
  :ai                    Envia o contexto atual para a IA continuar ou responder.
  :config                Abre o menu de configurações (pasta, tema, IA, chave).
  :theme                 Abre o menu para mudar o esquema de cores e fundo.
  :rename <nome>         Renomeia o arquivo ou define o título (ou :title <nome>).
  :set key <chave>       Configura a sua Chave de API de IA (Gemini ou OpenAI).
  :sync                  Sincroniza as notas com o Firebase (quando online).
  :account               Conta: trocar senha, ver/remover membros do workspace.
  :passwd                Troca a sua senha.
  :whoami                Mostra o usuário/workspace e o status de conexão.
  :logout                Encerra a sessão atual.
  :help                  Mostra a lista completa de comandos dentro do editor.

[ Editor - Modo de Inserção ]
  Esc                    Retornar para o Modo de Comando.
  Ctrl + A               Selecionar todo o texto atual.
  Ctrl + C               Copiar a seleção para a área de transferência interna.
  Ctrl + K               Recortar a seleção atual.
  Ctrl + V               Colar.
  Shift + Setas          Selecionar texto.
  Ctrl + Shift + ←/→     Selecionar a palavra inteira.
  Shift + Home/End       Selecionar texto até o início/fim da linha.
  Del / Backspace        Apagar o texto selecionado ou caractere.

[ Navegador de Arquivos ] (getex get all)
  j / k  ou ↑ / ↓        Navegar pela lista de arquivos.
  n                      Criar uma nova nota (pede o nome e abre o editor).
  Enter                  Abrir o arquivo selecionado no editor.
  c                      Exibir/Ocultar o Calendário de filtro de datas à direita.
  h / l  ou ← / →        Navegar entre os dias no Calendário para filtrar a lista.
  r                      Usar IA para reorganizar magicamente o arquivo selecionado.
  d                      Deletar o documento selecionado.
  PgUp / PgDn            Rolar a janela de visualização prévia (Preview).
  q  ou  Esc             Sair do navegador.
"""
    print(help_text)
    sys.exit(0)

def main():
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        show_help()

    cfg = load_config()
    if cfg is None:
        cfg = first_run_setup()

    os.makedirs(os.path.expanduser(f"~/Desktop/{cfg['folder_name']}"), exist_ok=True)

    # ── Firebase: init + login ───────────────────────────────────────────────
    # Fluxo: sessão salva → entra direto (auto-resume); sem sessão e Firebase
    # configurado → tela de login; Firebase ausente → modo local (sem gate).
    fb_init()
    online  = check_online()
    session = load_session()
    if session:
        _fb_state["user"] = session
    elif fb_db() is None:
        _fb_state["user"] = LOCAL_GUEST
    else:
        def _login(stdscr):
            return LoginScreen(stdscr, cfg, online).run()
        user = curses.wrapper(_login)
        if user is None:
            print("\nLogin cancelado.\n")
            return
        _fb_state["user"] = user

    # Sincronização inicial (best-effort) — usa a pasta do workspace ativo
    if fb_is_real_user() and fb_is_online():
        sync_notes(active_folder(cfg))

    if args == ["get", "all"]:
        def _browse(stdscr):
            FilesBrowser(stdscr, cfg).run()
        curses.wrapper(_browse)
        return

    # Título opcional via linha de comando: getex "meu titulo"
    cli_title = " ".join(args) if args else ""

    def _edit(stdscr):
        ed = GetexEditor(stdscr, cfg, title=cli_title or None)
        return ed.run()

    msg = curses.wrapper(_edit)
    if msg:
        print(f"\n{msg}\n")


if __name__ == "__main__":
    main()
