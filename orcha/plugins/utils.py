#                                   MIT License
#
#              Copyright (c) 2022 Javier Alonso <jalonso@teldat.com>
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
"""Different plugin utilities (i.e.: listing all installed plugins on the system)"""
from __future__ import annotations

import importlib
import pkgutil
import typing

from ..utils.logging_utils import get_logger
from .base import BasePlugin

if typing.TYPE_CHECKING:
    from typing import List, Optional, Type

log = get_logger()


def query_plugins() -> List[Type[BasePlugin]]:
    """
    Query all installed plugins on the system. Notice that plugins must start with the
    prefix ``orcha_`` and must export an object with name ``plugin`` which holds a reference
    to a class inheriting from :class:`BasePlugin`.

    Returns:
        list[BasePlugin]: a dictionary whose keys are module names and the value is
                               the module itself.
    """
    discovered_plugins = {
        name: importlib.import_module(name)
        for _, name, _ in pkgutil.iter_modules()
        if name.startswith("orcha_")
    }
    plugins = []
    for plugin, mod in discovered_plugins.items():
        pl: Optional[Type[BasePlugin]] = getattr(mod, "plugin", None)
        if pl is None:
            log.warning(
                'invalid plugin specified for "%s". '
                "Is there a plugin export class defined in __init__?",
                plugin,
            )
            continue

        if not issubclass(pl, BasePlugin):
            log.warning(
                'invalid class "%s" found when loading plugin "%s" - not a "BasePlugin" subclass',
                pl,
                plugin,
            )
            continue
        plugins.append(pl)

    return plugins
