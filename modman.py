import sys
import os
import zipfile
import requests
import tempfile
import shutil
import threading
import hashlib
import configparser
import io
from urllib.parse import urlparse, parse_qs, unquote
import urllib.request
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk  # Added Pillow for processing the mod logo image

# ---------- CONSTANTS ----------
GAME_ID = 3809
API_KEY = None

BG        = "#0f1115"  # Deep slate off-black
BG2       = "#171a21"  # Dark charcoal container fill
ACCENT    = "#00f59b"  # Mod.io vibrant mint/cyan primary
ACCENT2   = "#00b0ff"  # Electric blue metadata highlight
FG        = "#f1f5f9"  # Crisp slate white for headers
FG_DIM    = "#94a3b8"  # Muted steel gray for descriptions
SUCCESS   = "#10b981"  # Emerald green
DANGER    = "#ef4444"  # Crimson red
FONT_MONO = ("Consolas", 10)
FONT_UI   = ("Segoe UI", 10)
FONT_TITLE= ("Segoe UI", 14, "bold")

# ---------- HASHING ----------
def md5_file(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

# ---------- PROTOCOL REGISTRATION ----------
try:
    import winreg
    def register_protocol(exe_path):
        key_path = r"Software\Classes\modman"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValue(key, "", winreg.REG_SZ, "URL:ModMan Protocol")
            winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path + r"\shell\open\command") as key:
            winreg.SetValue(key, "", winreg.REG_SZ, f"\"{exe_path}\" \"%1\"")
except ImportError:
    def register_protocol(exe_path):
        pass  # non-Windows

# ---------- CONFIG ----------
def get_config_path():
    config_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "ModMan")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "config.ini")

def load_api_key():
    config_path = get_config_path()
    config = configparser.ConfigParser()
    if os.path.exists(config_path):
        config.read(config_path)
        if "modio" in config and "api_key" in config["modio"]:
            return config["modio"]["api_key"]
    return None

def save_api_key(api_key):
    config_path = get_config_path()
    config = configparser.ConfigParser()
    config["modio"] = {"api_key": api_key}
    with open(config_path, "w") as f:
        config.write(f)

# ---------- UTILS ----------
def human_size(size):
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"

def parse_modman_url(url: str):
    parsed = urlparse(url)
    if parsed.scheme != "modman":
        raise ValueError("Invalid protocol (expected modman://)")
    params = parse_qs(parsed.query)
    
    # Collection processing path
    if "collection" in params:
        return {"mode": "collection", "collection_id": params["collection"][0]}
        
    if "direct_url" in params:
        direct_url = unquote(params["direct_url"][0])
        if not direct_url.startswith(("http://", "https://")):
            raise ValueError("direct_url must be http/https")
        filename = params.get("name", [os.path.basename(urlparse(direct_url).path) or "mod.zip"])[0]
        filesize = int(params.get("size", [0])[0])
        return {"mode": "direct", "direct_url": direct_url, "filename": filename, "filesize": filesize}
        
    mod_id  = params.get("id",   [None])[0]
    file_id = params.get("file", [None])[0]
    if not mod_id or not file_id:
        raise ValueError("Missing mod id, file id, or collection id in URL")
    return {"mode": "modio", "mod_id": mod_id, "file_id": file_id}

# ---------- MOD.IO API ----------
def get_mod_info(mod_id):
    url = f"https://g-3809.modapi.io/v1/games/{GAME_ID}/mods/{mod_id}"
    r = requests.get(url, params={"api_key": API_KEY}, timeout=10)
    r.raise_for_status()
    data = r.json()
    
    logo_url = None
    if "logo" in data and isinstance(data["logo"], dict):
        logo_url = data["logo"].get("thumb_320x180") or data["logo"].get("original")

    return {
        "name": data.get("name", "Unknown"), 
        "summary": data.get("summary", ""),
        "logo_url": logo_url
    }

def get_mod_file_info(mod_id, file_id):
    url = f"https://g-3809.modapi.io/v1/games/{GAME_ID}/mods/{mod_id}/files/{file_id}"
    r = requests.get(url, params={"api_key": API_KEY}, timeout=10)
    r.raise_for_status()
    data = r.json()
    return {
        "filename":     data.get("filename", "mod.zip"),
        "filesize":     data.get("filesize", 0),
        "download_url": data["download"]["binary_url"],
        "md5":          data.get("filehash", {}).get("md5")
    }

def get_collection_details(collection_id):
    """Fetches the meta-details of the collection itself (Name, Summary, Logo)."""
    url = f"https://g-3809.modapi.io/v1/games/{GAME_ID}/collections/{collection_id}"
    r = requests.get(url, params={"api_key": API_KEY}, timeout=10)
    r.raise_for_status()
    return r.json()

def get_collection_mods(collection_id):
    url = f"https://g-3809.modapi.io/v1/games/{GAME_ID}/collections/{collection_id}/mods"
    r = requests.get(url, params={"api_key": API_KEY}, timeout=10)
    r.raise_for_status()
    payload = r.json()
    
    mods_list = []
    for item in payload.get("data", []):
        if not item.get("modfile"):
            continue  # Skip if the mod doesn't have an active file release payload
        
        logo_url = None
        if "logo" in item and isinstance(item["logo"], dict):
            logo_url = item["logo"].get("thumb_320x180") or item["logo"].get("original")
            
        mods_list.append({
            "name": item.get("name", "Unknown Mod"),
            "summary": item.get("summary", ""),
            "logo_url": logo_url,
            "filename": item["modfile"].get("filename", "mod.zip"),
            "filesize": item["modfile"].get("filesize", 0),
            "download_url": item["modfile"]["download"]["binary_url"],
            "md5": item["modfile"].get("filehash", {}).get("md5")
        })
    return mods_list

# ---------- FILESYSTEM ----------
def get_bonelab_mods_dir():
    return os.path.join(
        os.environ.get("USERPROFILE", os.path.expanduser("~")),
        "AppData", "LocalLow", "Stress Level Zero", "BONELAB", "Mods"
    )

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


# ===========================================================
#  GUI
# ===========================================================
class ModManApp(tk.Tk):
    def __init__(self, modman_url=None):
        super().__init__()
        self.modman_url = modman_url
        self.title("ModMan")
        self.geometry("520x560") 
        self.resizable(False, False)
        self.configure(bg=BG)
        self._image_cache = None  
        self._queue = []  # Holds a list of files to download in multiple-mode contexts

        self._build_ui()
        self._apply_styles()

        if modman_url:
            self.after(200, self._start_install_flow)
        else:
            self._show_idle()

    # ---- STYLES ----
    def _apply_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TProgressbar",
                        troughcolor=BG2, bordercolor=BG2,
                        background=ACCENT, lightcolor=ACCENT, darkcolor=ACCENT,
                        thickness=6)

    # ---- LAYOUT ----
    def _build_ui(self):
        header = tk.Frame(self, bg=BG2, height=60)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="MODMAN", font=("Segoe UI Semibold", 12),
                 bg=BG2, fg=ACCENT).pack(side="left", padx=24, pady=12)

        self.btn_key = tk.Button(
            header, text="API Key", font=FONT_UI,
            bg=BG2, fg=FG_DIM, relief="flat", cursor="hand2",
            activebackground=BG2, activeforeground=FG,
            bd=0, highlightthickness=0,
            command=self._prompt_api_key
        )
        self.btn_key.pack(side="right", padx=24)

        body = tk.Frame(self, bg=BG, padx=32, pady=24)
        body.pack(fill="both", expand=True)

        self.lbl_status_badge = tk.Label(body, text="IDLE", font=("Segoe UI", 9, "bold"), 
                                         bg=BG2, fg=FG_DIM, padx=8, pady=2)
        self.lbl_status_badge.pack(anchor="w", pady=(0, 12))

        self.lbl_logo = tk.Label(body, bg=BG)
        self.lbl_logo.pack(anchor="w", pady=(0, 14))

        self.lbl_title = tk.Label(body, text="Waiting for link...",
                                  font=FONT_TITLE, bg=BG, fg=FG, wraplength=450, anchor="w", justify="left")
        self.lbl_title.pack(fill="x")

        self.lbl_summary = tk.Label(body, text="", font=FONT_UI,
                                    bg=BG, fg=FG_DIM, wraplength=450, justify="left", anchor="w")
        self.lbl_summary.pack(fill="x", pady=(6, 0))

        meta_row = tk.Frame(body, bg=BG)
        meta_row.pack(fill="x", pady=(16, 0))

        self.lbl_file  = tk.Label(meta_row, text="", font=FONT_MONO, bg=BG, fg=FG_DIM)
        self.lbl_file.pack(side="left")
        self.lbl_size  = tk.Label(meta_row, text="", font=FONT_MONO, bg=BG, fg=ACCENT2)
        self.lbl_size.pack(side="left", padx=12)

        self.progress_var = tk.IntVar(value=0)
        self.progress = ttk.Progressbar(body, variable=self.progress_var,
                                        maximum=100, length=450)
        self.progress.pack(fill="x", pady=(24, 6))
        
        self.lbl_progress = tk.Label(body, text="", font=FONT_MONO, bg=BG, fg=FG_DIM, anchor="w")
        self.lbl_progress.pack(fill="x")

        btn_row = tk.Frame(body, bg=BG)
        btn_row.pack(fill="x", pady=(24, 0))

        self.btn_install = self._make_btn(btn_row, "Install Mod", ACCENT, self._confirm_install, is_primary=True)
        self.btn_install.pack(side="left")

        self.btn_cancel = self._make_btn(btn_row, "Cancel", BG, self.destroy, fg=FG_DIM)
        self.btn_cancel.pack(side="left", padx=16)

    def _make_btn(self, parent, text, bg, cmd, fg=FG, is_primary=False):
        btn = tk.Button(parent, text=text, font=("Segoe UI Semibold", 10),
                         bg=bg, fg=fg, relief="flat", cursor="hand2",
                         padx=18, pady=6, bd=0, highlightthickness=0,
                         activebackground=ACCENT if is_primary else BG2, 
                         activeforeground="#fff" if is_primary else FG,
                         command=cmd)
        return btn

    def _show_idle(self):
        self.lbl_status_badge.config(text="READY", fg=FG_DIM, bg=BG2)
        self.lbl_title.config(text="No installation target", fg=FG)
        self.lbl_summary.config(text="Launch ModMan via an integrated web download layer or a modman:// link to begin installation.")
        self.lbl_file.config(text="")
        self.lbl_size.config(text="")
        self.lbl_logo.config(image="")
        self._image_cache = None
        self.btn_install.config(state="disabled")
        self.progress_var.set(0)
        self.lbl_progress.config(text="")

    def _prompt_api_key(self):
        key = simpledialog.askstring(
            "mod.io API Key",
            "Enter your mod.io API key:\n(get one at https://mod.io/me/access)",
            parent=self
        )
        if key:
            save_api_key(key.strip())
            global API_KEY
            API_KEY = key.strip()
            messagebox.showinfo("Saved", "API key saved.", parent=self)

    # ---- INSTALL FLOW ----
    def _start_install_flow(self):
        global API_KEY
        try:
            parsed = parse_modman_url(self.modman_url)
        except ValueError as e:
            messagebox.showerror("Bad URL", str(e), parent=self)
            return

        self._parsed = parsed

        if parsed["mode"] in ("modio", "collection"):
            API_KEY = load_api_key()
            if not API_KEY:
                self._prompt_api_key()
                if not API_KEY:
                    messagebox.showerror("No API Key", "An API key is required.", parent=self)
                    return
            
            if parsed["mode"] == "collection":
                threading.Thread(target=self._fetch_collection_info, daemon=True).start()
            else:
                threading.Thread(target=self._fetch_modio_info, daemon=True).start()

        else:  # direct path
            self.lbl_status_badge.config(text="EXTERNAL", fg=ACCENT2, bg=BG2)
            self.lbl_title.config(text=parsed["filename"], fg=FG)
            self.lbl_summary.config(text="Direct package bundle installation from user link configuration.")
            self.lbl_file.config(text=parsed["filename"])
            self.lbl_logo.config(image="")
            self._image_cache = None
            if parsed["filesize"] > 0:
                self.lbl_size.config(text=human_size(parsed["filesize"]))
            
            # Map simple object parameters down into standard collection payload array architecture
            self._queue = [{
                "name": parsed["filename"],
                "filename": parsed["filename"],
                "filesize": parsed["filesize"],
                "download_url": parsed["direct_url"],
                "md5": None
            }]
            self.btn_install.config(state="normal")

    def _fetch_modio_info(self):
        try:
            mod_info  = get_mod_info(self._parsed["mod_id"])
            file_info = get_mod_file_info(self._parsed["mod_id"], self._parsed["file_id"])
            
            self._queue = [{
                "name": mod_info["name"],
                "filename": file_info["filename"],
                "filesize": file_info["filesize"],
                "download_url": file_info["download_url"],
                "md5": file_info["md5"]
            }]

            img_tk = None
            if mod_info["logo_url"]:
                try:
                    req = urllib.request.Request(mod_info["logo_url"], headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=5) as response:
                        img_data = response.read()
                    img_open = Image.open(io.BytesIO(img_data))
                    img_resized = img_open.resize((320, 180), Image.Resampling.LANCZOS)
                    img_tk = ImageTk.PhotoImage(img_resized)
                except Exception:
                    img_tk = None 

            self.after(0, lambda: self._populate_single_info(mod_info, file_info, img_tk))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", str(e), parent=self))

    def _populate_single_info(self, mod_info, file_info, img_tk):
        self.lbl_status_badge.config(text="MOD.IO", fg=ACCENT, bg=BG2)
        if img_tk:
            self._image_cache = img_tk  
            self.lbl_logo.config(image=self._image_cache)
        else:
            self.lbl_logo.config(image="")

        self.lbl_title.config(text=mod_info["name"], fg=FG)
        self.lbl_summary.config(text=mod_info["summary"] or "No remote summary description metadata provided.")
        self.lbl_file.config(text=file_info["filename"])
        self.lbl_size.config(text=human_size(file_info["filesize"]))
        self.btn_install.config(state="normal")

    def _fetch_collection_info(self):
            try:
                collection_id = self._parsed["collection_id"]
                
                # 1. Fetch collection structural metadata
                coll_meta = get_collection_details(collection_id)
                
                # 2. Fetch target mods list queue
                mods = get_collection_mods(collection_id)
                if not mods:
                    raise RuntimeError("The specified collection is empty or contains no valid active files.")
                
                self._queue = mods
                total_size = sum(m["filesize"] for m in mods)
                
                # Extract collection's native cover image
                img_tk = None
                logo_data = coll_meta.get("logo")
                logo_url = logo_data.get("thumb_320x180") or logo_data.get("original") if isinstance(logo_data, dict) else None
                
                # Fallback to first mod logo if collection doesn't have one
                if not logo_url and mods[0]["logo_url"]:
                    logo_url = mods[0]["logo_url"]

                if logo_url:
                    try:
                        req = urllib.request.Request(logo_url, headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(req, timeout=5) as response:
                            img_data = response.read()
                        img_open = Image.open(io.BytesIO(img_data))
                        img_resized = img_open.resize((320, 180), Image.Resampling.LANCZOS)
                        img_tk = ImageTk.PhotoImage(img_resized)
                    except Exception:
                        img_tk = None

                self.after(0, lambda: self._populate_collection_info(coll_meta, len(mods), total_size, img_tk))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e), parent=self))

    def _populate_collection_info(self, coll_meta, mod_count, total_size, img_tk):
        self.lbl_status_badge.config(text="COLLECTION", fg=ACCENT, bg=BG2)
        if img_tk:
            self._image_cache = img_tk
            self.lbl_logo.config(image=self._image_cache)
        else:
            self.lbl_logo.config(image="")
            
        # UI now renders beautiful real-world metadata names and descriptions
        self.lbl_title.config(text=coll_meta.get("name", "Unknown Collection"), fg=FG)
        self.lbl_summary.config(text=coll_meta.get("summary") or "This action will deploy all mods contained inside this collection.")
        self.lbl_file.config(text=f"{mod_count} mods queued")
        self.lbl_size.config(text=human_size(total_size))
        self.btn_install.config(text="Install Collection", state="normal")

    def _confirm_install(self):
        self.btn_install.config(state="disabled")
        self.btn_cancel.config(state="disabled")
        threading.Thread(target=self._do_batch_install, daemon=True).start()

    def _do_batch_install(self):
        try:
            mods_dir = get_bonelab_mods_dir()
            os.makedirs(mods_dir, exist_ok=True)
            
            total_mods = len(self._queue)
            
            for index, item in enumerate(self._queue, start=1):
                url = item["download_url"]
                filename = item["filename"]
                filesize = item["filesize"]
                expected_md5 = item["md5"]
                mod_name = item["name"]
                
                # Update header indicators dynamically to display granular queue progress
                self.after(0, lambda n=mod_name, i=index, t=total_mods: self.lbl_title.config(
                    text=f"[{i}/{t}] {n}", fg=FG
                ))
                
                zip_path = self._download(url, filename, filesize, index, total_mods)
                
                if expected_md5:
                    if md5_file(zip_path).lower() != expected_md5.lower():
                        raise RuntimeError(f"Data Integrity Check Failed on '{mod_name}': MD5 mismatch.")
                        
                root_folder = get_zip_root_folder(zip_path)
                if root_folder and is_mod_installed(mods_dir, root_folder):
                    answer = self._ask_update(root_folder)
                    if not answer:
                        os.remove(zip_path)
                        continue  # Skip deployment if the conflict dialog yields a manual refusal
                    shutil.rmtree(os.path.join(mods_dir, root_folder))
                    
                extract_zip(zip_path, mods_dir)
                os.remove(zip_path)
                
            self.after(0, self._done)
        except Exception as e:
            self.after(0, lambda: self._error(str(e)))

    def _download(self, url, filename, total_size, item_idx=1, total_items=1):
        tmp_dir = tempfile.gettempdir()
        safe_name = filename.replace("/", "_").replace("\\", "_")
        path = os.path.join(tmp_dir, safe_name)

        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            if total_size <= 0:
                total_size = int(r.headers.get("Content-Length", 0))

            downloaded = 0
            with open(path, "wb") as f:
                for chunk in r.iter_content(8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            pct = int(downloaded * 100 / total_size)
                            label = f"Mod {item_idx}/{total_items} | {human_size(downloaded)} of {human_size(total_size)}"
                            self.after(0, lambda p=pct, l=label: self._update_progress(p, l))
        return path

    def _update_progress(self, pct, label):
        self.progress_var.set(pct)
        self.lbl_progress.config(text=label)

    def _ask_update(self, folder_name):
        result = [False]
        event  = threading.Event()

        def ask():
            result[0] = messagebox.askyesno(
                "Conflict Detected",
                f'"{folder_name}" is currently active on disk.\nOverwrite local installation entries?',
                parent=self
            )
            event.set()

        self.after(0, ask)
        event.wait()
        return result[0]

    def _done(self):
        self.lbl_status_badge.config(text="COMPLETED", fg=SUCCESS, bg=BG2)
        self.lbl_title.config(text="Installation Complete", fg=SUCCESS)
        self.lbl_file.config(text="All targets deployed successfully")
        self.progress_var.set(100)
        self.btn_cancel.config(text="Done!", state="normal")

    def _error(self, msg):
        self.lbl_status_badge.config(text="CRITICAL FAILURE", fg=DANGER, bg=BG2)
        self.lbl_title.config(text="Deployment Terminated", fg=DANGER)
        self.btn_cancel.config(state="normal")
        self.btn_install.config(state="normal")
        messagebox.showerror("Error", msg, parent=self)


# ===========================================================
#  ENTRY POINT
# ===========================================================
def main():
    if getattr(sys, "frozen", False):
        exe_path = sys.executable
    else:
        exe_path = os.path.abspath(sys.argv[0])

    url = None
    if len(sys.argv) >= 2 and sys.argv[1].startswith("modman:"):
        url = sys.argv[1]
    else:
        register_protocol(exe_path)

    app = ModManApp(modman_url=url)
    app.mainloop()


if __name__ == "__main__":
    main()
