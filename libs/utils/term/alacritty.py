import os
import shutil
import sys
from pathlib import Path
from typing import Optional, Tuple

from _shutil import file_is_old


def is_alacritty_installed():
    return shutil.which("alacritty")


def wrap_args_alacritty(
    args,
    borderless: bool = False,
    font_size: Optional[int] = None,
    font: Optional[str] = None,
    padding: Optional[int] = None,
    position: Optional[Tuple[int, int]] = None,
    title: Optional[str] = None,
    **kwargs,
):
    assert isinstance(args, list)

    if not is_alacritty_installed():
        raise FileNotFoundError("Alacritty is not installed.")

    # Copy alacritty config file
    # https://github.com/alacritty/alacritty/blob/master/alacritty.yml
    if sys.platform == "win32":
        dest_config = os.path.expandvars(r"%APPDATA%\alacritty\alacritty.yml")
    else:
        dest_config = os.path.expanduser("~/.config/alacritty/alacritty.yml")
    os.makedirs(os.path.dirname(dest_config), exist_ok=True)
    src_config = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "settings"
        / "alacritty.yml"
    ).resolve()
    if file_is_old(src_config, dest_config):
        shutil.copy(src_config, dest_config)

    out = ["alacritty"]

    # Specify option key value pairs
    options = []
    if font_size is not None:
        options += [
            f"font.size={font_size}",
        ]
    if font is not None:
        options += [f"font.normal.family={font}"]
    if borderless:
        options += ["window.decorations=none"]
    if position:
        options += [
            f"window.position.x={position[0]}",
            f"window.position.y={position[1]}",
        ]
    if padding is not None:
        options += [f"window.padding.x={padding}", f"window.padding.y={padding}"]
    if len(options) > 0:
        out += ["-o"] + options

    if title:
        out += ["--title", title]

    if sys.platform == "win32":
        # HACK: Alacritty handles spaces in a weird way: if arg has space in it,
        # must double quote it. Backslash will need to be replaced with 2 backslashes otherwise they'll disappear for some reason.
        args = ['"' + x.replace("\\", "\\\\") + '"' if " " in x else x for x in args]

    out += ["-e"] + args
    return out
