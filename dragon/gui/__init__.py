"""The hands: what the agent sees of a screen, and the loop that works on it.

The generic pieces live here, independent of any one device: :class:`~dragon.gui.screen.Screen`
(the picture and the little a surface can always say about it), :class:`~dragon.gui.operator.GuiOperator`
(the step loop that drives a vision model through the Sentinel) and the errors in
:mod:`dragon.gui.errors`. The computer's own link is :mod:`dragon.computer.link`.
"""

from dragon.gui.errors import STOP_MARKER, Device, DeviceError, DeviceGone, DeviceStopped
from dragon.gui.operator import AUTO_LANGUAGE, COMPUTER, GuiOperator
from dragon.gui.screen import Screen

__all__ = [
    "AUTO_LANGUAGE",
    "COMPUTER",
    "STOP_MARKER",
    "Device",
    "DeviceError",
    "DeviceGone",
    "DeviceStopped",
    "GuiOperator",
    "Screen",
]
