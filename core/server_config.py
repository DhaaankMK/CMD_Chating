import json
import os

CFG_FILENAME = "server.cfg"


def caminho_cfg():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), CFG_FILENAME)


def existe():
    return os.path.exists(caminho_cfg())


def carregar():
    p = caminho_cfg()
    if not os.path.exists(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def salvar(cfg):
    with open(caminho_cfg(), "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
