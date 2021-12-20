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
"""
The plugins are part of the basic structure of Orcha. Plugins allow extended
functionality by using command line arguments and custom
:class:`managers <orcha.lib.Manager>` and :class:`petitions <orcha.interfaces.Petition>`.

Note:
    By default, Orcha provides the complete structure for running and orchestrate
    what you want, based on :attr:`actions <orcha.interfaces.Petition.action>` and
    :attr:`conditions <orcha.interfaces.Petition.conditions>`. Nevertheless, there
    is no code in there and the provided command line interface is just the
    skeleton for further plugins to add their functionality.

    That said, plugins are **mandatory** in order to work with Orcha.
"""
from .base import B, BasePlugin, query_plugins
from .lp import ListPlugin

__all__ = ["BasePlugin", "B", "ListPlugin", "query_plugins"]
