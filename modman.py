import sys
import os
import zipfile
import requests
import tempfile
import shutil
from urllib.parse import urlparse, parse_qs, unquote
from tqdm import tqdm
import winreg
import configparser

# ---------- COLORS ----------
from colorama import Fore, Style, init
init(autoreset=True)


# ---------- HASHING ----------
import hashlib

def md5_file(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()





# ---------- PROTOCOL REGISTRATION ----------
def register_protocol(exe_path):
    key_path = r"Software\Classes\modman"

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
        winreg.SetValue(key, "", winreg.REG_SZ, "URL:ModMan Protocol")
        winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path + r"\shell\open\command") as key:
        winreg.SetValue(
            key,
            "",
            winreg.REG_SZ,
            f"\"{exe_path}\" \"%1\""
        )

# ================= CONFIG =================
GAME_ID = 3809
API_KEY = None
# ==========================================

# ---------- CONFIG ----------
def get_config_path():
    config_dir = os.path.join(os.environ["APPDATA"], "ModMan")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "config.ini")

def get_api_key():
    config_path = get_config_path()
    config = configparser.ConfigParser()

    if os.path.exists(config_path):
        config.read(config_path)
        if "modio" in config and "api_key" in config["modio"]:
            return config["modio"]["api_key"]

    print(Fore.RED + "ключа нету блять!")
    print(Fore.BLUE + "можно получить тут : https://mod.io/me/access!")
    api_key = input(Fore.YELLOW + "введи ключ > ").strip()

    if not api_key:
        raise RuntimeError("нужен ключ")

    config["modio"] = {"api_key": api_key}
    with open(config_path, "w") as f:
        config.write(f)

    print(Fore.GREEN + "сохранил ключ.")
    return api_key

# ---------- UTILS ----------
def human_size(size):
    for unit in ("b", "kb", "mb", "gb"):
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} tb"

def parse_modman_url(url: str):
    parsed = urlparse(url)
    if parsed.scheme != "modman":
        raise ValueError("неверный протокол")

    params = parse_qs(parsed.query)

    # ---- DIRECT URL MODE ----
    if "direct_url" in params:
        direct_url = unquote(params["direct_url"][0])

        if not direct_url.startswith(("http://", "https://")):
            raise ValueError("direct_url должен быть http/https")

        filename = params.get(
            "name",
            [os.path.basename(urlparse(direct_url).path) or "mod.zip"]
        )[0]

        filesize = int(params.get("size", [0])[0])

        return {
            "mode": "direct",
            "direct_url": direct_url,
            "filename": filename,
            "filesize": filesize
        }

    # ---- MOD.IO MODE ----
    mod_id = params.get("id", [None])[0]
    file_id = params.get("file", [None])[0]

    if not mod_id or not file_id:
        raise ValueError("нет id или fileid")

    return {
        "mode": "modio",
        "mod_id": mod_id,
        "file_id": file_id
    }

# ---------- MOD.IO API ----------
def get_mod_info(mod_id):
    url = f"https://g-3809.modapi.io/v1/games/{GAME_ID}/mods/{mod_id}"
    r = requests.get(url, params={"api_key": API_KEY}, timeout=10)
    r.raise_for_status()
    data = r.json()
    return {
        "name": data.get("name", "без названия"),
        "summary": data.get("summary", "без описания")
    }

def get_mod_file_info(mod_id, file_id):
    url = f"https://g-3809.modapi.io/v1/games/{GAME_ID}/mods/{mod_id}/files/{file_id}"
    r = requests.get(url, params={"api_key": API_KEY}, timeout=10)
    r.raise_for_status()
    data = r.json()
    return {
        "filename": data.get("filename", "mod.zip"),
        "filesize": data.get("filesize", 0),
        "download_url": data["download"]["binary_url"],
        "md5": data.get("filehash", {}).get("md5")
    }

# ---------- FILESYSTEM ----------
def get_bonelab_mods_dir():
    return os.path.join(
        os.environ["USERPROFILE"],
        "AppData", "LocalLow",
        "Stress Level Zero",
        "BONELAB",
        "Mods"
    )

def download_with_progress(url, filename, total_size):
    tmp_dir = tempfile.gettempdir()
    safe_name = filename.replace("/", "_").replace("\\", "_")
    path = os.path.join(tmp_dir, safe_name)

    with requests.get(url, stream=True, timeout=30) as r:
        r.raise_for_status()
        with open(path, "wb") as f, tqdm(
            total=total_size if total_size > 0 else None,
            unit="b",
            unit_scale=True,
            desc=Fore.CYAN + "качает",
            ncols=80,
            colour="green"
        ) as bar:
            for chunk in r.iter_content(8192):
                if chunk:
                    f.write(chunk)
                    if bar:
                        bar.update(len(chunk))

    return path

def get_zip_root_folder(zip_path):
    with zipfile.ZipFile(zip_path, "r") as z:
        names = z.namelist()
        roots = {name.split("/")[0] for name in names if "/" in name}
        return list(roots)[0] if len(roots) == 1 else None

def is_mod_installed(mods_dir, folder_name):
    return folder_name and os.path.exists(os.path.join(mods_dir, folder_name))

def extract_zip(zip_path, dest_dir):
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(dest_dir)

# ---------- MAIN ----------
def main():
    global API_KEY

    if getattr(sys, 'frozen', False):
        exe_path = sys.executable
    else:
        exe_path = os.path.abspath(sys.argv[0])

    if len(sys.argv) < 2 or not sys.argv[1].startswith("modman:"):
        register_protocol(exe_path)

    if len(sys.argv) < 2:
        print(Fore.GREEN + "протокол зарегистрирован, запуск без ссылки")
        return

    parsed = parse_modman_url(sys.argv[1])

    if parsed["mode"] == "modio":
        API_KEY = get_api_key()
        mod_info = get_mod_info(parsed["mod_id"])
        file_info = get_mod_file_info(parsed["mod_id"], parsed["file_id"])

        print(Fore.CYAN + "\n------------------------------")
        print(Fore.CYAN + " установка мода")
        print(Fore.CYAN + "------------------------------")
        print(Fore.YELLOW + f"название : {mod_info['name']}")
        print(Fore.WHITE + f"описание : {mod_info['summary']}")
        print(Fore.MAGENTA + f"файл     : {file_info['filename']}")
        print(Fore.BLUE + f"размер   : {human_size(file_info['filesize'])}")
        print(Fore.CYAN + "------------------------------")

        if input(Fore.YELLOW + "установить? (y/n): ").lower() != "y":
            return

        zip_path = download_with_progress(
            file_info["download_url"],
            file_info["filename"],
            file_info["filesize"]
        )

        if file_info.get("md5"):
            if input("проверить хеш? (y/n): ").lower() == "y":
                print("считаю md5...")
                local_md5 = md5_file(zip_path)

                print("md5 (local) :", local_md5)
                print("md5 (mod.io):", file_info["md5"])

                if local_md5.lower() != file_info["md5"].lower():
                    raise RuntimeError("хеш не совпадает, файл битый или подменён")
                else:
                    print("хеш совпадает, всё ок")


    else:
        print(Fore.CYAN + "\n------------------------------")
        print(Fore.CYAN + " установка мода (direct_url)")
        print(Fore.CYAN + "------------------------------")
        print(Fore.MAGENTA + f"файл : {parsed['filename']}")
        print(Fore.CYAN + "------------------------------")

        if input(Fore.YELLOW + "установить? (y/n): ").lower() != "y":
            return

        zip_path = download_with_progress(
            parsed["direct_url"],
            parsed["filename"],
            parsed["filesize"]
        )

    mods_dir = get_bonelab_mods_dir()
    os.makedirs(mods_dir, exist_ok=True)

    root_folder = get_zip_root_folder(zip_path)

    if root_folder and is_mod_installed(mods_dir, root_folder):
        print(Fore.YELLOW + "мод уже установлен:", root_folder)
        if input(Fore.YELLOW + "обновить? (y/n): ").lower() != "y":
            os.remove(zip_path)
            return
        shutil.rmtree(os.path.join(mods_dir, root_folder))

    print(Fore.CYAN + "распаковываю...")
    extract_zip(zip_path, mods_dir)
    os.remove(zip_path)

    print(Fore.GREEN + "готово.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(Fore.RED + "что-то пошло по пизде:")
        print(Fore.RED + str(e))
