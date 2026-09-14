import os
import shutil

if os.name == "nt":
    os.system("")

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"
GRAY = "\033[90m"


def _supports_color():
    return os.getenv("NO_COLOR") is None and (os.name == "nt" or os.getenv("TERM") not in (None, "dumb"))


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def width():
    return max(68, min(shutil.get_terminal_size((88, 24)).columns, 110))


def _bar(char="─"):
    return char * width()


def print_system(t):
    print(YELLOW + "◆ SISTEMA  " + RESET + str(t))


def print_success(t):
    print(GREEN + "✓ OK       " + RESET + str(t))


def print_error(t):
    print(RED + "✗ ERRO     " + RESET + str(t))


def print_info(t):
    print(CYAN + "• " + RESET + str(t))


def print_admin(t):
    print(RED + BOLD + "⚡ ADMIN    " + RESET + str(t))


def print_banner():
    clear()
    w = width()
    inner = w - 2
    print(CYAN + BOLD + "╔" + "═" * inner + "╗")
    print("║" + " CHAT TERMINAL PRO".ljust(inner) + "║")
    print("║" + " comunicação local • segura • sem complicação".ljust(inner) + "║")
    print("╚" + "═" * inner + "╝" + RESET)
    print(GRAY + "  QuickServer  ·  Perfil global  ·  Hosting  ·  Admin" + RESET)


def print_rule():
    print(GRAY + _bar() + RESET)


def print_status(label, value, color=WHITE):
    print("  " + GRAY + f"{label:<12}" + RESET + color + str(value) + RESET)


def prompt(text="Escolha"):
    return input(CYAN + "❯ " + RESET + text + ": ").strip()


def chat_help(is_admin=False, is_owner=False):
    print_rule()
    print(CYAN + BOLD + "  COMANDOS DO CHAT" + RESET)
    print("  /help       mostra esta ajuda")
    print("  /whoami     exibe seu perfil e ID")
    print("  /list       lista pessoas online")
    print("  /clear      limpa a tela")
    print("  /time       mostra o horário local")
    print("  /logout     remove o login automático deste servidor")
    print("  /sair       encerra a sessão")
    if is_admin:
        print("  /kick #ID [motivo]  /promover #ID  /ban #ID")
        print("  /modo publico|privado  /motd texto  /slots N")
    if is_owner:
        print("  /rebaixar #ID  /owner")
    print_rule()
