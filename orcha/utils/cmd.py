#                                   MIT License
#
#              Copyright (c) 2021 Javier Alonso <jalonso@teldat.com>
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#      copies of the Software, and to permit persons to whom the Software is
#            furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
#                 copies or substantial portions of the Software.
#
#   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#     AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#                                    SOFTWARE.
"""Command line utilities that can be used by subprojects or plugins"""
from __future__ import annotations

import shlex
import subprocess
import typing

from .logging_utils import get_logger
from .ops import nop

if typing.TYPE_CHECKING:
    from typing import Any, Callable, Sequence

log = get_logger()


def run_command(
    cmd: str | Sequence[str],
    on_start: Callable[[subprocess.Popen], Any] = nop,
    on_output: Callable[[str], Any] = nop,
    on_finish: Callable[[int], Any] = nop,
    cwd: str | None = None,
) -> int:
    """
    Runs a command in a "secure" environment redirecting stderr into stdout and
    calling :func:`on_output` on every line (as they are being written).

    The method accepts three functions which are used for defining a custom behavior
    during execution:

        + :func:`on_start` receives the :class:`Popen <subprocess.Popen>` object just
          created, even before starting running something.
        + :func:`on_output` receives a UTF-8 string corresponding with current command output.
        + :func:`on_finish` receives the program return code, so you can handle any errors
          that may occur.

    Args:
        cmd (:obj:`str` | :class:`Collection <collections.abc.Collection>`): the command to run.
            Can be a :obj:`str` or an iterable. If a :obj:`str` is given
            then :func:`shlex.split` is called for dividing the command.
        on_start (Callable[[subprocess.Popen], Any]): function to be run when the process has
            just started. Defaults to :obj:`None`.
        on_output (Callable[[str], Any]): function to be called when the process outputs a line.
            Defaults to :obj:`None`.
        on_finish (Callable[[int], Any]): function to be called when the process finishes.
            Defaults to :obj:`None`.
        cwd (str): working directory to move on when calling the command. Defaults to :obj:`None`.

    Returns:
        int: command return code
    """
    command = shlex.split(cmd) if isinstance(cmd, str) else cmd
    log.debug("$ %s", cmd)
    log.debug("> %s", command)

    with subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        universal_newlines=True,
        bufsize=1,
        cwd=cwd,
        start_new_session=True,
    ) as proc:
        on_start(proc)
        for line in proc.stdout:
            on_output(line)

        ret = proc.wait()
    on_finish(ret)
    return ret
