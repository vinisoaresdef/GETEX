#!/usr/bin/env python3
"""
getex_server — backend de notas do getex (substitui o Firebase).

Stdlib pura: http.server + sqlite3. Sem dependências pip.
Banco: um único arquivo SQLite (GETEX_DB, padrão ./getex.db).

Modelo (igual ao antigo Firestore, agora em SQLite):
  workspaces(wid, name, created_at, created_by, admin_uid)
  users(uid, wid, email, name, salt, password_hash, created_at)   UNIQUE(wid,email)
  notes(id, wid, owner_uid, author_email, filename, title, content, marks, updated_at, deleted)
  sessions(token, uid, wid, created_at)

Auth: workspace/email/senha. Senha é PBKDF2 verificada AQUI; o hash só volta
para o próprio dono (após provar a senha), para o login offline do cliente.
Ações administrativas e sync exigem um token de sessão (emitido no login/registro).
"""
import os, json, time, sqlite3, hashlib, secrets, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DB   = os.environ.get("GETEX_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "getex.db"))
PORT = int(os.environ.get("GETEX_PORT", "8090"))
_LOCK = threading.Lock()  # ponytail: lock global p/ escrever; suficiente p/ time pequeno. Por-workspace se escalar.


# ─── Senhas (idêntico ao cliente: PBKDF2-HMAC-SHA256, 100k) ──────────────────
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

def normalize_ws(name):
    s = (name or "").strip().upper()
    out = []
    for ch in s:
        if ch.isalnum():
            out.append(ch)
        elif ch in (" ", "-", "_"):
            out.append("_")
    return "".join(out)[:64]


# ─── Banco ───────────────────────────────────────────────────────────────────
def db():
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c

def init_db():
    with _LOCK, db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS workspaces(
            wid TEXT PRIMARY KEY, name TEXT, created_at REAL,
            created_by TEXT, admin_uid TEXT);
        CREATE TABLE IF NOT EXISTS users(
            uid TEXT PRIMARY KEY, wid TEXT, email TEXT, name TEXT,
            salt TEXT, password_hash TEXT, created_at REAL,
            UNIQUE(wid, email));
        CREATE TABLE IF NOT EXISTS notes(
            id TEXT PRIMARY KEY, wid TEXT, owner_uid TEXT, author_email TEXT,
            filename TEXT, title TEXT, content TEXT, marks TEXT,
            updated_at REAL, deleted INTEGER DEFAULT 0);
        CREATE INDEX IF NOT EXISTS idx_notes_wid ON notes(wid);
        CREATE TABLE IF NOT EXISTS sessions(
            token TEXT PRIMARY KEY, uid TEXT, wid TEXT, created_at REAL);
        """)


# ─── Sessão / auth ───────────────────────────────────────────────────────────
def _session_dict(c, u, wid, ws_name, token):
    return {"uid": u["uid"], "email": u["email"], "name": u["name"],
            "workspace_id": wid, "workspace_name": ws_name,
            "salt": u["salt"], "password_hash": u["password_hash"], "token": token}

def issue_token(c, uid, wid):
    tok = secrets.token_urlsafe(32)
    c.execute("INSERT INTO sessions(token,uid,wid,created_at) VALUES(?,?,?,?)",
              (tok, uid, wid, time.time()))
    return tok

def auth(c, body):
    """Devolve a linha de user a partir do token, ou None."""
    tok = (body or {}).get("token", "")
    if not tok:
        return None
    s = c.execute("SELECT uid,wid FROM sessions WHERE token=?", (tok,)).fetchone()
    if not s:
        return None
    return c.execute("SELECT * FROM users WHERE uid=?", (s["uid"],)).fetchone()


# ─── Handlers (cada um devolve (status, dict)) ───────────────────────────────
def h_health(c, b):
    return 200, {"ok": True}

def h_register(c, b):
    wid = normalize_ws(b.get("ws_name"))
    email = (b.get("email") or "").strip().lower()
    pw = b.get("password") or ""
    if not wid or not email or not pw:
        return 400, {"error": "Informe workspace, email e senha."}
    if c.execute("SELECT 1 FROM workspaces WHERE wid=?", (wid,)).fetchone():
        return 409, {"error": f"Workspace '{wid}' já existe — peça ao admin para te adicionar"}
    salt, h = hash_password(pw)
    uid = secrets.token_hex(16)
    nm = (b.get("name") or "").strip() or email.split("@")[0]
    now = time.time()
    c.execute("INSERT INTO users(uid,wid,email,name,salt,password_hash,created_at) VALUES(?,?,?,?,?,?,?)",
              (uid, wid, email, nm, salt, h, now))
    c.execute("INSERT INTO workspaces(wid,name,created_at,created_by,admin_uid) VALUES(?,?,?,?,?)",
              (wid, wid, now, email, uid))
    tok = issue_token(c, uid, wid)
    u = {"uid": uid, "email": email, "name": nm, "salt": salt, "password_hash": h}
    return 200, _session_dict(c, u, wid, wid, tok)

def h_login(c, b):
    wid = normalize_ws(b.get("ws_name"))
    email = (b.get("email") or "").strip().lower()
    pw = b.get("password") or ""
    if not wid:
        return 400, {"error": "Informe o workspace"}
    ws = c.execute("SELECT * FROM workspaces WHERE wid=?", (wid,)).fetchone()
    if not ws:
        return 404, {"error": "Workspace não encontrado"}
    u = c.execute("SELECT * FROM users WHERE wid=? AND email=?", (wid, email)).fetchone()
    if not u:
        return 404, {"error": "Usuário não encontrado neste workspace"}
    if not verify_password(pw, u["salt"], u["password_hash"]):
        return 401, {"error": "Senha incorreta"}
    tok = issue_token(c, u["uid"], wid)
    return 200, _session_dict(c, u, wid, ws["name"], tok)

def h_ws_info(c, b):
    if auth(c, b) is None:
        return 401, {"error": "Sessão inválida"}
    wid = normalize_ws(b.get("wid"))
    ws = c.execute("SELECT * FROM workspaces WHERE wid=?", (wid,)).fetchone()
    if not ws:
        return 404, {"error": "Workspace não encontrado"}
    return 200, {"created_by": ws["created_by"], "admin_uid": ws["admin_uid"], "name": ws["name"]}

def h_member_add(c, b):
    caller = auth(c, b)
    if caller is None:
        return 401, {"error": "Sessão inválida"}
    wid = normalize_ws(b.get("wid")) or caller["wid"]
    ws = c.execute("SELECT * FROM workspaces WHERE wid=?", (wid,)).fetchone()
    if not ws:
        return 404, {"error": "Workspace não encontrado"}
    if caller["uid"] != ws["admin_uid"]:
        return 403, {"error": "Só o admin do workspace pode adicionar membros"}
    email = (b.get("email") or "").strip().lower()
    pw = b.get("password") or ""
    if not email or not pw:
        return 400, {"error": "Informe email e senha do novo membro"}
    if c.execute("SELECT 1 FROM users WHERE wid=? AND email=?", (wid, email)).fetchone():
        return 409, {"error": "Email já cadastrado neste workspace"}
    salt, h = hash_password(pw)
    nm = (b.get("name") or "").strip() or email.split("@")[0]
    c.execute("INSERT INTO users(uid,wid,email,name,salt,password_hash,created_at) VALUES(?,?,?,?,?,?,?)",
              (secrets.token_hex(16), wid, email, nm, salt, h, time.time()))
    return 200, {"ok": True}

def h_member_list(c, b):
    caller = auth(c, b)
    if caller is None:
        return 401, {"error": "Sessão inválida"}
    wid = normalize_ws(b.get("wid")) or caller["wid"]
    if caller["wid"] != wid:
        return 403, {"error": "Você não é membro deste workspace"}
    rows = c.execute("SELECT uid,email,name FROM users WHERE wid=? ORDER BY email", (wid,)).fetchall()
    return 200, {"members": [dict(r) for r in rows]}

def h_member_remove(c, b):
    caller = auth(c, b)
    if caller is None:
        return 401, {"error": "Sessão inválida"}
    wid = caller["wid"]
    ws = c.execute("SELECT * FROM workspaces WHERE wid=?", (wid,)).fetchone()
    if not ws or caller["uid"] != ws["admin_uid"]:
        return 403, {"error": "Só o admin do workspace pode remover membros"}
    uid = b.get("uid") or ""
    if uid == caller["uid"] or uid == ws["admin_uid"]:
        return 400, {"error": "Não é possível remover o admin/criador"}
    c.execute("DELETE FROM users WHERE wid=? AND uid=?", (wid, uid))
    return 200, {"ok": True}

def h_passwd(c, b):
    caller = auth(c, b)
    if caller is None:
        return 401, {"error": "Sessão inválida"}
    if not verify_password(b.get("old_pw") or "", caller["salt"], caller["password_hash"]):
        return 401, {"error": "Senha atual incorreta"}
    new_pw = b.get("new_pw") or ""
    if len(new_pw) < 1:
        return 400, {"error": "Nova senha vazia"}
    salt, h = hash_password(new_pw)
    c.execute("UPDATE users SET salt=?, password_hash=? WHERE uid=?", (salt, h, caller["uid"]))
    return 200, {"salt": salt, "hash": h}

def h_notes_pull(c, b):
    caller = auth(c, b)
    if caller is None:
        return 401, {"error": "Sessão inválida"}
    rows = c.execute(
        "SELECT id,filename,title,content,marks,owner_uid,updated_at,deleted FROM notes WHERE wid=?",
        (caller["wid"],)).fetchall()
    notes = []
    for r in rows:
        d = dict(r)
        try:
            d["marks"] = json.loads(r["marks"]) if r["marks"] else {}
        except Exception:
            d["marks"] = {}
        d["deleted"] = bool(r["deleted"])
        notes.append(d)
    return 200, {"notes": notes}

def h_notes_push(c, b):
    caller = auth(c, b)
    if caller is None:
        return 401, {"error": "Sessão inválida"}
    nid = b.get("id")
    if not nid:
        return 400, {"error": "id da nota ausente"}
    c.execute("""INSERT INTO notes(id,wid,owner_uid,author_email,filename,title,content,marks,updated_at,deleted)
                 VALUES(?,?,?,?,?,?,?,?,?,?)
                 ON CONFLICT(id) DO UPDATE SET
                   filename=excluded.filename, title=excluded.title, content=excluded.content,
                   marks=excluded.marks, updated_at=excluded.updated_at, deleted=excluded.deleted""",
              (nid, caller["wid"], caller["uid"], caller["email"],
               b.get("filename", ""), b.get("title", ""), b.get("content", ""),
               json.dumps(b.get("marks") or {}), float(b.get("updated_at") or time.time()),
               1 if b.get("deleted") else 0))
    return 200, {"ok": True}

def h_notes_delete(c, b):
    caller = auth(c, b)
    if caller is None:
        return 401, {"error": "Sessão inválida"}
    c.execute("UPDATE notes SET deleted=1, updated_at=? WHERE id=? AND wid=?",
              (time.time(), b.get("id"), caller["wid"]))
    return 200, {"ok": True}


ROUTES = {
    ("GET", "/health"):           h_health,
    ("POST", "/health"):          h_health,
    ("POST", "/workspace/register"): h_register,
    ("POST", "/login"):           h_login,
    ("POST", "/workspace/info"):  h_ws_info,
    ("POST", "/member/add"):      h_member_add,
    ("POST", "/member/list"):     h_member_list,
    ("POST", "/member/remove"):   h_member_remove,
    ("POST", "/passwd"):          h_passwd,
    ("POST", "/notes/pull"):      h_notes_pull,
    ("POST", "/notes/push"):      h_notes_push,
    ("POST", "/notes/delete"):    h_notes_delete,
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silencia log padrão ruidoso
        pass

    def _send(self, status, obj):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle(self, method):
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        fn = ROUTES.get((method, path))
        if fn is None:
            return self._send(404, {"error": "rota não encontrada"})
        body = {}
        if method == "POST":
            try:
                n = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(n) if n else b""
                body = json.loads(raw.decode("utf-8")) if raw else {}
            except Exception:
                return self._send(400, {"error": "JSON inválido"})
        try:
            with _LOCK, db() as c:
                status, obj = fn(c, body)
        except Exception as e:
            return self._send(500, {"error": f"erro interno: {str(e)[:80]}"})
        self._send(status, obj)

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")


def main():
    init_db()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"getex_server ouvindo em :{PORT}  (db={DB})", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
