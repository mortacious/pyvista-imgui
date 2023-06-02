try:
    from importlib.metadata import version

    __version__ = version("pyvista_imgui")
except Exception:  # pragma: no cover # pylint: disable=broad-exception-caught
    try:
        from ._version import __version__
    except ImportError:
        __version__ = '0.0.0'

from .texture_render_window import *
from .imgui_render_window import *
from .plotting import *