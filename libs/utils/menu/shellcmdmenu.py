import os
import signal
import subprocess
import sys
from itertools import cycle
from threading import Thread
from typing import Optional

from utils.menu import Menu


class MutableString:
    def __init__(self, initial_value=""):
        self.value = initial_value

    def append(self, text):
        self.value += text

    def __str__(self) -> str:
        return self.value


class ShellCmdMenu(Menu):
    def __init__(self, command: str, prompt: str = "", **kwargs):
        super().__init__(prompt=prompt, search_mode=False, line_number=False, **kwargs)

        self.__command = command
        self.__prompt = prompt
        self.__exception: Optional[Exception] = None
        self.__output = ""

        self.__thread = Thread(target=self.__shell_cmd_thread)
        self.__spinner = cycle(["|", "/", "-", "\\"])
        self.__thread.start()

        self.__update_prompt()

    def __shell_cmd_thread(self):
        try:
            self.__process = subprocess.Popen(
                self.__command,
                shell=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=0,
            )
            assert self.__process.stdout

            line = MutableString()
            self.append_item(line)
            while True:
                chunk = self.__process.stdout.read(1024).decode(errors="ignore")
                if chunk == "":
                    break
                self.__output += chunk
                for i, s in enumerate(chunk.split("\n")):
                    if i > 0:
                        line = MutableString()
                        self.append_item(line)
                    line.append(s)
        except Exception as e:
            self.__exception = e

    def on_close(self):
        self.__send_ctrl_c()

    def on_keyboard_interrupt(self):
        self.__send_ctrl_c()

    def on_idle(self):
        if not self.__thread.is_alive():
            if self.__exception is not None:
                raise self.__exception
            self.close()
        else:
            self.__update_prompt()

    def on_enter_pressed(self):
        if self.__process and self.__process.stdin:
            self.__process.stdin.write(self.get_input().encode() + b"\n")
            self.clear_input()

    def get_output(self) -> str:
        return self.__output

    def __send_ctrl_c(self):
        if self.__process:
            if sys.platform == "win32":
                os.kill(self.__process.pid, signal.CTRL_C_EVENT)
            else:
                self.__process.send_signal(signal.SIGINT)

    def __update_prompt(self):
        self.set_prompt(next(self.__spinner) + " " + self.__prompt)
