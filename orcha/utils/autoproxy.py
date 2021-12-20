# Based on: https://stackoverflow.com/a/63797696/8597016
# Backport of https://github.com/python/cpython/pull/4819
# Improvements to the Manager / proxied shared values code
# broke handling of proxied objects without a custom proxy type,
# as the AutoProxy function was not updated.
#
# This code adds a wrapper to AutoProxy if it is missing the
# new argument.
"""Monkeypatches an existing bug with the AutoProxy class"""
import sys
from functools import wraps
from inspect import signature
from multiprocessing import managers

from .logging_utils import get_logger

log = get_logger()
_AutoProxy = getattr(managers, "AutoProxy")


@wraps(_AutoProxy)
def AutoProxy(*args, incref=True, manager_owned=False, **kwargs):
    # Create the autoproxy without the manager_owned flag, then
    # update the flag on the generated instance. If the manager_owned flag
    # is set, `incref` is disabled, so set it to False here for the same
    # result.
    autoproxy_incref = False if manager_owned else incref
    proxy = _AutoProxy(*args, incref=autoproxy_incref, **kwargs)
    setattr(proxy, "_owned_by_manager", manager_owned)
    return proxy


def fix():
    if "manager_owned" in signature(_AutoProxy).parameters:
        log.debug(
            "Python interpreter (%d.%d.%d) has AutoProxy already patched",
            sys.version_info.major,
            sys.version_info.minor,
            sys.version_info.micro,
        )
        return

    log.debug('patching "multiprocessing.managers.AutoProxy"...')
    setattr(managers, "AutoProxy", AutoProxy)

    SyncManager = managers.SyncManager
    registry: dict = getattr(managers.SyncManager, "_registry")
    for typeid, (callable, exposed, method_to_typeid, proxytype) in registry.items():
        if proxytype is not _AutoProxy:
            continue

        create_method = hasattr(managers.SyncManager, typeid)

        # pylint: disable=no-member
        SyncManager.register(typeid, callable, proxytype, exposed, method_to_typeid, create_method)
