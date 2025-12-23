# ModMan Protocol Reference (modman://)

This document describes the custom **modman:// URL protocol** used by ModMan to install BONELAB mods via deep links (for example from browsers, Telegram, or other applications).

The protocol is registered on Windows and handled by the ModMan executable.

---

## Overview

The modman:// protocol supports two modes:

1. mod.io mode – install a mod directly from mod.io using a mod ID and file ID
2. direct URL mode – install a mod from a direct HTTP or HTTPS ZIP file URL

---

## General Format

The general format of a ModMan link is:

`modman://download?<parameters>`

* Scheme: modman
* Action: download
* Parameters: URL query parameters

---
## Mode 1: mod.io download

Installs a mod using the mod.io API.

### Required parameters

| Parameter | Description    |
| --------- | -------------- |
| id        | mod.io mod ID  |
| file      | mod.io file ID |

---

### Example

| Example modman:// link                |
| ------------------------------------- |
| modman://download?id=12345&file=67890 |

---

### Behavior

| Step | Description                                                        |
| ---: | ------------------------------------------------------------------ |
|    1 | Prompts the user for a mod.io API key if not already configured    |
|    2 | Fetches mod metadata from mod.io                                   |
|    3 | Downloads the specified mod file                                   |
|    4 | Optionally verifies the file using the MD5 hash provided by mod.io |
|    5 | Extracts the mod into the BONELAB Mods directory                   |
|    6 | Prompts before overwriting an existing mod                         |

---



## Mode 2: Direct URL download

Installs a mod directly from a ZIP file hosted at a URL.

---

### Required parameters

| Parameter  | Description                                          |
| ---------- | ---------------------------------------------------- |
| direct_url | URL-encoded HTTP or HTTPS URL pointing to a ZIP file |

---

### Optional parameters

| Parameter | Description                                             |
| --------- | ------------------------------------------------------- |
| name      | Filename to use when saving the ZIP                     |
| size      | Expected file size in bytes (used for progress display) |

---

### Examples

| Usage                    | modman:// link                                                                                      |
| ------------------------ | --------------------------------------------------------------------------------------------------- |
| Basic                    | modman://download?direct_url=https%3A%2F%2Fexample.com%2Fmod.zip                                    |
| With optional parameters | modman://download?direct_url=https%3A%2F%2Fexample.com%2Fmod.zip&name=example_mod.zip&size=52428800 |

---

### Behavior

| Step | Description                                      |
| ---: | ------------------------------------------------ |
|    1 | Downloads the ZIP file from the provided URL     |
|    2 | Displays a progress bar (if size is provided)    |
|    3 | Extracts the mod into the BONELAB Mods directory |
|    4 | Prompts before overwriting an existing mod       |



---

## Hash Verification

### mod.io files

If the mod.io API provides a file hash:

* The user is asked whether they want to verify the file
* A local MD5 hash is calculated
* The local hash is compared against the mod.io filehash
* Installation is aborted if the hashes do not match

### Direct URL files

* No hash is provided automatically
* Hash verification is optional and manual

---

## BONELAB Mods Directory

Mods are installed into the following directory:

%USERPROFILE%\AppData\LocalLow\Stress Level Zero\BONELAB\Mods

---

## Protocol Registration

* The protocol is registered under the current user

* Registry path:
  HKEY_CURRENT_USER\Software\Classes\modman

* The handler command launches the ModMan executable with the URL as an argument

* Protocol registration occurs automatically when the ModMan executable is run manually

---

## Supported Use Cases

* Clicking modman:// links in web browsers
* Using deep links from Telegram or Discord
* Launching installs via Win + R
* Automation or scripting
* Mod distribution without a custom installer

---

## Notes

* The protocol is Windows-only
* The ModMan executable must be installed and registered
* URLs must be properly URL-encoded
* ZIP files must contain a valid BONELAB mod structure

---

## Example Links

`modman://download?id=3809&file=123456`

`modman://download?direct_url=https%3A%2F%2Fcdn.example.com%2Fbonelab_mod.zip`

---

## Disclaimer

The modman:// protocol performs no sandboxing.
Only install mods from sources you trust.
