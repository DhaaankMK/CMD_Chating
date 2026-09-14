import base64
import hashlib
import hmac
import secrets

from cryptography.fernet import Fernet

MAX_TEXT_LEN = 500
MAX_FIELDS = 20
MAX_KEY_LEN = 40
PBKDF2_ITER = 200_000
LOGIN_MAX_TENTATIVAS = 5
LOGIN_BLOQUEIO_SEG = 60

_PASSPHRASE = b"chat_terminal_pro::v5::chave_unica_do_projeto"
_CHAVE = base64.urlsafe_b64encode(hashlib.sha256(_PASSPHRASE).digest())


class SecuritySystem:
    def __init__(self):
        self.fernet = Fernet(_CHAVE)

    def encrypt(self, data):
        return self.fernet.encrypt(data)

    def decrypt(self, data):
        try:
            return self.fernet.decrypt(data)
        except Exception:
            return None

    @staticmethod
    def validate_payload(payload):
        if not isinstance(payload, dict):
            return False, "payload invalido"
        if len(payload) > MAX_FIELDS:
            return False, "payload excede " + str(MAX_FIELDS) + " campos"
        for k, v in payload.items():
            if not isinstance(k, str):
                return False, "chave invalida"
            if len(k) > MAX_KEY_LEN:
                return False, "chave muito longa"
            if isinstance(v, str) and len(v) > MAX_TEXT_LEN:
                return False, "campo '" + k + "' excede " + str(MAX_TEXT_LEN) + " chars"
            if not isinstance(v, (str, int, float, bool, type(None))):
                return False, "tipo invalido no campo '" + k + "'"
        return True, ""


def hash_senha(senha):
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, PBKDF2_ITER)
    return salt.hex(), dk.hex()


def verificar_senha(senha, salt_hex, hash_hex):
    try:
        salt = bytes.fromhex(salt_hex)
    except Exception:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, PBKDF2_ITER)
    return hmac.compare_digest(dk.hex(), hash_hex)


def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def gerar_token():
    return secrets.token_urlsafe(32)


def gerar_remember_token():
    return secrets.token_urlsafe(48)


def iguais(a, b):
    try:
        return hmac.compare_digest(str(a), str(b))
    except Exception:
        return False
