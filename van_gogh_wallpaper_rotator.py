import ctypes
import json
import os
import random
import sys
import time
import winreg
from pathlib import Path

# ============================================================
# CONFIGURAÇÃO
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

SCRIPT_PATH = Path(__file__).resolve()

WALLPAPER_DIR = BASE_DIR / "Van_Gogh_Collection" / "Wallpapers_FullHD"

CACHE_DIR = BASE_DIR / "Van_Gogh_Collection" / ".cache"

STATE_FILE = CACHE_DIR / "rotator_state.json"

LOG_FILE = CACHE_DIR / "rotator.log"

# Rodando via pythonw.exe (sem console, como no login
# automático) sys.stdout/stderr vêm como None — nesse caso
# jogamos a saída para um arquivo de log. Com console normal,
# só garantimos UTF-8 (cp1252 quebra em vários emojis usados
# abaixo).
if sys.stdout is None or sys.stderr is None:

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    log_handle = open(
        LOG_FILE, "a", encoding="utf-8", buffering=1
    )

    sys.stdout = log_handle
    sys.stderr = log_handle

elif (
    sys.stdout.encoding
    and sys.stdout.encoding.lower() != "utf-8"
):

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_INTERVAL_MINUTES = 30

SPI_SETDESKWALLPAPER = 20
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDCHANGE = 0x02

STARTUP_DIR = (
    Path(os.environ["APPDATA"])
    / "Microsoft"
    / "Windows"
    / "Start Menu"
    / "Programs"
    / "Startup"
)

STARTUP_SCRIPT = STARTUP_DIR / "VanGoghWallpaperRotator.vbs"


# ============================================================
# WALLPAPER DO WINDOWS
# ============================================================

def set_wallpaper_style_fill():

    # WallpaperStyle "10" = Preencher (mantém proporção,
    # corta o excesso). Evita que o Windows distorça/reduza
    # a imagem (e a legenda) num monitor com resolução
    # diferente de 1920x1080.
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Control Panel\Desktop",
        0,
        winreg.KEY_SET_VALUE
    )

    try:

        winreg.SetValueEx(
            key, "WallpaperStyle", 0, winreg.REG_SZ, "10"
        )

        winreg.SetValueEx(
            key, "TileWallpaper", 0, winreg.REG_SZ, "0"
        )

    finally:

        winreg.CloseKey(key)


def set_wallpaper(path):

    ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETDESKWALLPAPER,
        0,
        str(path),
        SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
    )


# ============================================================
# ESTADO (evita repetir antes de passar por todas as imagens)
# ============================================================

def load_deck():

    if not STATE_FILE.exists():
        return []

    try:

        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("deck", [])

    except Exception:

        return []


def save_deck(deck):

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"deck": deck}, f)


def next_wallpaper(images):

    deck = [
        name
        for name in load_deck()
        if name in images
    ]

    if not deck:

        deck = list(images.keys())

        random.shuffle(deck)

    name = deck.pop(0)

    save_deck(deck)

    return images[name]


# ============================================================
# INICIALIZAÇÃO AUTOMÁTICA COM O WINDOWS
# ============================================================

def python_executable_for_startup():

    # pythonw.exe roda sem abrir janela de console.
    pythonw = Path(sys.executable).with_name("pythonw.exe")

    if pythonw.exists():
        return pythonw

    return Path(sys.executable)


def install_startup(interval_minutes):

    STARTUP_DIR.mkdir(parents=True, exist_ok=True)

    python_exe = python_executable_for_startup()

    vbs_content = (
        'Set WshShell = CreateObject("WScript.Shell")\n'
        'WshShell.Run "'
        f'""{python_exe}"" ""{SCRIPT_PATH}"" {interval_minutes}'
        '", 0, False\n'
    )

    with open(
        STARTUP_SCRIPT, "w", encoding="utf-8"
    ) as f:

        f.write(vbs_content)

    print(
        f"✓ Instalado em: {STARTUP_SCRIPT}\n\n"
        f"A partir do próximo login, o papel de parede vai "
        f"trocar sozinho a cada {interval_minutes} min, sem "
        f"precisar abrir nada.\n\n"
        "Para desativar depois, rode:\n"
        f"  python \"{SCRIPT_PATH}\" --uninstall-startup"
    )


def uninstall_startup():

    if STARTUP_SCRIPT.exists():

        STARTUP_SCRIPT.unlink()

        print(
            f"✓ Removido: {STARTUP_SCRIPT}"
        )

    else:

        print(
            "Nada instalado para remover."
        )


# ============================================================
# LOOP PRINCIPAL
# ============================================================

def parse_interval_minutes(args):

    if not args:
        return DEFAULT_INTERVAL_MINUTES

    try:

        minutes = float(args[0])

        if minutes <= 0:
            raise ValueError

        return minutes

    except ValueError:

        print(
            f"Intervalo inválido: '{args[0]}'. "
            "Use um número de minutos, ex: 30"
        )

        sys.exit(1)


def run_loop(interval_minutes):

    if not WALLPAPER_DIR.exists():

        print(
            f"Pasta não encontrada: {WALLPAPER_DIR}\n"
            "Rode van_gogh_wallpapers.py primeiro."
        )

        sys.exit(1)

    set_wallpaper_style_fill()

    print(
        "==========================================\n"
        " VAN GOGH WALLPAPER ROTATOR\n"
        "==========================================\n"
    )
    print(
        f"Pasta: {WALLPAPER_DIR}"
    )
    print(
        f"Intervalo: {interval_minutes} minuto(s)"
    )
    print(
        "Pressione Ctrl+C para parar.\n"
    )

    try:

        while True:

            images = {
                path.name: path
                for path in WALLPAPER_DIR.glob("*.jpg")
            }

            if not images:

                print(
                    "Nenhuma imagem encontrada em "
                    f"{WALLPAPER_DIR}. Tentando de novo em "
                    f"{interval_minutes} min..."
                )

            else:

                wallpaper = next_wallpaper(images)

                print(
                    f"🖼️ {wallpaper.stem}"
                )

                set_wallpaper(
                    wallpaper.resolve()
                )

            time.sleep(interval_minutes * 60)

    except KeyboardInterrupt:

        print(
            "\nParado pelo usuário."
        )


def main():

    args = sys.argv[1:]

    if "--uninstall-startup" in args:

        uninstall_startup()

        return

    if "--install-startup" in args:

        args.remove("--install-startup")

        install_startup(
            parse_interval_minutes(args)
        )

        return

    run_loop(
        parse_interval_minutes(args)
    )


if __name__ == "__main__":

    main()
