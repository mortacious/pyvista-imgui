import pyvista as pv
from .imgui_render_window import VTKImguiRenderWindowInteractor, BACKEND_IMGUI_BUNDLE, BACKEND_PYIMGUI
from pyvista import global_theme
from pyvista.plotting.render_window_interactor import RenderWindowInteractor
import typing as typ
from functools import wraps

__all__ = ['ImguiPlotter']


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
    """

    def __init__(self, 
                 multi_samples: int = None,
                 line_smoothing: bool = False,
                 point_smoothing: bool = False,
                 polygon_smoothing: bool = False,
                 background: bool = False,
                 **kwargs):

        # imgui has it's own border functionality so ignore the vtk one
        border = kwargs.pop("border", False)

        VTKImguiRenderWindowInteractor.__init__(self, border=border)
        pv.BasePlotter.__init__(self, **kwargs)

        if multi_samples is None:
            multi_samples = global_theme.multi_samples

        self.renwin.SetMultiSamples(multi_samples)
        if line_smoothing:
            self.renwin.LineSmoothingOn()
        if point_smoothing:
            self.renwin.PointSmoothingOn()
        if polygon_smoothing:
            self.renwin.PolygonSmoothingOn()

        for renderer in self.renderers:
            self.renwin.AddRenderer(renderer)

        if global_theme.depth_peeling["enabled"]:
            if self.enable_depth_peeling():
                for renderer in self.renderers:
                    renderer.enable_depth_peeling()

        self._setup_interactor()

        self._background = background
        self._thread = None

        self._app = None
        # Set some private attributes that let BasePlotter know
        # that this is safely rendering
        self._first_time = False  # Crucial!

    def _setup_interactor(self) -> None:
        self.iren = RenderWindowInteractor(
            self, interactor=self.renwin.GetInteractor()
        )
        self.iren.interactor.RemoveObservers(
            "MouseMoveEvent"
        )  # slows window update?
        self.iren.initialize()
        self.enable_trackball_style()

    def __del__(self):
        # We have to check here if the plotter was only partially initialized
        self.deep_clean()
        if self._initialized:
            del self.renderers

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
        pv.BasePlotter.add_actor(self, *args, **kwargs)

    def _show_imgui_bundle(self, 
                           title: typ.Optional[str] = None, 
                           window_size: tuple[int, int] = (1400, 1080)):
        """
        show method for the imgui-bundle package.

        Parameters
        ----------
        title, optional
            The title of the window, if None, a default title is used.
        window_size, optional
            The size of the displayed window, by default (1400, 1080)
        """

        from imgui_bundle import immapp, hello_imgui, imgui     
        runner_params = hello_imgui.RunnerParams()
        runner_params.app_window_params.window_title = title or "ImguiPlotter"
        runner_params.app_window_params.window_geometry.size = window_size
        runner_params.imgui_window_params.show_status_bar = True

        def gui():
            hello_imgui.apply_theme(hello_imgui.ImGuiTheme_.imgui_colors_dark)
            vec = imgui.get_main_viewport().pos
            imgui.set_next_window_pos(vec, imgui.Cond_.once)
            imgui.set_next_window_size(imgui.get_main_viewport().size)
            imgui.set_next_window_bg_alpha(1.0)
            imgui.begin("Vtk Viewer", flags=imgui.WindowFlags_.no_bring_to_front_on_focus | imgui.WindowFlags_.no_title_bar | imgui.WindowFlags_.no_decoration | imgui.WindowFlags_.no_resize | imgui.WindowFlags_.no_move)
            self.render()
            imgui.end()

        runner_params.callbacks.show_gui = gui
        runner_params.imgui_window_params.default_imgui_window_type = hello_imgui.DefaultImGuiWindowType.no_default_window
        immapp.run(runner_params=runner_params)

    def _show_pyimgui(self,
                      title: typ.Optional[str] = None, 
                      window_size: tuple[int, int] = (1400, 1080)):
        """
        Show method for the pyimgui package

        Parameters
        ----------
        title, optional
            The title of the window, if None, a default title is used.
        window_size, optional
            The size of the displayed window, by default (1400, 1080)
        """
        import glfw
        import OpenGL.GL as GL
        import imgui
        from imgui.integrations.glfw import GlfwRenderer

        if not glfw.init():
            raise ValueError("Could not initialize OpenGL context")

        # Create a window and its OpenGL context
        window = glfw.create_window(int(window_size[0]), int(window_size[1]), title or "ImguiPlotter", None, None)
        glfw.make_context_current(window)

        if not window:
            glfw.terminate()
            raise ValueError("Could not initialize Window")
        
        background_color = (0.0, 0.0, 0.0, 1.0)
        GL.glClearColor(*background_color)
        imgui.create_context()

        impl = GlfwRenderer(window)

        while not glfw.window_should_close(window):
            glfw.poll_events()
            impl.process_inputs()
            imgui.new_frame()
            vec = imgui.get_main_viewport().pos
            imgui.set_next_window_position(vec.x, vec.y, imgui.ONCE)
            size = imgui.get_main_viewport().size
            imgui.set_next_window_size(size.x, size.y)
            imgui.set_next_window_bg_alpha(1.0)
            window_flags = imgui.WINDOW_NO_BRING_TO_FRONT_ON_FOCUS | \
                           imgui.WINDOW_NO_TITLE_BAR | \
                           imgui.WINDOW_NO_DECORATION | \
                           imgui.WINDOW_NO_RESIZE | \
                           imgui.WINDOW_NO_MOVE
                                 
            imgui.begin("Vtk Viewer", flags=window_flags)
            self.render()
            imgui.end()

            imgui.render()

            GL.glClearColor(*background_color)
            GL.glClear(GL.GL_COLOR_BUFFER_BIT)
            impl.render(imgui.get_draw_data())
            glfw.swap_buffers(window)

        impl.shutdown()
        glfw.terminate()

    def show(self, 
             title: typ.Optional[str] = None, 
             window_size: tuple[int, int] = (1400, 1080),
             before_close_callback: typ.Optional[typ.Callable] = None,
            **kwargs):
        """
        Show this plotter as a standalone imgui application. This call blocks until
        the resulting window is closed again.
        To integrate within an existing imgui context use render() within 
        the rendering loop.

        Parameters
        ----------
        title, optional
            The title to use for the standalone window. Defaults to None to use the default title.
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

        def _show():
            if self.imgui_backed == BACKEND_IMGUI_BUNDLE:
                self._show_imgui_bundle(title=title, window_size=window_size)
            else:
                self._show_pyimgui(title=title, window_size=window_size)
        if self._background:
            from threading import Thread
            self._thread = Thread(target=_show)
            self._thread.start()
        else:
            _show()
    
