import json
import socket
import struct
import threading
import time

MCAST_GRP = "239.255.42.99"
MCAST_PORT = 5556
ANNOUNCE_INTERVAL = 3.0
ENTRY_TTL = 10.0
PROTO_VERSION = 5
MAX_ANNOUNCE = 2048


class DiscoveryAnnouncer:
    def __init__(self, info_provider):
        self.info_provider = info_provider
        self.running = False
        self.sock = None

    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        try:
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
        except Exception:
            pass
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while self.running:
            try:
                info = self.info_provider()
                if info is not None:
                    info = dict(info)
                    info["type"] = "announce"
                    info["v"] = PROTO_VERSION
                    raw = json.dumps(info, ensure_ascii=False).encode("utf-8")
                    if len(raw) > MAX_ANNOUNCE:
                        continue
                    self.sock.sendto(raw, (MCAST_GRP, MCAST_PORT))
            except Exception:
                pass
            time.sleep(ANNOUNCE_INTERVAL)

    def stop(self):
        self.running = False
        try:
            self.sock.close()
        except Exception:
            pass


class DiscoveryListener:
    def __init__(self):
        self.servers = {}
        self.lock = threading.Lock()
        self.running = False
        self.sock = None

    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.bind(("", MCAST_PORT))
        except OSError as e:
            raise RuntimeError("Porta " + str(MCAST_PORT) + " ocupada: " + str(e))
        mreq = struct.pack("4sl", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
        try:
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        except OSError:
            pass
        self.sock.settimeout(0.8)
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(4096)
            except socket.timeout:
                self._expire()
                continue
            except OSError:
                break
            try:
                if len(data) > MAX_ANNOUNCE:
                    continue
                info = json.loads(data.decode("utf-8"))
                if info.get("type") != "announce":
                    continue
                if info.get("v") != PROTO_VERSION:
                    continue
                port = int(info.get("port", 0))
                name = str(info.get("name", ""))
                if not (1 <= port <= 65535) or not name or len(name) > 80:
                    continue
                info["_seen"] = time.time()
                info["_origem"] = addr[0]
                # Nunca confie no host anunciado no pacote: use a origem UDP.
                # Isso evita que um anúncio redirecione o usuário para outro IP.
                info["host"] = addr[0]
                info["port"] = port
                key = (addr[0], port)
                with self.lock:
                    self.servers[key] = info
            except Exception:
                pass
        self._expire()

    def _expire(self):
        agora = time.time()
        with self.lock:
            for k in [k for k, v in self.servers.items()
                      if agora - v["_seen"] > ENTRY_TTL]:
                del self.servers[k]

    def listar(self):
        with self.lock:
            return sorted(self.servers.values(),
                          key=lambda x: x.get("_seen", 0), reverse=True)

    def stop(self):
        self.running = False
        try:
            self.sock.close()
        except Exception:
            pass
