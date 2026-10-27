"""Dragon app server: the always-on agent behind the web app.

    dragon serve                     # http://127.0.0.1:8787
    dragon serve --host 0.0.0.0      # reachable from your other devices on the same network

Everything the CLI can do, the app can do — plus background work while the app
is closed, approval cards, side chats, goals, tasks, memory you can edit, and an
activity log behind the avatar.
"""

from __future__ import annotations

import contextlib
import os
import socket
import sys
import threading
import traceback

from dragon import __version__, loopback
from dragon.certs import ensure_ca_bundle
from dragon.config import Settings
from dragon.server.api import STATIC_DIR, create_app
from dragon.server.service import DragonService

__all__ = ["DragonService", "STATIC_DIR", "create_app", "lan_ip", "port_taken", "serve"]


def lan_ip() -> str | None:
    """Best-effort LAN address (no packets are actually sent)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return None


def port_taken(host: str, port: int, timeout: float = 0.5) -> str | None:
    """What already answers on ``host:port``, if anything: ``"Dragon <version>"`` when it
    is one of ours (its ``/api/health`` says so), ``"another program"`` otherwise, ``None``
    when nothing listens there. A connect, not a bind: a bind would mistake the previous
    run's closing connections for a listener."""
    probe_host = {"": "127.0.0.1", "0.0.0.0": "127.0.0.1", "localhost": "127.0.0.1", "::": "::1"}
    where = probe_host.get(host, host)
    try:
        with socket.create_connection((where, port), timeout=timeout):
            pass
    except OSError:
        return None
    import json

    from dragon.local_http import local_open

    base = f"http://[{where}]:{port}" if ":" in where else f"http://{where}:{port}"
    try:
        with local_open(f"{base}/api/health", timeout=timeout * 4) as response:
            health = json.loads(response.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - not HTTP, not JSON, not answering: not ours
        return "another program"
    if isinstance(health, dict) and health.get("ok") is True and health.get("version"):
        return f"Dragon {health['version']}"
    return "another program"


def serve(
    settings: Settings,
    host: str | None = None,
    port: int | None = None,
    log_level: str = "warning",
) -> None:
    """Run the app server (blocking). Prints the URL, with the access token in its
    ``#fragment`` where the browser keeps it to itself."""
    import uvicorn

    from dragon.stdio import utf8_console

    utf8_console()
    ensure_ca_bundle()
    # Windows: asyncio's self-pipe is a loopback connection; on a machine that intercepts
    # those the loop would never start. Say so and stop, rather than listen on nothing.
    loopback.install()
    problem = loopback.check()
    if problem:
        print(f"Dragon: {problem}", file=sys.stderr, flush=True)
        raise SystemExit(78)
    host = host or settings.server.host
    port = port or settings.server.port
    taken = port_taken(host, port)
    if taken:
        # before the service starts: a second `dragon serve` used to open the data directory,
        # announce itself as ready, link included, and only then die on uvicorn's bind error
        advice = (
            "That one keeps running: open it in the browser, or stop it before starting another."
            if taken.startswith("Dragon")
            else "Stop it, or choose another port with --port."
        )
        print(
            f"Dragon: port {port} on {host} is already in use by {taken}. {advice}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(98)
    service = DragonService(settings)
    app = create_app(settings, service)

    shown_host = host
    if host in ("0.0.0.0", "::", ""):
        shown_host = lan_ip() or "127.0.0.1"
    url = f"http://[{shown_host}]:{port}/" if ":" in shown_host else f"http://{shown_host}:{port}/"
    if service.token:
        # in the fragment: the browser keeps it to itself, so it is in no access log
        url += f"#token={service.token}"
    # the banner once the socket is about to open (a desktop shell reads the log when the
    # app takes long to answer); the services may still be coming up behind it, and
    # /api/health says which one
    print(f"Dragon {__version__} starting on {host}:{port} (pid {os.getpid()})", flush=True)
    serving = threading.Event()

    def on_ready() -> None:
        serving.set()
        _print_banner(url, service)

    app.state.on_ready = on_ready
    _watch_startup(serving)
    # The standard loop, not uvloop: uvloop leaves extra copies of a child's stdout/stderr
    # open in the child, so anything it leaves running in the background (Cursor's CLI keeps a
    # worker alive, `nohup … &` in the shell tool) holds our pipes and the read never ends.
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=log_level,
        loop="asyncio",
        ws_ping_interval=20,
        ws_ping_timeout=20,
    )


def _watch_startup(serving: threading.Event, after: tuple[float, ...] = (20, 40)) -> None:
    """A daemon thread that, should the socket still not be open 20 s and then 60 s after
    the banner, writes where every thread is to stderr. A machine on which the runtime
    starts and then says nothing (a Windows box whose security software holds the
    loopback, a stalled import) is then diagnosable from the desktop shell's log."""

    def watch() -> None:
        waited = 0.0
        for delay in after:
            if serving.wait(delay):
                return
            waited += delay
            _dump_threads(f"still not serving after {waited:.0f} s")

    threading.Thread(target=watch, name="startup-watchdog", daemon=True).start()


def _dump_threads(why: str) -> None:
    lines = [f"Dragon: {why}; where every thread is:"]
    names = {t.ident: t.name for t in threading.enumerate()}
    for ident, frame in sys._current_frames().items():
        lines.append(f"--- thread {names.get(ident, '?')} ({ident})")
        lines.extend(line.rstrip() for line in traceback.format_stack(frame))
    with contextlib.suppress(Exception):
        print("\n".join(lines), file=sys.stderr, flush=True)


def _print_banner(url: str, service: DragonService) -> None:
    from rich.console import Console

    console = Console()
    name = (service.profile.name or "").strip()
    # "Dragon · Lumi is ready."; before the agent has a name of its own, "Dragon is ready."
    who = f" · [bold]{name}[/bold]" if name and name != "Ember" else ""
    console.print(f"[bold magenta]Dragon[/bold magenta]{who} is ready.")
    if not STATIC_DIR.is_dir():
        console.print(
            "[yellow]web app not built[/yellow]: run `cd web && npm install && npm run build`"
        )
    console.print(f"Open in your browser:  [bold cyan]{url}[/bold cyan]")
    if service.token:
        console.print(
            "[dim]The link carries your access token in its #fragment; share it only with "
            "your own devices, or paste the token where a client asks for one.[/dim]"
        )
    console.print(
        "[dim]Press Ctrl+C to stop. Your Dragon keeps working in the background while it runs.[/dim]"
    )
