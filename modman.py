import sys
import os
import zipfile
import requests
import tempfile
import shutil
from urllib.parse import urlparse, parse_qs
from tqdm import tqdm
import winreg
import ctypes
import configparser


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False
    
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
# ==========================================

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

    # First run / missing key
    print("ключа нету блять!")
    print("введи ключ :")
    api_key = input("> ").strip()

    if not api_key:
        raise RuntimeError("нужен ключ.")

    config["modio"] = {"api_key": api_key}
    with open(config_path, "w") as f:
        config.write(f)

    print("сохранил ключ блять.")
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
    mod_id = params.get("id", [None])[0]
    file_id = params.get("file", [None])[0]

    if not mod_id or not file_id:
        raise ValueError("нет id или fileid")

    return mod_id, file_id


# ---------- MOD.IO API ----------

def get_mod_info(mod_id):
    url = f"https://g-3809.modapi.io/v1/games/{GAME_ID}/mods/{mod_id}"
    r = requests.get(url, params={"api_key": API_KEY}, timeout=10)
    r.raise_for_status()
    data = r.json()
    return {
        "name": data.get("name", "чет ты залупу запустил какуюто!"),
        "summary": data.get("summary", "описания чет нет")
    }


def get_mod_file_info(mod_id, file_id):
    url = f"https://g-3809.modapi.io/v1/games/{GAME_ID}/mods/{mod_id}/files/{file_id}"
    r = requests.get(url, params={"api_key": API_KEY}, timeout=10)
    r.raise_for_status()
    data = r.json()
    return {
        "filename": data.get("filename", "mod.zip"),
        "filesize": data.get("filesize", 0),
        "download_url": data["download"]["binary_url"]
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
            total=total_size,
            unit="b",
            unit_scale=True,
            desc="качает",
            ncols=80
        ) as bar:
            for chunk in r.iter_content(8192):
                if chunk:
                    f.write(chunk)
                    bar.update(len(chunk))

    return path


def get_zip_root_folder(zip_path):
    with zipfile.ZipFile(zip_path, "r") as z:
        names = z.namelist()
        roots = {name.split("/")[0] for name in names if "/" in name}
        return list(roots)[0] if len(roots) == 1 else None


def is_mod_installed(mods_dir, folder_name):
    if not folder_name:
        return False
    return os.path.exists(os.path.join(mods_dir, folder_name))


def extract_zip(zip_path, dest_dir):
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(dest_dir)


# ---------- MAIN ----------

def main():
    exe_path = os.path.abspath(sys.argv[0])
    global API_KEY
    API_KEY = get_api_key()

    # auto-register protocol (no admin needed)
    register_protocol(exe_path)

    if len(sys.argv) < 2:
        print("запуск без ссылки, протокол зарегистрирован")
        return

    try:
        mod_id, file_id = parse_modman_url(sys.argv[1])

        mod_info = get_mod_info(mod_id)
        file_info = get_mod_file_info(mod_id, file_id)

        print("\n------------------------------")
        print(" установка мода))")
        print("------------------------------")
        print(f"название : {mod_info['name']}")
        print(f"описание : {mod_info['summary']}")
        print(f"файл     : {file_info['filename']}")
        print(f"размер   : {human_size(file_info['filesize'])}")
        print("------------------------------")

        choice = input("установить это дерьмо? (y/n): ").strip().lower()
        if choice != "y":
            print("ну и иди нахуй хрябум.")
            return

        zip_path = download_with_progress(
            file_info["download_url"],
            file_info["filename"],
            file_info["filesize"]
        )

        mods_dir = get_bonelab_mods_dir()
        os.makedirs(mods_dir, exist_ok=True)

        root_folder = get_zip_root_folder(zip_path)

        if root_folder and is_mod_installed(mods_dir, root_folder):
            print("\nэтот мод уже стоит долбаеб!")
            print(f"папка: {root_folder}")
            overwrite = input("обновить? (y/n): ").strip().lower()
            if overwrite != "y":
                os.remove(zip_path)
                return

            print("удаляю старое.")
            shutil.rmtree(os.path.join(mods_dir, root_folder))

        print("\nраспаковываю файлы...")
        extract_zip(zip_path, mods_dir)
        os.remove(zip_path)

        print("\nготово.")

    except Exception as e:
        print("\nчто-то пошло по пизде.")
        print(e)


if __name__ == "__main__":
    main()
