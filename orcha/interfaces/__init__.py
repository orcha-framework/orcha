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
""":mod:`interfaces` defines the basic structure needed when communicating with Orcha"""
from .decorators import is_implemented, notimplemented
from .message import Message
from .petition import (
    BROKEN_STATES,
    RUNNING_STATES,
    STOPPED_STATES,
    EmptyPetition,
    Petition,
    PetitionState,
    Placeholder,
    SignalingPetition,
)
from .service import ServiceWrapper, register_service, start_service
from .types import Bool, SupportsBool

__all__ = [
    "EmptyPetition",
    "Message",
    "Petition",
    "register_service",
    "ServiceWrapper",
    "start_service",
    "SignalingPetition",
    "PetitionState",
    "STOPPED_STATES",
    "RUNNING_STATES",
    "BROKEN_STATES",
    "SupportsBool",
    "notimplemented",
    "is_implemented",
    "Bool",
    "Placeholder",
]
