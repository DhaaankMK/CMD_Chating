import json
import socket
import threading
import time

from core import database, protocol
from core.discovery import DiscoveryAnnouncer
from core.net_utils import enable_keepalive, get_local_ips, ip_principal
from core.security import (SecuritySystem, gerar_token, iguais,
                           LOGIN_MAX_TENTATIVAS, LOGIN_BLOQUEIO_SEG)

MSG_RATE_MAX = 5
MSG_RATE_JANELA = 3.0
IP_RATE_MAX = 15
IP_RATE_JANELA = 60.0
AUTH_TIMEOUT = 12.0


class RateLimiter:
    def __init__(self, maximo, janela):
        self.maximo = maximo
        self.janela = janela
        self._d = {}
        self._lock = threading.Lock()

    def permitir(self, chave):
        agora = time.time()
        with self._lock:
            hist = [t for t in self._d.get(chave, []) if agora - t < self.janela]
            if len(hist) >= self.maximo:
                self._d[chave] = hist
                return False
            hist.append(agora)
            self._d[chave] = hist
            return True


class LoginLimiter:
    def __init__(self):
        self._t = {}
        self._lock = threading.Lock()

    def permitido(self, ip, nome):
        key = (ip, nome)
        with self._lock:
            agora = time.time()
            count, bloq = self._t.get(key, (0, 0))
            if bloq > agora:
                return False, int(bloq - agora)
            if bloq and agora >= bloq:
                self._t.pop(key, None)
            return True, 0

    def falha(self, ip, nome):
        key = (ip, nome)
        with self._lock:
            agora = time.time()
            count, _ = self._t.get(key, (0, 0))
            count += 1
            if count >= LOGIN_MAX_TENTATIVAS:
                self._t[key] = (count, agora + LOGIN_BLOQUEIO_SEG)
            else:
                self._t[key] = (count, 0)

    def limpar(self, ip, nome):
        with self._lock:
            self._t.pop((ip, nome), None)


class AdminControlServer:
    """Servidor de controle local (127.0.0.1) para admin.py."""

    def __init__(self, server, port):
        self.server = server
        self.port = port
        self.sock = None
        self.running = False

    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.bind(("127.0.0.1", self.port))
        except OSError as e:
            print("[ADMIN-CTRL] Porta " + str(self.port) + " indisponivel: " + str(e))
            return
        self.sock.listen(5)
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while self.running:
            try:
                conn, addr = self.sock.accept()
            except OSError:
                break
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn):
        try:
            with conn:
                f = conn.makefile("rwb")
                while self.running:
                    line = f.readline()
                    if not line:
                        break
                    try:
                        cmd = json.loads(line.decode("utf-8"))
                        resp = self.server.exec_admin_command(cmd)
                        out = json.dumps({"ok": True, "res": resp}) + "\n"
                    except Exception as e:
                        out = json.dumps({"ok": False, "erro": str(e)}) + "\n"
                    f.write(out.encode())
                    f.flush()
        except Exception:
            pass

    def stop(self):
        self.running = False
        try:
            self.sock.close()
        except Exception:
            pass


class ChatServer:
    def __init__(self, cfg):
        self.cfg = cfg
        self.host = cfg.get("host", "0.0.0.0")
        self.port = int(cfg.get("port", 5555))
        self.name = cfg.get("name", "Servidor")
        self.hoster = cfg.get("hoster", "?")
        self.publico = bool(cfg.get("public", True))
        self.max_slots = int(cfg.get("max_slots", 20))
        self.motd = cfg.get("motd", "")
        self.security = SecuritySystem()
        self.clients = []
        self.lock = threading.Lock()
        self.running = False
        self.sock = None
        self.login_limiter = LoginLimiter()
        self.ip_limiter = RateLimiter(IP_RATE_MAX, IP_RATE_JANELA)
        self.announcer = None
        self.control = None
        self.started_at = time.time()

    def _info_anuncio(self):
        if not self.publico or not self.running:
            return None
        with self.lock:
            usados = len(self.clients)
        return {
            "name": self.name, "hoster": self.hoster,
            "host": ip_principal(), "port": self.port,
            "slots_max": self.max_slots, "slots_used": usados,
            "motd": self.motd, "public": self.publico,
            "uptime": int(time.time() - self.started_at),
        }

    def start(self, banner=True):
        database.init_db()
        database.limpar_remember_expirados()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        enable_keepalive(self.sock)
        try:
            self.sock.bind((self.host, self.port))
        except OSError as e:
            raise RuntimeError("Nao consegui abrir porta " + str(self.port) + ": " + str(e))
        self.sock.listen(64)
        self.running = True

        if self.publico:
            self.announcer = DiscoveryAnnouncer(self._info_anuncio)
            self.announcer.start()

        self.control = AdminControlServer(self, self.port + 1000)
        self.control.start()

        if banner:
            self._print_banner()

        threading.Thread(target=self._ping_loop, daemon=True).start()

        try:
            while self.running:
                try:
                    conn, addr = self.sock.accept()
                except OSError:
                    break
                if not self.running:
                    break
                if not self.ip_limiter.permitir(addr[0]):
                    try:
                        conn.close()
                    except Exception:
                        pass
                    continue
                threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True).start()
        except KeyboardInterrupt:
            print("\n[SERVIDOR] Encerrando...")
        finally:
            self.stop()

    def start_background(self):
        """Inicia o servidor numa thread separada (modo hosting+chat)."""
        database.init_db()
        database.limpar_remember_expirados()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        enable_keepalive(self.sock)
        try:
            self.sock.bind((self.host, self.port))
        except OSError as e:
            raise RuntimeError("Nao consegui abrir porta " + str(self.port) + ": " + str(e))
        self.sock.listen(64)
        self.running = True

        if self.publico:
            self.announcer = DiscoveryAnnouncer(self._info_anuncio)
            self.announcer.start()

        self.control = AdminControlServer(self, self.port + 1000)
        self.control.start()

        threading.Thread(target=self._ping_loop, daemon=True).start()
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def _accept_loop(self):
        while self.running:
            try:
                conn, addr = self.sock.accept()
            except OSError:
                break
            if not self.running:
                break
            if not self.ip_limiter.permitir(addr[0]):
                try:
                    conn.close()
                except Exception:
                    pass
                continue
            threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True).start()

    def stop(self):
        if not self.running:
            return
        self.running = False
        try:
            if self.announcer:
                self.announcer.stop()
        except Exception:
            pass
        try:
            if self.control:
                self.control.stop()
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass
        with self.lock:
            for c in list(self.clients):
                try:
                    c["sock"].close()
                except Exception:
                    pass
            self.clients.clear()

    def _print_banner(self):
        print()
        print("=" * 68)
        print("  SERVIDOR ONLINE: " + self.name)
        print("=" * 68)
        print("  Hoster:  " + self.hoster)
        print("  Modo:    " + ("PUBLICO" if self.publico else "PRIVADO"))
        print("  Slots:   " + str(self.max_slots))
        print("  MOTD:    " + (self.motd or "(vazia)"))
        print("  Bind:    " + self.host + ":" + str(self.port))
        print("  Admin:   127.0.0.1:" + str(self.port + 1000))
        print()
        print("  Enderecos:")
        print("    Local:     127.0.0.1:" + str(self.port))
        for ip in get_local_ips():
            print("    Rede LAN:  " + ip + ":" + str(self.port))
        print()
        print("  Ctrl+C para encerrar.")
        print("=" * 68)
        print()

    def _ping_loop(self):
        while self.running:
            time.sleep(25)
            if not self.running:
                break
            with self.lock:
                clients = list(self.clients)
            for c in clients:
                try:
                    protocol.send_message(c["sock"], self.security, "ping", {})
                except Exception:
                    try:
                        c["sock"].close()
                    except Exception:
                        pass

    def _handle_client(self, conn, addr):
        client = {"sock": conn, "addr": addr, "user": None, "token": None,
                  "msg_limiter": RateLimiter(MSG_RATE_MAX, MSG_RATE_JANELA)}
        try:
            enable_keepalive(conn)
            conn.settimeout(AUTH_TIMEOUT)

            with self.lock:
                total = len(self.clients)
            if total >= self.max_slots:
                self._send_auth_error(conn, "Servidor cheio")
                return

            user = None
            lembrar = False

            while self.running and user is None:
                msg = protocol.recv_message(conn, self.security)
                if not msg:
                    return
                action = msg.get("action")
                payload = msg.get("payload", {})
                ok, err = self.security.validate_payload(payload)
                if not ok:
                    self._send_auth_error(conn, err)
                    continue

                ip = addr[0]
                row = None

                if action == "auto_login":
                    rid = database.validar_remember_token(payload.get("auto_token", ""))
                    if not rid:
                        self._send_auth_error(conn, "auto_token_invalido")
                        continue
                    row = database.get_by_registro(rid)
                    if not row:
                        self._send_auth_error(conn, "auto_token_invalido")
                        continue

                elif action == "login":
                    nome = (payload.get("nome") or "").strip()
                    permitido, espera = self.login_limiter.permitido(ip, nome)
                    if not permitido:
                        self._send_auth_error(conn, "rate_limited:" + str(espera))
                        continue
                    row = database.autenticar(nome, payload.get("senha", ""))
                    if not row:
                        self.login_limiter.falha(ip, nome)
                        self._send_auth_error(conn, "Credenciais invalidas")
                        continue
                    self.login_limiter.limpar(ip, nome)
                    lembrar = bool(payload.get("lembrar"))

                elif action == "register":
                    nome = (payload.get("nome") or "").strip()
                    permitido, espera = self.login_limiter.permitido(ip, "__register__")
                    if not permitido:
                        self._send_auth_error(conn, "muitas tentativas; aguarde " + str(espera) + "s")
                        continue
                    ok_reg, result = database.registrar(nome, payload.get("senha", ""))
                    if not ok_reg:
                        self.login_limiter.falha(ip, "__register__")
                        self._send_auth_error(conn, result)
                        continue
                    self.login_limiter.limpar(ip, "__register__")
                    row = database.autenticar(nome, payload["senha"])
                    if not row:
                        self._send_auth_error(conn, "Falha pos-registro")
                        continue

                else:
                    self._send_auth_error(conn, "Acao invalida")
                    continue

                rid, nome_db, is_admin, is_banned = row
                if is_banned:
                    self._send_auth_error(conn, "Voce esta banido")
                    return
                user = {"registro_id": rid, "nome": nome_db, "is_admin": bool(is_admin),
                        "is_owner": database.is_owner(rid)}

            if user is None:
                return

            client["user"] = user
            client["token"] = gerar_token()

            resp = {
                "success": True,
                "registro_id": user["registro_id"],
                "nome": user["nome"],
                "is_admin": user["is_admin"],
                "is_owner": user["is_owner"],
                "token": client["token"],
                "server_name": self.name,
                "hoster": self.hoster,
                "motd": self.motd,
                "slots_max": self.max_slots,
                "slots_used": 0,
            }
            if lembrar:
                resp["remember_token"] = database.criar_remember_token(user["registro_id"])

            protocol.send_message(conn, self.security, "auth_response", resp)
            conn.settimeout(None)

            with self.lock:
                self.clients.append(client)
                usados = len(self.clients)
            print("[+] " + user["nome"] + " (" + user["registro_id"] + ") entrou [" + str(usados) + "/" + str(self.max_slots) + "]")
            self._broadcast_system(user["nome"] + " entrou. [" + str(usados) + "/" + str(self.max_slots) + "]")

            while self.running:
                msg = protocol.recv_message(conn, self.security)
                if msg is None:
                    break
                self._process(client, msg)

        except (ConnectionError, OSError):
            pass
        except Exception as e:
            print("[!] Erro com " + str(addr) + ": " + str(e))
        finally:
            with self.lock:
                if client in self.clients:
                    self.clients.remove(client)
                usados = len(self.clients)
            if client["user"]:
                print("[-] " + client["user"]["nome"] + " saiu [" + str(usados) + "/" + str(self.max_slots) + "]")
                self._broadcast_system(client["user"]["nome"] + " saiu. [" + str(usados) + "/" + str(self.max_slots) + "]")
            try:
                conn.close()
            except Exception:
                pass

    def _send_auth_error(self, conn, motivo):
        try:
            protocol.send_message(conn, self.security, "auth_response",
                                  {"success": False, "erro": motivo})
        except Exception:
            pass

    def _process(self, client, msg):
        action = msg.get("action")
        payload = msg.get("payload", {})
        ok, err = self.security.validate_payload(payload)
        if not ok:
            self._send_system(client, "Payload rejeitado: " + err)
            return
        if action == "pong":
            return
        if action == "message":
            if not iguais(payload.get("token"), client.get("token")):
                self._send_system(client, "Token invalido.")
                raise ConnectionError("token invalido")
            if not client["msg_limiter"].permitir(client["user"]["registro_id"]):
                self._send_system(client, "Devagar!")
                return
            texto = (payload.get("texto") or "").strip()
            if not texto:
                return
            if texto.startswith("/"):
                self._handle_command(client, texto)
            else:
                self._broadcast_message(client, texto)
        elif action == "disconnect":
            raise ConnectionError("cliente solicitou desconexao")

    def _handle_command(self, client, texto):
        parts = texto.split()
        cmd = parts[0].lower()
        is_owner = bool(client["user"].get("is_owner"))
        is_admin = bool(client["user"].get("is_admin"))

        if cmd == "/help":
            self._send_system(client, "Comandos: /help /whoami /list /stats /me texto /sair /logout"
                              + (" /kick /promover /ban /modo /motd /slots" if is_admin else "")
                              + (" /rebaixar /owner" if is_owner else ""))
            return
        if cmd == "/whoami":
            u = client["user"]
            cargo = " [OWNER]" if u.get("is_owner") else (" [ADMIN]" if u["is_admin"] else "")
            self._send_system(client, "Voce e " + u["nome"] + " (" + u["registro_id"] + ")" + cargo)
            return
        if cmd == "/list":
            with self.lock:
                lista = list(self.clients)
            self._send_system(client, "Online: " + str(len(lista)) + "/" + str(self.max_slots))
            for c in lista:
                u = c["user"]
                if u:
                    cargo = "  [OWNER]" if u.get("is_owner") else ("  [ADMIN]" if u["is_admin"] else "")
                    self._send_system(client, "  " + u["registro_id"] + "  " + u["nome"] + cargo)
            return

        if cmd == "/owner":
            if database.OWNER_ID:
                self._send_system(client, "Owner configurado (ID protegido)")
            else:
                self._send_system(client, "Nenhum Owner configurado nesta instalação.")
            return

        if cmd == "/stats":
            with self.lock:
                online = len(self.clients)
            uptime = int(time.time() - self.started_at)
            horas, resto = divmod(uptime, 3600)
            minutos, segundos = divmod(resto, 60)
            self._send_system(client, "Servidor: " + self.name + " | online: " + str(online) + "/" + str(self.max_slots)
                               + " | uptime: " + str(horas) + "h " + str(minutos) + "m " + str(segundos) + "s")
            return

        if cmd == "/me":
            acao = " ".join(parts[1:]).strip()
            if not acao:
                self._send_system(client, "Uso: /me texto")
                return
            self._broadcast_system("* " + client["user"]["nome"] + " " + acao)
            return

        if not is_admin and not is_owner:
            self._send_system(client, "Comando restrito a administradores.")
            return

        if cmd == "/kick":
            if len(parts) < 2:
                self._send_system(client, "Uso: /kick #ID [motivo]")
                return
            target = self._find_by_id(parts[1])
            if database.is_owner(parts[1]):
                self._send_system(client, "O Owner não pode ser expulso.")
                return
            motivo = " ".join(parts[2:]) or "Sem motivo"
            if not target:
                self._send_system(client, "Nao esta online.")
                return
            self._send_system(target, "Voce foi expulso. Motivo: " + motivo)
            try:
                target["sock"].close()
            except Exception:
                pass
            self._broadcast_system(target["user"]["nome"] + " foi expulso por "
                                   + client["user"]["nome"] + ". Motivo: " + motivo)

        elif cmd == "/promover":
            if len(parts) < 2:
                self._send_system(client, "Uso: /promover #ID")
                return
            rid = parts[1]
            if database.is_owner(rid):
                self._send_system(client, "Esse usuário já possui o cargo Owner.")
                return
            row = database.get_by_registro(rid)
            if not row:
                self._send_system(client, "ID nao encontrado.")
                return
            if row[2]:
                self._send_system(client, row[1] + " ja e admin.")
                return
            if not database.set_admin(rid, True):
                self._send_system(client, "Falha.")
                return
            online = self._find_by_id(rid)
            if online:
                online["user"]["is_admin"] = True
            self._broadcast_system(row[1] + " (" + rid + ") agora e ADMIN.")

        elif cmd == "/ban":
            if len(parts) < 2:
                self._send_system(client, "Uso: /ban #ID")
                return
            rid = parts[1]
            if database.is_owner(rid):
                self._send_system(client, "O Owner não pode ser banido.")
                return
            row = database.get_by_registro(rid)
            if not row:
                self._send_system(client, "ID nao encontrado.")
                return
            if row[2] and not is_owner:
                self._send_system(client, "Somente o Owner pode banir administradores.")
                return
            database.set_ban(rid, True)
            target = self._find_by_id(rid)
            if target:
                self._send_system(target, "Voce foi BANIDO.")
                try:
                    target["sock"].close()
                except Exception:
                    pass
            self._broadcast_system(row[1] + " (" + rid + ") foi BANIDO.")

        elif cmd == "/rebaixar":
            if not is_owner:
                self._send_system(client, "Somente o Owner pode rebaixar administradores.")
                return
            if len(parts) < 2:
                self._send_system(client, "Uso: /rebaixar #ID")
                return
            rid = parts[1]
            if database.is_owner(rid):
                self._send_system(client, "O Owner não pode ser rebaixado.")
                return
            row = database.get_by_registro(rid)
            if not row:
                self._send_system(client, "ID não encontrado.")
                return
            if database.set_admin(rid, False):
                online = self._find_by_id(rid)
                if online:
                    online["user"]["is_admin"] = False
                self._broadcast_system(row[1] + " deixou de ser administrador.")

        elif cmd == "/modo":
            if len(parts) < 2 or parts[1].lower() not in ("publico", "privado", "public", "private"):
                self._send_system(client, "Uso: /modo publico|privado")
                return
            novo = parts[1].lower() in ("publico", "public")
            self.publico = novo
            self.cfg["public"] = novo
            from core import server_config
            server_config.salvar(self.cfg)
            if novo and not self.announcer:
                self.announcer = DiscoveryAnnouncer(self._info_anuncio)
                self.announcer.start()
            elif not novo and self.announcer:
                self.announcer.stop()
                self.announcer = None
            self._broadcast_system("Servidor agora esta " + ("PUBLICO" if novo else "PRIVADO"))

        elif cmd == "/motd":
            novo = " ".join(parts[1:]).strip()
            self.motd = novo
            self.cfg["motd"] = novo
            from core import server_config
            server_config.salvar(self.cfg)
            self._broadcast_system("MOTD: " + (novo or "(vazia)"))

        elif cmd == "/slots":
            if len(parts) < 2 or not parts[1].isdigit():
                self._send_system(client, "Uso: /slots N")
                return
            n = int(parts[1])
            if n < 2 or n > 500:
                self._send_system(client, "2-500.")
                return
            self.max_slots = n
            self.cfg["max_slots"] = n
            from core import server_config
            server_config.salvar(self.cfg)
            self._broadcast_system("Capacidade: " + str(n) + " slots.")

        else:
            self._send_system(client, "Comando desconhecido: " + cmd)

    def _find_by_id(self, rid):
        with self.lock:
            for c in self.clients:
                if c["user"] and c["user"]["registro_id"] == rid:
                    return c
        return None

    def _send_system(self, client, texto):
        try:
            protocol.send_message(client["sock"], self.security, "system", {"texto": texto})
        except Exception:
            pass

    def _broadcast_system(self, texto):
        self._broadcast("system", {"texto": texto})

    def _broadcast_message(self, sender, texto):
        u = sender["user"]
        self._broadcast("message", {
            "registro_id": u["registro_id"], "nome": u["nome"],
            "is_admin": u["is_admin"], "texto": texto,
        })

    def _broadcast(self, action, payload):
        with self.lock:
            clients = list(self.clients)
        for c in clients:
            try:
                protocol.send_message(c["sock"], self.security, action, payload)
            except Exception:
                pass

    # ---------- Comandos remotos do admin.py ----------
    def exec_admin_command(self, cmd):
        action = cmd.get("action")
        if action == "ping":
            return "pong"
        if action == "list":
            with self.lock:
                lista = [c["user"] for c in self.clients if c["user"]]
            return {"online": len(lista), "slots_max": self.max_slots, "users": lista}
        if action == "say":
            texto = (cmd.get("texto") or "").strip()
            if texto:
                self._broadcast_system("[ADMIN] " + texto)
            return "ok"
        if action == "kick":
            rid = cmd.get("rid", "")
            if database.is_owner(rid):
                return "owner protegido"
            t = self._find_by_id(rid)
            if not t:
                return "nao encontrado"
            try:
                t["sock"].close()
            except Exception:
                pass
            self._broadcast_system(t["user"]["nome"] + " foi expulso por um admin.")
            return "kickado"
        if action in ("promote", "ban", "unban"):
            rid = cmd.get("rid", "")
            row = database.get_by_registro(rid)
            if not row:
                return "usuario nao encontrado"
            if database.is_owner(rid):
                return "owner protegido"
            if action == "promote":
                database.set_admin(rid, True)
                online = self._find_by_id(rid)
                if online:
                    online["user"]["is_admin"] = True
                self._broadcast_system(row[1] + " agora e administrador.")
                return "promovido"
            banido = action == "ban"
            database.set_ban(rid, banido)
            online = self._find_by_id(rid)
            if online and banido:
                self._send_system(online, "Sua conta foi bloqueada.")
                try:
                    online["sock"].close()
                except Exception:
                    pass
            self._broadcast_system(row[1] + (" foi banido." if banido else " foi desbanido."))
            return "banido" if banido else "desbanido"
        if action == "stop":
            threading.Thread(target=self.stop, daemon=True).start()
            return "encerrando"
        if action == "info":
            with self.lock:
                usados = len(self.clients)
            return {
                "name": self.name, "hoster": self.hoster, "port": self.port,
                "slots_used": usados, "slots_max": self.max_slots,
                "public": self.publico, "motd": self.motd,
                "uptime": int(time.time() - self.started_at),
            }
        return "comando desconhecido"
