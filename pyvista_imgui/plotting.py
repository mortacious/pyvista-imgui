import pyvista as pv
from .imgui_render_window import VTKImguiRenderWindowInteractor
from pyvista import global_theme
from pyvista.plotting.render_window_interactor import RenderWindowInteractor
import typing as typ
from functools import wraps
import contextlib

__all__ = ['ImguiPlotter']


@contextlib.contextmanager
def _no_base_plotter_init():
    init = pv.BasePlotter.__init__
    pv.BasePlotter.__init__ = lambda *args, **kwargs: None
    try:
        yield
    finally:
        pv.BasePlotter.__init__ = init

class ImguiPlotter(VTKImguiRenderWindowInteractor, pv.BasePlotter):
    """
    This class extends pyvista's BasePlotter making it available
    as a DearImGui widget. 

    To display this plotter withing an existing imgui application, just call
    the 'render'-method when building the ui. 

    Alternatively, the plotter also supports rendering as a standalone 
    imgui-application by calling the 'show'-method. It will display the plotter
    as a widget inside a minimal window-application.

    Parameters
    ----------
    multi_samples, optional
        The number of multi-samples used to mitigate aliasing. 4 is a
        good default but 8 will have better results with a potential
        impact on performance.. Defaults to None.
    line_smoothing, optional
        Enable line smoothing, by default False
    point_smoothing, optional
        Enable point smoothing, by default False
    polygon_smoothing, optional
        Enable polygon smoothing, by default False
    background, optional
        Spawn the viewer in a background thread to allow the main python interpreter to continue. 
        Only works when calling 'show'
    imgui_backend, optional
        The imgui backend to use for the ui. Use either 'pyimgui' or 'imgui_bundle'.
    """

    def __init__(self, 
                 title=None,
                 window_size=None,
                 line_smoothing: bool = False,
                 point_smoothing: bool = False,
                 polygon_smoothing: bool = False,
                 background: bool = False,
                 imgui_backend: typ.Optional[str] = None,
                 **kwargs):
        
        self._initialized = False
        
        # imgui has it's own border functionality so ignore the vtk one
        border = kwargs.pop("border", False)
        with _no_base_plotter_init():
            VTKImguiRenderWindowInteractor.__init__(self, border=border, imgui_backend=imgui_backend)
        pv.BasePlotter.__init__(self, **kwargs)
        self.title = title or "ImguiPlotter"
        self.suppress_rendering = True # disable rendering as the event loop is controlled by imgui

        self.render_window.SetMultiSamples(0)
        if line_smoothing:
            self.render_window.LineSmoothingOn()
        if point_smoothing:
            self.render_window.PointSmoothingOn()
        if polygon_smoothing:
            self.render_window.PolygonSmoothingOn()

        for renderer in self.renderers:
            self.render_window.AddRenderer(renderer)

        # Add the shadow renderer to allow us to capture interactions within
        # a given viewport
        # https://vtk.org/pipermail/vtkusers/2018-June/102030.html
        number_or_layers = self.render_window.GetNumberOfLayers()
        current_layer = self.renderer.GetLayer()
        self.render_window.SetNumberOfLayers(number_or_layers + 1)
        self.render_window.AddRenderer(self.renderers.shadow_renderer)
        self.renderers.shadow_renderer.SetLayer(current_layer + 1)
        self.renderers.shadow_renderer.SetInteractive(False)  # never needs to capture
        
        self.background_color = self.theme.background
        self._setup_interactor()

        # # Add the shadow renderer to allow us to capture interactions within
        # # a given viewport
        # # https://vtk.org/pipermail/vtkusers/2018-June/102030.html
        number_or_layers = self.render_window.GetNumberOfLayers()
        current_layer = self.renderer.GetLayer()
        self.render_window.SetNumberOfLayers(number_or_layers + 1)
        self.render_window.AddRenderer(self.renderers.shadow_renderer)
        self.renderers.shadow_renderer.SetLayer(current_layer + 1)
        self.renderers.shadow_renderer.SetInteractive(False)  # never needs to capture


        # Set window size
        self._window_size_unset = False
        if window_size is None:
            self.window_size = self._theme.window_size
            if self.window_size == pv.plotting.themes.Theme().window_size:
                self._window_size_unset = True
        else:
            self.window_size = window_size

        # # Set camera widget based on theme. This requires that an
        # # interactor be present.
        if self.theme._enable_camera_orientation_widget:
            self.add_camera_orientation_widget()

        # Set background
        self.set_background(self._theme.background)

        if self._theme.depth_peeling.enabled:
            if self.enable_depth_peeling():
                for renderer in self.renderers:
                    renderer.enable_depth_peeling()

        # set anti_aliasing based on theme
        if self.theme.anti_aliasing:
            self.enable_anti_aliasing(self.theme.anti_aliasing)

        self._run_background = background
        self._thread = None

        # self._app = None
        # Set some private attributes that let BasePlotter know
        # that this is safely rendering
        self._first_time = False  # Crucial!
        self._initialized = True

    def _setup_interactor(self) -> None:
        self.iren = RenderWindowInteractor(
            self, interactor=self.render_window.GetInteractor()
        )
        self.iren.interactor.RemoveObservers(
            "MouseMoveEvent"
        )  # slows window update?
        self.iren.initialize()
        self.enable_trackball_style()
        self.iren.add_observer("KeyPressEvent", self.key_press_event)


    def __del__(self):
        # We have to check here if the plotter was only partially initialized
        self.deep_clean()
        if self._initialized:
            del self.renderers

    @property
    def window_size(self) -> tuple[int, int]:  # numpydoc ignore=RT01
        """Return the render window size in ``(width, height)``.

        Examples
        --------
        Change the window size from ``200 x 200`` to ``400 x 400``.

        >>> import pyvista as pv
        >>> pl = pv.Plotter(window_size=[200, 200])
        >>> pl.window_size
        [200, 200]
        >>> pl.window_size = [400, 400]
        >>> pl.window_size
        [400, 400]

        """
        return tuple(self.render_window.GetSize())

    @window_size.setter
    def window_size(self, window_size):  # numpydoc ignore=GL08
        self.render_window.SetSize(window_size[0], window_size[1])
        self._window_size_unset = False
        #self.render() # rendering is controlled by imgui so do not do that here!

    def close(self, render=False):
        """Override the BasePlotter's close method to ensure correct behavior.

        Parameters
        ----------
        render : bool
            Unused argument.

        """
        from pyvista.plotting.widgets import WidgetHelper
        from pyvista.plotting.plotting import _ALL_PLOTTERS
        
        # optionally run just prior to exiting the plotter
        if self._before_close_callback is not None:
            self._before_close_callback(self)
            self._before_close_callback = None

        # must close out widgets first
        WidgetHelper.close(self)
        # Renderer has an axes widget, so close it
        self.renderers.close()
        self.renderers.remove_all_lights()

        # reset scalar bars
        self.scalar_bars.clear()
        self.mesh = None
        self.mapper = None

        if hasattr(self, 'textActor'):
            del self.textActor

        # end movie
        if hasattr(self, 'mwriter'):
            try:
                self.mwriter.close()
            except BaseException:
                pass

        # Remove the global reference to this plotter unless building the
        # gallery to allow it to collect.
        if not pv.BUILDING_GALLERY:
            if _ALL_PLOTTERS is not None:
                _ALL_PLOTTERS.pop(self._id_name, None)

        # this helps managing closed plotters
        self._closed = True 

    @wraps(pv.BasePlotter.add_actor)
    def add_actor(self, *args, **kwargs):
        """
        Override to ignore the 'render' argument
        """
        kwargs["render"] = False # never render as this is not controlled by vtk any more
        return pv.BasePlotter.add_actor(self, *args, **kwargs)
    
    @wraps(pv.BasePlotter.set_background)
    def set_background(self, color, top=None, right=None, side=None, corner=None, all_renderers=True):
        # the background color is not set unless the top color is set as well to enforce it 
        super().set_background(color, top=top or color, right=right, side=side, corner=corner, all_renderers=all_renderers)

    def show(self, 
             window_size: tuple[int, int] = None,
             before_close_callback: typ.Optional[typ.Callable] = None,
            **kwargs):
        """
        Show this plotter as a standalone imgui application. This call blocks until
        the resulting window is closed again.
        To integrate within an existing imgui context use render() within 
        the rendering loop.

        Parameters
        ----------
        window_size, optional
            The window size. Defaults to (1400, 1080).
        before_close_callback, optional
            An optional callback to execute before closing, by default None.
        kwargs: Exists to ensure compatiblity with the BasePlotter interface. 
                Any additional keywords are ignored for this plotter.
        """
        if before_close_callback is None:
            before_close_callback = global_theme._before_close_callback
        self._before_close_callback = before_close_callback

        if window_size is None:
            window_size = self.window_size
        else:
            self._window_size_unset = False
        self.render_window.SetSize(window_size[0], window_size[1])

        def _show():
            self.imgui_backend.show(title=self.title, window_size=window_size)

        if self._run_background:
            from threading import Thread
            self._thread = Thread(target=_show)
            self._thread.start()
        else:
            _show()
    
