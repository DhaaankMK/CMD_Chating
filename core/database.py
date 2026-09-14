import os
import sqlite3
import threading
import time
import uuid

from core.security import hash_senha, verificar_senha, hash_token

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chat.db"
)
_lock = threading.Lock()
REMEMBER_DIAS = 30
# Distribuição pública começa sem Owner configurado.
# Configure uma política de Owner fora do código-fonte caso isso seja necessário.
OWNER_ID = None


def _connect():
    con = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    con.execute("PRAGMA journal_mode=WAL")
    return con


def init_db():
    with _lock:
        con = _connect()
        try:
            cur = con.cursor()
            cur.execute(
                "CREATE TABLE IF NOT EXISTS usuarios ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " registro_id TEXT UNIQUE NOT NULL,"
                " nome TEXT UNIQUE NOT NULL,"
                " senha_salt TEXT NOT NULL,"
                " senha_hash TEXT NOT NULL,"
                " is_admin INTEGER NOT NULL DEFAULT 0,"
                " is_banned INTEGER NOT NULL DEFAULT 0,"
                " criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )
            cur.execute(
                "CREATE TABLE IF NOT EXISTS remember_tokens ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " token_hash TEXT UNIQUE NOT NULL,"
                " registro_id TEXT NOT NULL,"
                " expires_at REAL NOT NULL,"
                " criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_rem_reg ON remember_tokens(registro_id)")
            con.commit()
        finally:
            con.close()


def gerar_registro_id():
    return "#" + uuid.uuid4().hex[:8].upper()


def is_owner(rid):
    """Sem Owner padrão: nenhuma conta da distribuição pública recebe esse cargo."""
    return bool(OWNER_ID) and str(rid or "").upper() == str(OWNER_ID).upper()


def registrar(nome, senha):
    nome = (nome or "").strip()
    if not nome or not senha:
        return False, "Nome e senha obrigatorios"
    if len(nome) > 30:
        return False, "Nome muito longo (max 30)"
    if len(nome) < 3:
        return False, "Nome muito curto (min 3)"
    if len(senha) < 4:
        return False, "Senha muito curta (min 4)"
    if len(senha) > 100:
        return False, "Senha muito longa"
    with _lock:
        con = _connect()
        try:
            cur = con.cursor()
            cur.execute("SELECT COUNT(*) FROM usuarios")
            total = cur.fetchone()[0]
            is_admin = 1 if total == 0 else 0
            rid = gerar_registro_id()
            salt, h = hash_senha(senha)
            cur.execute(
                "INSERT INTO usuarios (registro_id, nome, senha_salt, senha_hash, is_admin)"
                " VALUES (?, ?, ?, ?, ?)",
                (rid, nome, salt, h, is_admin),
            )
            con.commit()
            return True, rid
        except sqlite3.IntegrityError:
            return False, "Nome ja existe"
        except sqlite3.Error as e:
            return False, "Erro DB: " + str(e)
        finally:
            con.close()


def autenticar(nome, senha):
    with _lock:
        con = _connect()
        try:
            cur = con.cursor()
            cur.execute(
                "SELECT registro_id, nome, senha_salt, senha_hash, is_admin, is_banned"
                " FROM usuarios WHERE nome=?",
                ((nome or "").strip(),),
            )
            row = cur.fetchone()
        finally:
            con.close()
    if not row:
        return None
    rid, nome_db, salt_hex, hash_hex, is_admin, is_banned = row
    if not verificar_senha(senha, salt_hex, hash_hex):
        return None
    return (rid, nome_db, is_admin, is_banned)


def get_by_registro(rid):
    with _lock:
        con = _connect()
        try:
            cur = con.cursor()
            cur.execute(
                "SELECT registro_id, nome, is_admin, is_banned FROM usuarios WHERE registro_id=?",
                (rid,),
            )
            return cur.fetchone()
        finally:
            con.close()


def get_by_nome(nome):
    with _lock:
        con = _connect()
        try:
            cur = con.cursor()
            cur.execute(
                "SELECT registro_id, nome, is_admin, is_banned FROM usuarios WHERE nome=?",
                ((nome or "").strip(),),
            )
            return cur.fetchone()
        finally:
            con.close()


def listar_todos():
    with _lock:
        con = _connect()
        try:
            cur = con.cursor()
            cur.execute("SELECT registro_id, nome, is_admin, is_banned, criado_em FROM usuarios ORDER BY id")
            return cur.fetchall()
        finally:
            con.close()


def set_admin(rid, status):
    if is_owner(rid) and not status:
        return False
    with _lock:
        con = _connect()
        try:
            cur = con.cursor()
            cur.execute("UPDATE usuarios SET is_admin=? WHERE registro_id=?",
                        (1 if status else 0, rid))
            con.commit()
            return cur.rowcount > 0
        finally:
            con.close()


def set_ban(rid, status):
    with _lock:
        con = _connect()
        try:
            cur = con.cursor()
            cur.execute("UPDATE usuarios SET is_banned=? WHERE registro_id=?",
                        (1 if status else 0, rid))
            con.commit()
            return cur.rowcount > 0
        finally:
            con.close()


def total_usuarios():
    with _lock:
        con = _connect()
        try:
            cur = con.cursor()
            cur.execute("SELECT COUNT(*) FROM usuarios")
            return cur.fetchone()[0]
        finally:
            con.close()


def criar_remember_token(rid, dias=REMEMBER_DIAS):
    from core.security import gerar_remember_token
    t = gerar_remember_token()
    exp = time.time() + dias * 86400
    with _lock:
        con = _connect()
        try:
            cur = con.cursor()
            cur.execute("INSERT INTO remember_tokens (token_hash, registro_id, expires_at)"
                        " VALUES (?, ?, ?)", (hash_token(t), rid, exp))
            con.commit()
        finally:
            con.close()
    return t


def validar_remember_token(token):
    if not token:
        return None
    with _lock:
        con = _connect()
        try:
            cur = con.cursor()
            cur.execute("SELECT registro_id, expires_at FROM remember_tokens WHERE token_hash=?",
                        (hash_token(token),))
            row = cur.fetchone()
        finally:
            con.close()
    if not row:
        return None
    rid, exp = row
    if time.time() > exp:
        revogar_remember_token(token)
        return None
    return rid


def revogar_remember_token(token):
    with _lock:
        con = _connect()
        try:
            cur = con.cursor()
            cur.execute("DELETE FROM remember_tokens WHERE token_hash=?", (hash_token(token),))
            con.commit()
            return cur.rowcount > 0
        finally:
            con.close()


def limpar_remember_expirados():
    with _lock:
        con = _connect()
        try:
            cur = con.cursor()
            cur.execute("DELETE FROM remember_tokens WHERE expires_at < ?", (time.time(),))
            con.commit()
        finally:
            con.close()


def garantir_hoster(nome, senha):
    """Garante que exista um usuario chamado 'nome' com senha. Vira admin."""
    database_init = init_db()
    row = get_by_nome(nome)
    if row:
        return True, row[0]
    ok, rid = registrar(nome, senha)
    if not ok:
        return False, rid
    set_admin(rid, True)
    return True, rid
