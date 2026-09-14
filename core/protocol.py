import json
import struct

HEADER_SIZE = 4
MAX_FRAME = 64 * 1024
MAX_ACTION = 32


def send_message(sock, security, action, payload):
    if not isinstance(action, str) or len(action) > MAX_ACTION:
        raise ValueError("acao invalida")
    if not isinstance(payload, dict):
        raise ValueError("payload invalido")
    msg = {"action": action, "payload": payload}
    raw = json.dumps(msg, ensure_ascii=False).encode("utf-8")
    encrypted = security.encrypt(raw)
    if len(encrypted) > MAX_FRAME:
        raise ValueError("mensagem excede o limite")
    header = struct.pack("!I", len(encrypted))
    sock.sendall(header + encrypted)


def recv_message(sock, security):
    header = _recv_exact(sock, HEADER_SIZE)
    if header is None:
        return None
    (length,) = struct.unpack("!I", header)
    if length <= 0 or length > MAX_FRAME:
        return None
    body = _recv_exact(sock, length)
    if body is None:
        return None
    decrypted = security.decrypt(body)
    if decrypted is None:
        return None
    try:
        msg = json.loads(decrypted.decode("utf-8"))
        if not isinstance(msg, dict) or not isinstance(msg.get("action"), str):
            return None
        if len(msg["action"]) > MAX_ACTION or not isinstance(msg.get("payload"), dict):
            return None
        return msg
    except Exception:
        return None


def _recv_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        try:
            chunk = sock.recv(n - len(buf))
        except (ConnectionError, OSError):
            return None
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)
