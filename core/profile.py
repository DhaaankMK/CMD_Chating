import json
import os

from cryptography.fernet import Fernet

DIR = os.path.join(os.path.expanduser("~"), ".chat_terminal_pro")
KEY_FILE = os.path.join(DIR, "key.bin")
PROFILE_FILE = os.path.join(DIR, "profile.json")
REMEMBER_FILE = os.path.join(DIR, "remember.json")
ADMIN_FILE = os.path.join(DIR, "admin.json")


def _dir():
    os.makedirs(DIR, exist_ok=True)


def _key():
    _dir()
    if os.path.exists(KEY_FILE):
        try:
            with open(KEY_FILE, "rb") as f:
                return f.read()
        except Exception:
            pass
    k = Fernet.generate_key()
    with open(KEY_FILE, "wb") as f:
        f.write(k)
    try:
        os.chmod(KEY_FILE, 0o600)
    except Exception:
        pass
    return k


def _fernet():
    return Fernet(_key())


def _ler_enc(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "rb") as f:
            enc = f.read()
        return json.loads(_fernet().decrypt(enc).decode("utf-8"))
    except Exception:
        return default


def _salvar_enc(path, dados):
    _dir()
    enc = _fernet().encrypt(json.dumps(dados, ensure_ascii=False).encode("utf-8"))
    with open(path, "wb") as f:
        f.write(enc)
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


# ---------- Perfil ----------
def load_profile():
    return _ler_enc(PROFILE_FILE, None)


def save_profile(dados):
    _salvar_enc(PROFILE_FILE, dados)


def delete_profile():
    try:
        os.remove(PROFILE_FILE)
    except Exception:
        pass


# ---------- Remember tokens ----------
def load_remember():
    return _ler_enc(REMEMBER_FILE, {})


def save_remember(dados):
    _salvar_enc(REMEMBER_FILE, dados)


def chave_servidor(host, port):
    return host + ":" + str(port)


# ---------- Admin ----------
def load_admin_cfg():
    try:
        with open(ADMIN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_admin_cfg(dados):
    _dir()
    with open(ADMIN_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2)
    try:
        os.chmod(ADMIN_FILE, 0o600)
    except Exception:
        pass
