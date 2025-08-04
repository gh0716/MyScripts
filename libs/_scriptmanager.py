import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from typing import Callable, Dict, Iterator, List, Optional, Set, Tuple

from _script import (
    Script,
    execute_script_autorun,
    get_all_script_access_time,
    get_all_scripts,
)
from _shutil import (
    clear_env_var_explorer,
    get_ahk_exe,
    pause,
    refresh_env_vars,
    start_process,
    update_env_var_explorer,
)
from _term import clear_terminal
from scripting.path import get_data_dir, get_my_script_root, get_script_history_file
from utils.jsonutil import load_json, save_json
from utils.template import render_template_file
from utils.tmux import is_in_tmux

MYSCRIPT_GLOBAL_HOTKEY = os.path.join(get_data_dir(), "GlobalHotkey.ahk")


def add_keyboard_hooks(keyboard_hooks):
    if sys.platform != "linux":
        import keyboard

        keyboard.unhook_all()
        for hotkey, func in keyboard_hooks.items():
            keyboard.add_hotkey(hotkey, func)


def register_global_hotkeys_sxhkd(scripts: List[Script]):
    s = (
        "control+q\n"
        "  wmctrl -a MyTerminal"
        f' || alacritty -e "{get_my_script_root()}/myscripts"\n\n'
    )

    replacements = {
        "win+": "super+",
        "enter": "Return",
        "tab": "Tab",
        "[": "bracketleft",
        "]": "bracketright",
        ",": "comma",
        ".": "period",
    }
    f_key_pattern = re.compile(r"\bf(\d+)\b")

    def replace_hotkey(hotkey: str) -> str:
        for key, value in replacements.items():
            hotkey = hotkey.replace(key, value)
        hotkey = f_key_pattern.sub(r"F\1", hotkey)
        return hotkey

    for script in scripts:
        hotkey_chain = script.cfg["globalHotkey"]
        if hotkey_chain and script.is_supported():
            hotkey_def = ";".join(
                [replace_hotkey(hotkey.lower()) for hotkey in hotkey_chain.split()]
            )
            s += "{}\n".format(hotkey_def)
            s += (
                "  python3"
                f" {get_my_script_root()}/bin/start_script.py"
                f" {script.script_path}\n\n"
            )

    with open(os.path.expanduser("~/.sxhkdrc"), "w") as f:
        f.write(s)
    if subprocess.call(["pgrep", "sxhkd"], stdout=subprocess.DEVNULL) == 0:
        logging.debug("Reload sxhkd config")
        subprocess.call(["pkill", "-USR1", "sxhkd"])  # reload config
    else:
        logging.debug("Start sxhkd daemon")
        start_process(["sxhkd", "-c", os.path.expanduser("~/.sxhkdrc")])


def register_global_hotkeys_sway(scripts: List[Script]):
    def replace_hotkey(hotkey: str) -> str:
        replacements = {
            "win+": "Mod4+",
            "ctrl+": "Control+",
            "alt+": "Mod1+",
            "[": "bracketleft",
            "]": "bracketright",
            ",": "comma",
            ".": "period",
        }
        for key, value in replacements.items():
            hotkey = hotkey.replace(key, value)
        return hotkey

    for script in scripts:
        hotkey_chain = script.cfg["globalHotkey"]
        if hotkey_chain and script.is_supported():
            hotkey_chain_arr = [
                replace_hotkey(hotkey.lower()) for hotkey in hotkey_chain.split()
            ]

            if len(hotkey_chain_arr) == 1:
                logging.info(
                    f"Register global hotkey '{hotkey_chain_arr[0]}' for script '{script.name}'"
                )
                args = [
                    "sway",
                    "bindsym",
                    hotkey_chain_arr[0],
                    "exec",
                    "python3",
                    f"{get_my_script_root()}/bin/start_script.py",
                    script.script_path,
                ]
                out = subprocess.check_output(args)
                if not json.loads(out)[0]["success"]:
                    raise RuntimeError(
                        f"Failed to register hotkey: {str(out)} for script: {script.name}"
                    )
            else:
                logging.warning(
                    f"Hotkey chain '{hotkey_chain}' is not supported on sway, only single hotkey is supported."
                )


def register_global_hotkeys_linux(scripts: List[Script]):
    if os.environ.get("SWAYSOCK"):
        register_global_hotkeys_sway(scripts)
    elif shutil.which("sxhkd"):
        register_global_hotkeys_sxhkd(scripts)


def _to_ahk_hotkey(hotkey: str):
    return (
        hotkey.lower()
        .replace("ctrl+", "^")
        .replace("alt+", "!")
        .replace("shift+", "+")
        .replace("win+", "#")
    )


def register_global_hotkeys_win(scripts: List[Script]):
    def wrap_hotkey_def_with_context_expr(hotkey_def: str, expr: str):
        return f"#If {expr}\n    {hotkey_def}\n#If\n\n"

    default_hotkey_context = 'not WinActive("ahk_exe vncviewer.exe")'
    hotkeys = ""
    match_clipboard = []
    first_hotkey_defined: Set[str] = set()

    for script in scripts:
        function_def = f'StartScript("{script.name}", "{script.script_path}")'
        hotkey_chain = script.cfg["globalHotkey"]
        if hotkey_chain and script.is_supported():
            hotkey_array = hotkey_chain.split()
            if len(hotkey_array) == 1:
                htk = _to_ahk_hotkey(hotkey_array[0])
                hotkeys += wrap_hotkey_def_with_context_expr(
                    f"{htk}::{function_def}", default_hotkey_context
                )
            elif len(hotkey_array) == 2:
                # First hotkey in the key combination
                key1 = _to_ahk_hotkey(hotkey_array[0])
                if key1 not in first_hotkey_defined:
                    hotkeys += wrap_hotkey_def_with_context_expr(
                        f"{key1}::return", default_hotkey_context
                    )

                first_hotkey_defined.add(key1)

                # Second hotkey in the key combination
                key2 = _to_ahk_hotkey(hotkey_array[1])
                hotkeys += wrap_hotkey_def_with_context_expr(
                    f"{key2}::{function_def}",
                    f'{default_hotkey_context} and A_PriorHotkey = "{key1}"',
                )

            else:
                raise Exception("Only support chaining two hotkeys.")

        patt = script.cfg["matchClipboard"]
        if patt:
            match_clipboard.append([patt, script.name, script.script_path])

    match_clipboard = sorted(match_clipboard, key=lambda x: x[1])  # sort by name

    render_template_file(
        os.path.join(get_my_script_root(), "GlobalHotkey.ahk"),
        MYSCRIPT_GLOBAL_HOTKEY,
        context={
            "PYTHON_EXEC": sys.executable,
            "START_SCRIPT": os.path.abspath("bin/start_script.py"),
            "RUN_SCRIPT": os.path.abspath("bin/run_script.py"),
            "HOTKEYS": hotkeys,
            "MATCH_CLIPBOARD": str(match_clipboard)
            .replace("\\\\", "\\")
            .replace("'", '"'),
        },
    )

    subprocess.Popen(
        [get_ahk_exe(), MYSCRIPT_GLOBAL_HOTKEY], close_fds=True, shell=True
    )


def execute_script(
    script: Script,
    args: Optional[List[str]] = None,
    cd=True,
    close_on_exit=None,
    out_to_file: Optional[str] = None,
    run_script_and_quit=False,
    run_script_local=False,
):
    refresh_env_vars()

    args_: List[str]
    if args is None:
        if not run_script_and_quit:
            args_ = update_env_var_explorer()
        else:
            args_ = []
    else:
        args_ = args

    # Save last executed script
    save_json(get_script_history_file(), {"file": script.script_path, "args": args_})

    if not run_script_and_quit:
        clear_terminal()

    success = script.execute(
        args=args_,
        cd=cd,
        close_on_exit=close_on_exit,
        new_window=False if run_script_and_quit else None,
        restart_instance=True,
        out_to_file=out_to_file,
        run_script_local=run_script_local,
    )
    if not success:
        pause()


def register_global_hotkeys_mac(scripts: List[Script]):
    if not shutil.which("skhd"):
        logging.warning("skhd is not installed, skip global hotkey registration")
        return

    error_log_file = f"/tmp/skhd_{os.getlogin()}.err.log"
    if os.path.exists(error_log_file):
        with open(error_log_file, "r") as f:
            err = f.read().strip()
        if err:
            logging.error("Last skhd error: " + err)

    # Clear /tmp/skhd_$USER.err.log
    with open(error_log_file, "w") as f:
        f.write("")

    s = f'ctrl-q : {sys.executable} {get_my_script_root()}/bin/run_script.py r/activate_window.py MyTerminal || open -n "{get_my_script_root()}/myscripts"\n\n'

    replacements = {
        "win+": "cmd+",
        "enter": "return",
        "[": "0x21",
        "]": "0x1E",
        ",": "0x2B",
        ".": "0x2F",
        "del": "backspace",
        "=": "0x1D",
    }
    f_key_pattern = re.compile(r"\bf(\d+)\b")

    def replace_hotkey(hotkey: str) -> str:
        # Replace F-keys to lower case: f1, f2, ...
        for key, value in replacements.items():
            hotkey = hotkey.replace(key, value)
        hotkey = f_key_pattern.sub(r"f\1", hotkey)

        # Replace right most + with -
        hotkey = re.sub(r"\+(\w+)$", r"-\1", hotkey)

        return hotkey

    for script in scripts:
        hotkey_chain_def = script.cfg["globalHotkey"]
        assert isinstance(hotkey_chain_def, str)
        if hotkey_chain_def and script.is_supported():
            hotkey_chain = [
                replace_hotkey(hotkey.lower()) for hotkey in hotkey_chain_def.split()
            ]
            if len(hotkey_chain) > 1:
                logging.warning(
                    f'Hotkey chain "{hotkey_chain_def}" is not supported on macos'
                )
                continue
            hotkey_def = ";".join(hotkey_chain)
            s += "{} : ".format(hotkey_def)
            s += (
                "python3"
                f" {get_my_script_root()}/bin/start_script.py"
                f" {script.script_path}\n\n"
            )

    with open(os.path.expanduser("~/.skhdrc"), "w") as f:
        f.write(s)
    subprocess.call(["skhd", "-r"])  # reload config


def register_global_hotkeys(scripts):
    if sys.platform == "win32":
        register_global_hotkeys_win(scripts)
    elif sys.platform == "linux":
        register_global_hotkeys_linux(scripts)
    elif sys.platform == "darwin":
        register_global_hotkeys_mac(scripts)


def _get_next_scheduled_script_run_time_file():
    return os.path.join(get_data_dir(), "next_scheduled_script_run_time.json")


class ScriptManager:
    def __init__(self, start_daemon=True, startup=False):
        self.next_scheduled_script_run_time: Dict[str, float] = load_json(
            _get_next_scheduled_script_run_time_file(), default={}
        )
        self.start_daemon = start_daemon
        self.scripts_autorun: List[Script] = []
        self.scripts: List[Script] = []
        self.startup = startup

        self.__match_scripts: List[Tuple[re.Pattern, Script]] = []
        self.__scheduled_script: List[Script] = []

    def update_script_access_time(self):
        access_time = get_all_script_access_time()
        for script in self.scripts:
            if script.script_path in access_time:
                script.mtime = max(
                    script.mtime,
                    access_time[script.script_path],
                )

    def sort_scripts(self):
        self.update_script_access_time()
        self.scripts[:] = sorted(
            self.scripts,
            key=lambda script: script.mtime,
            reverse=True,
        )

    def reload_scripts(
        self,
        autorun=True,
        on_progress: Optional[Callable[[int], None]] = None,
    ) -> bool:
        script_dict = {script.script_path: script for script in self.scripts}
        existing_scripts: Set[str] = set()

        self.scripts_autorun.clear()
        self.__scheduled_script.clear()

        clear_env_var_explorer()

        any_script_reloaded = False
        for i, file in enumerate(get_all_scripts()):
            if i % 20 == 0:
                if on_progress is not None:
                    on_progress(i)

            existing_scripts.add(file)
            if file in script_dict:
                script = script_dict[file]
                reloaded = script.refresh_script()
            else:
                script = Script(file)
                self.scripts.append(script)
                reloaded = True

            if script.cfg["runEveryNSec"]:
                self.__scheduled_script.append(script)

            if reloaded:
                any_script_reloaded = True
                should_run_script = False
                if script.cfg["autoRun"] and script.is_supported():
                    self.scripts_autorun.append(script)
                    if autorun:
                        should_run_script = True

                if script.cfg["runAtStartup"] and self.startup:
                    logging.info("runAtStartup: %s" % script.name)
                    should_run_script = True

                # Check if auto run script
                if should_run_script:
                    execute_script_autorun(script)

        # Remove deleted scripts
        self.scripts[:] = [
            script for script in self.scripts if script.script_path in existing_scripts
        ]

        # Sort
        self.scripts.sort()

        # The startup scripts should run only once.
        self.startup = False

        return any_script_reloaded

    def update_clipboard_script_map(self):
        self.__match_scripts.clear()
        for script in self.scripts:
            patt = script.cfg["matchClipboard"]
            if patt:
                self.__match_scripts.append((re.compile(patt), script))

    def match_clipboard(self, s: str) -> Iterator[Script]:
        for regex, script in self.__match_scripts:
            if re.search(regex, s):
                yield script

    def refresh_all_scripts(
        self,
        on_progress: Optional[Callable[[int], None]] = None,
        on_register_hotkeys: Optional[Callable[[Dict[str, Script]], None]] = None,
    ):
        begin_time = time.time()

        if self.reload_scripts(autorun=self.start_daemon, on_progress=on_progress):
            # Register hotkeys
            if on_register_hotkeys is not None:
                hotkeys: Dict[str, Script] = {}
                for script in self.scripts:
                    hotkey = script.cfg["hotkey"]
                    if hotkey:
                        logging.debug("Hotkey: %s: %s" % (hotkey, script.name))
                        hotkeys[hotkey] = script
                on_register_hotkeys(hotkeys)

            if self.start_daemon:
                register_global_hotkeys(self.scripts)
                self.update_clipboard_script_map()

        self.sort_scripts()

        logging.debug("Script refresh takes %.1f secs." % (time.time() - begin_time))

        # Startup script should only be run once
        self.startup = False

    def get_scheduled_scripts_run_time(self) -> Dict[Script, float]:
        run_time: Dict[Script, float] = {}
        for script in self.__scheduled_script:
            if script.script_path in self.next_scheduled_script_run_time:
                run_time[script] = self.next_scheduled_script_run_time[
                    script.script_path
                ]
        return run_time

    def get_scheduled_scripts_to_run(self) -> Iterator[Script]:
        if not self.start_daemon:
            return

        has_any_script_to_run = False
        now = time.time()
        for script in self.__scheduled_script:
            run_every_n_seconds = script.cfg["runEveryNSec"]
            if run_every_n_seconds:
                if (
                    script.script_path not in self.next_scheduled_script_run_time
                    or now > self.next_scheduled_script_run_time[script.script_path]
                ):
                    if script.is_running():
                        logging.warning("Script is still running, skip scheduled task")
                    else:
                        logging.info(f"Run scheduled task: {script.name}")
                        has_any_script_to_run = True
                        yield script

                    self.next_scheduled_script_run_time[script.script_path] = (
                        time.time() + int(run_every_n_seconds)
                    )

        if has_any_script_to_run:
            # Save last scheduled script run time
            config_file = _get_next_scheduled_script_run_time_file()
            save_json(config_file, self.next_scheduled_script_run_time)
