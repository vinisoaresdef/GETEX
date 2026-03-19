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
import datetime

# ─── Constantes ─────────────────────────────────────────────────────────────
CONFIG_FILE = os.path.expanduser("~/.getex_config")
ESC_KEY     = 27

DEFAULT_CONFIG = {
    "folder_name": "GetexDocs",
    "ai_provider": "gemini",
    "api_key":     "",
}

# ─── Config ──────────────────────────────────────────────────────────────────
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
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
def call_ai(text, cfg):
    try:
        import urllib.request
        import json as _json
        provider = cfg.get("ai_provider", "gemini")
        api_key  = cfg.get("api_key", "")
        if not api_key:
            return "[ERRO] Nenhuma chave de API configurada. Use :set key SUA_CHAVE"
        prompt = (
            "Continue, melhore ou responda ao seguinte texto "
            "de forma útil e concisa:\n\n" + text
        )
        if provider == "gemini":
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-pro:generateContent?key={api_key}"
            )
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            req = urllib.request.Request(
                url, data=_json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"}, method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = _json.loads(resp.read())
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
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
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = _json.loads(resp.read())
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[ERRO IA] {e}"

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
    folder_path = os.path.expanduser(f"~/Desktop/{cfg.get('folder_name','GetexDocs')}")
    os.makedirs(folder_path, exist_ok=True)
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
def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1,  curses.COLOR_BLACK,  curses.COLOR_CYAN)     # INSERT
    curses.init_pair(2,  curses.COLOR_BLACK,  curses.COLOR_YELLOW)   # COMMAND
    curses.init_pair(3,  curses.COLOR_WHITE,  curses.COLOR_RED)      # erro
    curses.init_pair(4,  curses.COLOR_CYAN,   -1)                    # nº linha
    curses.init_pair(5,  curses.COLOR_WHITE,  curses.COLOR_BLUE)     # cmd bar
    curses.init_pair(6,  curses.COLOR_GREEN,  -1)                    # info
    curses.init_pair(7,  curses.COLOR_BLACK,  curses.COLOR_WHITE)    # lista sel
    curses.init_pair(8,  curses.COLOR_YELLOW, -1)                    # título
    curses.init_pair(9,  curses.COLOR_WHITE,  curses.COLOR_MAGENTA)  # header
    curses.init_pair(10, curses.COLOR_BLACK,  curses.COLOR_CYAN)     # seleção texto

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

        curses.set_escdelay(25)
        init_colors()
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
        self.clear_sel()
        self.status = f"✓ Recortado para clipboard"

    def delete_sel(self):
        if not self.has_sel():
            return
        sr, sc, er, ec = self.sel_range()
        self.lines, self.row, self.col = delete_selection(self.lines, sr, sc, er, ec)
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
            while c > 0 and not ln[c-1].isalnum():
                c -= 1
            while c > 0 and ln[c-1].isalnum():
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
                # número de linha
                try:
                    self.stdscr.addstr(sr, 0, f"{br+1:>4} ", curses.color_pair(4))
                except curses.error:
                    pass
                # conteúdo da linha, char a char para highlight de seleção
                ln   = self.lines[br]
                disp = ln[:w - gutter - 1]
                for ci, ch in enumerate(disp):
                    attr = sel_pair if self.in_selection(br, ci) else 0
                    try:
                        self.stdscr.addch(sr, gutter + ci, ch, attr)
                    except curses.error:
                        pass
                # espaço após fim da linha — highlight se seleção passa por aqui
                if self.in_selection(br, len(ln)):
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
        rtag  = f"  {self.title}  " if self.title else "  getex  "
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
                disp_cmd = "  'i' inserir | ':rename' nomear | ':wq' salvar | Shift+↑↓←→ selecionar"
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
        if cmd == "wq":
            if self.source_file:
                # Editando arquivo existente → sobrescreve
                path = save_document(self.lines, self.cfg,
                                     filepath=self.source_file, overwrite=True)
            else:
                # Nova sessão → gera nome com data+hora (+ título se houver)
                path = save_document(self.lines, self.cfg, title=self.title or None)
            return "QUIT", f"✓ Salvo em {path}"
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
                        self.row -= 1
                    continue

                # ── Enter: cancela seleção e insere nova linha ────────────
                if is_enter(k):
                    if self.has_sel():
                        self.delete_sel()
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
                            self.row = min(self.row, len(self.lines) - 1)
                        else:
                            self.lines[0] = ""
                        self.col = 0


# ═══════════════════════════════════════════════════════════════════════════════
# NAVEGADOR DE ARQUIVOS  — getex get all
# ═══════════════════════════════════════════════════════════════════════════════
def list_docs(cfg):
    folder = os.path.expanduser(f"~/Desktop/{cfg.get('folder_name','GetexDocs')}")
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
        self.files    = list_docs(cfg)
        self.sel      = 0
        self.v_scroll = 0
        self.p_scroll = 0

        curses.set_escdelay(25)
        init_colors()
        curses.curs_set(0)
        self.stdscr.keypad(True)

    def load_preview(self):
        if not self.files:
            return []
        fpath = self.files[self.sel][0]
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                return f.read().splitlines()
        except Exception as e:
            return [f"[Erro: {e}]"]

    def render(self):
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()

        folder = self.cfg.get("folder_name", "GetexDocs")
        header = f"  getex get all  │  ~/Desktop/{folder}/  │  {len(self.files)} arquivo(s)"
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
            pair   = curses.color_pair(7) | curses.A_BOLD if fi == self.sel else 0
            try:
                self.stdscr.addstr(row, 0, line[:list_w], pair)
            except curses.error:
                pass

        prev_lines = self.load_preview()
        if not self.files:
            try:
                self.stdscr.addstr(2, prev_x + 2, "Nenhum arquivo encontrado.",
                                   curses.color_pair(3))
            except curses.error:
                pass
        else:
            fname = self.files[self.sel][1]
            try:
                self.stdscr.addstr(1, prev_x + 1,
                    f" {fname} "[:prev_w], curses.color_pair(8) | curses.A_BOLD)
            except curses.error:
                pass
            for pi in range(content_h - 1):
                li  = pi + self.p_scroll
                row = pi + 2
                if li < len(prev_lines):
                    try:
                        self.stdscr.addstr(row, prev_x + 1, prev_lines[li][:prev_w - 1])
                    except curses.error:
                        pass

        hints = " ↑↓ navegar │ Enter abrir/editar │ d deletar │ PgUp/PgDn preview │ Esc/q sair "
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
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                initial = f.read().splitlines()
        except Exception as e:
            initial = [f"[Erro: {e}]"]

        def _edit(stdscr):
            # source_file=fpath garante que :wq sobrescreve em vez de fazer append
            ed = GetexEditor(stdscr, self.cfg, initial_lines=initial or [""], source_file=fpath)
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
            elif is_enter(k):
                if self.files:
                    self.open_file(self.files[self.sel][0])
                    self.files = list_docs(self.cfg)
                    self.sel   = min(self.sel, max(0, len(self.files) - 1))
            elif k == curses.KEY_PPAGE:
                self.p_scroll = max(0, self.p_scroll - 10)
            elif k == curses.KEY_NPAGE:
                prev = self.load_preview()
                h, _ = self.stdscr.getmaxyx()
                self.p_scroll = min(self.p_scroll + 10, max(0, len(prev) - (h - 4)))
            elif k == curses.KEY_HOME:
                self.p_scroll = 0
            elif k == curses.KEY_END:
                prev = self.load_preview()
                h, _ = self.stdscr.getmaxyx()
                self.p_scroll = max(0, len(prev) - (h - 4))
            elif k == "d":
                if self.files:
                    fname = self.files[self.sel][1]
                    if self.confirm_delete(fname):
                        os.remove(self.files[self.sel][0])
                        self.files    = list_docs(self.cfg)
                        self.sel      = min(self.sel, max(0, len(self.files) - 1))
                        self.p_scroll = 0
            elif is_esc(k) or k in ("q", "Q"):
                return


# ═══════════════════════════════════════════════════════════════════════════════
# PONTO DE ENTRADA
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    cfg = load_config()
    if cfg is None:
        cfg = first_run_setup()

    os.makedirs(
        os.path.expanduser(f"~/Desktop/{cfg['folder_name']}"),
        exist_ok=True
    )

    args = sys.argv[1:]

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
