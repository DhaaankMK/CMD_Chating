import time

from core.discovery import DiscoveryListener
from core.net_utils import ping_tcp


def descobrir(timeout=3.5):
    listener = DiscoveryListener()
    try:
        listener.start()
    except Exception:
        return [], None
    time.sleep(timeout)
    return listener.listar(), listener


def ranquear(servers):
    """
    Score = 0.65 * populacao_normalizada + 0.35 * latencia_normalizada
    Retorna [(score, servidor, latencia_ms), ...] ordenado desc.
    """
    resultado = []
    for s in servers:
        host = s.get("host")
        port = s.get("port")
        if not host or not port:
            continue
        usados = int(s.get("slots_used", 0) or 0)
        maxs = max(1, int(s.get("slots_max", 1) or 1))
        if usados >= maxs:
            continue
        lat = ping_tcp(host, port, timeout=1.5)
        if lat is None:
            continue
        pop_score = (usados / maxs) * 100.0
        lat_score = max(0.0, 100.0 - min(100.0, lat))
        score = pop_score * 0.65 + lat_score * 0.35
        resultado.append((score, s, lat))
    resultado.sort(key=lambda x: x[0], reverse=True)
    return resultado


def melhor(timeout=3.5):
    servers, listener = descobrir(timeout)
    try:
        if not servers:
            return None, [], None
        ranking = ranquear(servers)
        if not ranking:
            return None, [], listener
        return ranking[0], ranking, listener
    finally:
        pass


def parar_listener(listener):
    if listener is None:
        return
    try:
        listener.stop()
    except Exception:
        pass
