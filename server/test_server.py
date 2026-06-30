#!/usr/bin/env python3
"""Self-check end-to-end do getex_server. Sobe um servidor temporário e
exercita registro/login/notas/membros/auth. Roda: python3 test_server.py"""
import os, sys, json, time, tempfile, subprocess, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = "8099"
BASE = f"http://127.0.0.1:{PORT}"

def call(path, payload=None, method="POST"):
    data = json.dumps(payload or {}).encode() if payload is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())

def main():
    db = tempfile.mktemp(suffix=".db")
    env = dict(os.environ, GETEX_DB=db, GETEX_PORT=PORT)
    proc = subprocess.Popen([sys.executable, os.path.join(HERE, "getex_server.py")], env=env)
    try:
        for _ in range(50):
            try:
                if call("/health", None, "GET")[0] == 200:
                    break
            except Exception:
                time.sleep(0.1)
        else:
            raise SystemExit("servidor não subiu")

        # registro do workspace + admin
        st, r = call("/workspace/register", {"ws_name": "Time X", "email": "a@x.com", "password": "s1", "name": "Ana"})
        assert st == 200 and r["workspace_id"] == "TIME_X" and r["token"], r
        admin = r["token"]

        # nome duplicado falha
        st, r = call("/workspace/register", {"ws_name": "time-x", "email": "b@x.com", "password": "s2"})
        assert st == 409, r

        # login confere senha
        assert call("/login", {"ws_name": "TIME_X", "email": "a@x.com", "password": "errada"})[0] == 401
        st, r = call("/login", {"ws_name": "TIME_X", "email": "a@x.com", "password": "s1"})
        assert st == 200 and r["token"], r

        # push + pull
        assert call("/notes/push", {"token": admin, "id": "n1", "filename": "doc.txt",
                                    "content": "ola mundo", "marks": {"2": "green"}, "updated_at": 100.0})[0] == 200
        st, r = call("/notes/pull", {"token": admin})
        assert st == 200 and len(r["notes"]) == 1 and r["notes"][0]["content"] == "ola mundo", r
        assert r["notes"][0]["marks"] == {"2": "green"}, r

        # pull sem token = 401 (privacidade do workspace)
        assert call("/notes/pull", {})[0] == 401

        # admin adiciona membro; membro loga e vê a mesma nota
        assert call("/member/add", {"token": admin, "email": "c@x.com", "password": "s3", "name": "Cleo"})[0] == 200
        st, r = call("/login", {"ws_name": "TIME_X", "email": "c@x.com", "password": "s3"})
        membro = r["token"]
        assert call("/notes/pull", {"token": membro})[1]["notes"][0]["content"] == "ola mundo"

        # membro NÃO pode adicionar (só admin)
        assert call("/member/add", {"token": membro, "email": "d@x.com", "password": "s4"})[0] == 403

        # troca de senha do membro
        assert call("/passwd", {"token": membro, "old_pw": "errada", "new_pw": "s5"})[0] == 401
        assert call("/passwd", {"token": membro, "old_pw": "s3", "new_pw": "s5"})[0] == 200
        assert call("/login", {"ws_name": "TIME_X", "email": "c@x.com", "password": "s5"})[0] == 200

        # lista de membros (2)
        st, r = call("/member/list", {"token": admin})
        assert st == 200 and len(r["members"]) == 2, r

        # admin remove o membro; não pode remover a si mesmo
        membros = {m["email"]: m["uid"] for m in r["members"]}
        assert call("/member/remove", {"token": admin, "uid": membros["a@x.com"]})[0] == 400
        assert call("/member/remove", {"token": admin, "uid": membros["c@x.com"]})[0] == 200
        assert len(call("/member/list", {"token": admin})[1]["members"]) == 1

        # exclusão (tombstone) aparece no pull como deleted
        assert call("/notes/delete", {"token": admin, "id": "n1"})[0] == 200
        notes = call("/notes/pull", {"token": admin})[1]["notes"]
        assert notes[0]["deleted"] is True, notes

        # isolamento entre workspaces: WS2 não vê notas do WS1
        st, r = call("/workspace/register", {"ws_name": "Outro", "email": "z@z.com", "password": "p"})
        assert call("/notes/pull", {"token": r["token"]})[1]["notes"] == []

        print("OK — todos os asserts passaram")
    finally:
        proc.terminate()
        try:
            os.remove(db)
        except Exception:
            pass

if __name__ == "__main__":
    main()
