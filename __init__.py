"""Euphoria ORIO Operations — unified plugin package (Innovex pilot demo).

Python half: ``dashboard/`` (FastAPI router mounted at
``/api/plugins/euphoria-orio-operations/``). Desktop renderer half:
``desktop/plugin.js``. Neither half registers core agent tools, hooks, or
middleware, so there is no capability to declare.
"""


def register(ctx) -> None:
    """No-op registration for the capability probe.

    The real surfaces are the dashboard API router and the desktop
    renderer. The probe requires register() to exist; it records nothing.
    """
    return None
