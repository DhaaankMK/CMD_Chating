import socket
import sys
import threading
import time
from collections import deque

from core import protocol, profile
from core.net_utils import enable_keepalive
from core.security import SecuritySystem
from ui import terminal


def _autologin_get(host, port):
    dados = profile.load_remember()
    return dados.get(profile.chave_servidor(host, port))


def _autologin_set(host, port, auto_token, registro_id, nome):
    dados = profile.load_remember()
    dados[profile.chave_servidor(host, port)] = {
        "auto_token": auto_token, "registro_id": registro_id, "nome": nome,
    }
    profile.save_remember(dados)


def _autologin_remove(host, port):
    dados = profile.load_remember()
    dados.pop(profile.chave_servidor(host, port), None)
    profile.save_remember(dados)


class ChatClient:
    def __init__(self, host="127.0.0.1", port=5555):
        self.host = host
        self.port = port
        self.sock = None
        self.security = SecuritySystem()
        self.running = False
        self.user = None
        self.token = None
        self.server_info = {}
        self._input_ativo = False
        self._print_lock = threading.Lock()
        self._history = deque(maxlen=50)
        self._started_at = None

    def connect(self, tentativas=3, timeout=5.0):
        ultimo = None
        for i in range(1, tentativas + 1):
            s = None
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(timeout)
                s.connect((self.host, self.port))
                enable_keepalive(s)
                self.sock = s
                return True
            except socket.timeout:
                ultimo = "timeout"
            except ConnectionRefusedError:
                ultimo = "conexao recusada"
            except OSError as e:
                ultimo = str(e)
            finally:
                if s is not None and s is not self.sock:
                    try:
                        s.close()
                    except OSError:
                        pass
            time.sleep(min(4.0, 0.8 * (2 ** (i - 1))))
        print("[CLIENTE] Falha. Ultimo erro: " + str(ultimo))
        return False

    def close(self):
        self.running = False
        try:
            if self.sock:
                self.sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass

    def _aplicar(self, resp, lembrar=False, remember_token=None):
        if not resp:
            return False
        payload = resp.get("payload", {})
        if not payload.get("success"):
            return False
        self.user = {
            "registro_id": payload["registro_id"],
            "nome": payload["nome"],
            "is_admin": payload["is_admin"],
            "is_owner": payload.get("is_owner", False),
        }
        self.token = payload.get("token")
        self.server_info = {
            "server_name": payload.get("server_name", "?"),
            "hoster": payload.get("hoster", "?"),
            "motd": payload.get("motd", ""),
            "slots_max": payload.get("slots_max", 0),
        }
        if lembrar and payload.get("remember_token"):
            _autologin_set(self.host, self.port, payload["remember_token"],
                           payload["registro_id"], payload["nome"])
        try:
            self.sock.settimeout(None)
        except OSError:
            pass
        return True

    def auto_auth(self, nome, senha):
        """
        Ordem: remember token -> login -> register.
        Server aceita multiplas tentativas no mesmo socket.
        Retorna (True, motivo) ou (False, motivo).
        """
        # 1) remember token
        info = _autologin_get(self.host, self.port)
        if info:
            try:
                protocol.send_message(self.sock, self.security, "auto_login",
                                      {"auto_token": info["auto_token"]})
                resp = protocol.recv_message(self.sock, self.security)
                if resp and resp.get("payload", {}).get("success"):
                    self._aplicar(resp, lembrar=False)
                    return True, "auto"
                _autologin_remove(self.host, self.port)
            except Exception:
                pass

        # 2) login
        try:
            protocol.send_message(self.sock, self.security, "login",
                                  {"nome": nome, "senha": senha, "lembrar": True})
            resp = protocol.recv_message(self.sock, self.security)
            if resp and resp.get("payload", {}).get("success"):
                self._aplicar(resp, lembrar=True)
                return True, "login"
        except Exception:
            pass

        # 3) register
        try:
            protocol.send_message(self.sock, self.security, "register",
                                  {"nome": nome, "senha": senha})
            resp = protocol.recv_message(self.sock, self.security)
            if resp and resp.get("payload", {}).get("success"):
                self._aplicar(resp, lembrar=False)
                # Pede remember token
                try:
                    protocol.send_message(self.sock, self.security, "login",
                                          {"nome": nome, "senha": senha, "lembrar": True})
                    resp2 = protocol.recv_message(self.sock, self.security)
                    if resp2 and resp2.get("payload", {}).get("success"):
                        self._aplicar(resp2, lembrar=True)
                except Exception:
                    pass
                return True, "register"
        except Exception as e:
            return False, str(e)

        return False, "nao foi possivel autenticar"

    def logout_local(self):
        _autologin_remove(self.host, self.port)

    def start(self):
        self.running = True
        self._started_at = time.time()
        threading.Thread(target=self._recv_loop, daemon=True).start()
        threading.Thread(target=self._ping_loop, daemon=True).start()
        self._input_loop()

    def _ping_loop(self):
        while self.running:
            time.sleep(25)
            if not self.running:
                break
            try:
                protocol.send_message(self.sock, self.security, "ping", {})
            except Exception:
                break

    def _recv_loop(self):
        while self.running:
            try:
                msg = protocol.recv_message(self.sock, self.security)
            except Exception:
                break
            if msg is None:
                break
            try:
                self._handle(msg)
            except Exception:
                pass
        self.running = False
        self._print_above_prompt(terminal.YELLOW + "[SISTEMA] Conexao encerrada." + terminal.RESET)
        print(terminal.GRAY + "[Pressione Enter para sair]" + terminal.RESET)

    def _handle(self, msg):
        action = msg.get("action")
        payload = msg.get("payload", {})
        if action == "message":
            nome = payload.get("nome", "?")
            texto = payload.get("texto", "")
            is_admin = payload.get("is_admin", False)
            is_owner = payload.get("is_owner", False)
            cor = terminal.MAGENTA if is_owner else (terminal.RED if is_admin else terminal.GREEN)
            tag = "[OWNER] " if is_owner else ("[ADMIN] " if is_admin else "")
            hora = time.strftime("%H:%M")
            self._print_above_prompt(terminal.GRAY + hora + " " + terminal.RESET + cor + tag + "[" + nome + "]" + terminal.RESET + " " + texto)
        elif action == "system":
            self._print_above_prompt(terminal.YELLOW + "[SISTEMA] " + payload.get("texto", "") + terminal.RESET)
        elif action == "ping":
            try:
                protocol.send_message(self.sock, self.security, "pong", {})
            except Exception:
                pass

    def _print_above_prompt(self, texto):
        with self._print_lock:
            try:
                sys.stdout.write("\r\033[2K")
                print(texto)
                if self._input_ativo and self.running:
                    sys.stdout.write(terminal.CYAN + "> " + terminal.RESET)
                    sys.stdout.flush()
            except Exception:
                pass

    def _input_loop(self):
        self._print_above_prompt(terminal.CYAN + "Digite uma mensagem ou /help para ver os comandos." + terminal.RESET)
        while self.running:
            try:
                self._input_ativo = True
                texto = input(terminal.CYAN + "> " + terminal.RESET)
            except (EOFError, KeyboardInterrupt):
                break
            finally:
                self._input_ativo = False
            texto = texto.strip()
            if not texto:
                continue
            if texto.startswith("!!") and self._history:
                texto = self._history[-1]
                self._print_above_prompt(terminal.GRAY + "↪ " + texto + terminal.RESET)
            elif not texto.startswith("/"):
                self._history.append(texto)
            if texto.lower() == "/sair":
                break
            if texto.lower() == "/clear":
                terminal.clear()
                self._print_above_prompt(terminal.CYAN + "Tela limpa. /help para ajuda." + terminal.RESET)
                continue
            if texto.lower() == "/time":
                self._print_above_prompt(terminal.GRAY + time.strftime("Agora são %d/%m/%Y %H:%M:%S") + terminal.RESET)
                continue
            if texto.lower() == "/help":
                terminal.chat_help(bool(self.user and self.user.get("is_admin")),
                                   bool(self.user and self.user.get("is_owner")))
                continue
            if texto.lower() == "/logout":
                self.logout_local()
                self._print_above_prompt(terminal.GREEN + "[OK] Auto-login removido deste servidor." + terminal.RESET)
                continue
            try:
                protocol.send_message(self.sock, self.security, "message",
                                      {"texto": texto, "token": self.token})
            except Exception as e:
                self._print_above_prompt(terminal.RED + "[ERRO] " + str(e) + terminal.RESET)
                break
        self.close()
