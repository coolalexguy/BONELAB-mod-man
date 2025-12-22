# ModMan – BONELAB mod installer via `modman://` links
## View live demo on [this telegram bot](https://t.me/modionetbot).
A small Windows utility that lets you install **BONELAB** mods directly from `modman://` links (mod.io deep links), similar to how Steam or Nexus Mod Manager works.

When you click a `modman://` link, ModMan:
- Fetches mod metadata from **mod.io**
- Downloads the selected mod file
- Extracts it into your BONELAB Mods folder
- Optionally updates an already installed mod




---

## Features

- 🔗 Custom `modman://` URL protocol support  
- 📦 Downloads mods directly from mod.io  
- 📂 Auto-detects BONELAB Mods directory  
- ⏳ Progress bar while downloading  
- 🔁 Optional overwrite when updating mods  
- 🧑 No admin rights required (HKCU-only registry changes)

---

## How it works

1. On first run, ModMan **registers the `modman://` protocol** for the current user.
2. Clicking a `modman://?id=MOD_ID&file=FILE_ID` link launches ModMan.
3. Mod metadata is fetched via the mod.io API.
4. The mod ZIP is downloaded and extracted to:

`%USERPROFILE%\AppData\LocalLow\Stress Level Zero\BONELAB\Mods`


---

## Usage

### First run (manual)

```bash
ModMan.exe
```

This registers the protocol and exits.
---
# Installing a mod

Click a modman:// link, for example:

`modman://install?id=12345&file=67890`
ModMan will prompt you before downloading and installing anything.

## Is this a virus / RAT?

**No.**

This tool:

- Does **not** open remote shells  
- Does **not** listen for commands  
- Does **not** persist beyond protocol registration  
- Does **not** access unrelated files or folders  

All network requests go only to **mod.io API endpoints** and the mod file download URL.

You are encouraged to **read the source code** and build the executable yourself.

---

## Security notes

- This tool downloads and extracts ZIP files from mod.io.
- ZIP contents are trusted as provided by mod authors.
- ZIP path validation is recommended for future versions.

If you don’t trust a mod, **don’t install it**.

---

## Requirements

- Windows 10 / 11  
- Python 3.10+ (for running from source)  
- Internet connection  

---

## Building

Example (PyInstaller):

```bash
pyinstaller --onefile modman.py
```

# Disclaimer

This project is not affiliated with Stress Level Zero or mod.io.
Use at your own risk. You are responsible for the mods you install.
