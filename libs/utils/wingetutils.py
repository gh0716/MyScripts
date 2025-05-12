import json
import logging
import os
import subprocess

from scripting.path import get_data_dir


def get_export_file() -> str:
    return os.path.join(get_data_dir(), "winget_export.json")


_WINGET_EXEC = r"C:\Users\rossning92\AppData\Local\Microsoft\WindowsApps\winget.exe"


def export_packages():
    subprocess.check_call(
        [_WINGET_EXEC, "export", get_export_file()],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def is_package_installed(pkg: str):
    logging.debug(f"Checking if winget package {pkg} is installed")

    export_file = get_export_file()
    if not os.path.exists(export_file):
        export_packages()

    with open(export_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    matched_packages = list(
        filter(lambda p: p["PackageIdentifier"] == pkg, data["Sources"][0]["Packages"])
    )
    return matched_packages != 0


def install_package(pkg: str, upgrade=False, force_install=True):
    if not is_package_installed(pkg) or force_install:
        args = [
            _WINGET_EXEC,
            "install",
            "-e",
            "--id",
            pkg,
            "--accept-source-agreements",
            "--accept-package-agreements",
        ]
        subprocess.check_call(args)
        export_packages()
