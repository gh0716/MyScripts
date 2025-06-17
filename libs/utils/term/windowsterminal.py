import json
import os
import sys

DEFAULT_TERMINAL_FONT_SIZE = 9


def setup_windows_terminal(
    font_size=DEFAULT_TERMINAL_FONT_SIZE,
    opacity=1.0,
):
    if sys.platform != "win32":
        raise Exception("OS not supported.")

    CONFIG_FILE = os.path.expandvars(
        r"%LOCALAPPDATA%\Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json"
    )

    with open(CONFIG_FILE, "r") as f:
        lines = f.read().splitlines()

    lines = [x for x in lines if not x.lstrip().startswith("//")]
    data = json.loads("\n".join(lines))

    updated = False

    settings = {
        "initialCols": 120,
        "initialRows": 40,
        "disableAnimations": True,
    }
    for k, v in settings.items():
        if k not in data or data[k] != v:
            data[k] = v
            updated = True

    # Default font size and color scheme
    default_profile = {
        "colorScheme": "Dracula",
        "font": {"face": "Consolas", "size": font_size},
    }

    if opacity < 1.0:
        default_profile["useAcrylic"] = True
        default_profile["acrylicOpacity"] = opacity

    if default_profile != data["profiles"]["defaults"]:
        data["profiles"]["defaults"] = default_profile
        updated = True

    # Customize selection color
    if not any(x["name"] == "Dracula" for x in data["schemes"]):
        data["schemes"].append(
            {
                "name": "Dracula",
                "cursorColor": "#F8F8F2",
                "selectionBackground": "#44475A",
                "background": "#282A36",
                "foreground": "#F8F8F2",
                "black": "#21222C",
                "blue": "#BD93F9",
                "cyan": "#8BE9FD",
                "green": "#50FA7B",
                "purple": "#FF79C6",
                "red": "#FF5555",
                "white": "#F8F8F2",
                "yellow": "#F1FA8C",
                "brightBlack": "#6272A4",
                "brightBlue": "#D6ACFF",
                "brightCyan": "#A4FFFF",
                "brightGreen": "#69FF94",
                "brightPurple": "#FF92DF",
                "brightRed": "#FF6E6E",
                "brightWhite": "#FFFFFF",
                "brightYellow": "#FFFFA5",
            }
        )
        updated = True

    if updated:
        # Only update when config file is changed
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=4)
