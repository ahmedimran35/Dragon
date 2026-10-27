"""This computer as a device: its screen as a picture, and — when Hands is on — as a hand.

:mod:`dragon.computer.screen` takes the picture (``mss`` and Pillow, or the platform's own
tool) and names the active window; :mod:`dragon.computer.hands` moves the mouse and types
(``pyautogui``, or ``xdotool`` on X11); :mod:`dragon.computer.link` is the object the
operator loop and the ``computer_*`` tools talk to, shaped the way
:mod:`dragon.gui.operator` expects, so one loop serves both.
"""

from dragon.computer.screen import active_window, capture, take_screenshot

__all__ = ["active_window", "capture", "take_screenshot"]
