"""Errors a device's screen can raise, and the one marker every tool understands.

A *device* here is anything the hands can look at and act on: this computer's screen, or
any other surface a link exposes. The vocabulary is deliberately small:

* :class:`DeviceError` — the device could not do what was asked (or is not there);
* :class:`DeviceGone` — the connection dropped under a request; often brief, so the
  operator waits a little for it to come back before giving up;
* :class:`DeviceStopped` — the person pressed Stop: the task ends and the agent asks.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


class DeviceError(RuntimeError):
    """The device could not do what was asked (or is not there)."""


STOP_MARKER = "dragon:stop"


class DeviceGone(DeviceError):
    """The device's connection is gone — it dropped under a request, or none is connected.
    Not the device's fault and often brief, so the operator waits a little for it to come
    back before the task is given up."""


class DeviceStopped(DeviceError):
    """The person pressed Stop: the task ends and the agent asks what to do."""

    def __init__(self, message: str = "") -> None:
        super().__init__(
            "The user pressed Stop. Do not go on operating the screen; ask them what to do next."
        )
        self.device_message = message


@dataclass
class Device:
    """One surface the hands may work on.

    The operator only needs to know what to call it, how big it is, and how to send it a
    message; a link fills the rest in.
    """

    id: str
    name: str = "device"
    platform: str = "unknown"
    gui: bool = False
    browser: bool = False
    apps: list[dict[str, str]] = field(default_factory=list)
    width: int = 0
    height: int = 0
    connected_at: float = field(default_factory=time.time)
    send: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "platform": self.platform,
            "gui": self.gui,
            "browser": self.browser,
            "apps": len(self.apps),
            "width": self.width,
            "height": self.height,
        }

    def app_list(self, limit: int = 60) -> str:
        """``Name (id), …`` — what the model may name in ``open_app``."""
        items = []
        for app in self.apps[:limit]:
            app_id, name = app.get("id", ""), app.get("name", "")
            items.append(
                f"{name} ({app_id})" if name and app_id and name != app_id else name or app_id
            )
        return ", ".join(i for i in items if i)


__all__ = [
    "STOP_MARKER",
    "Device",
    "DeviceError",
    "DeviceGone",
    "DeviceStopped",
]
