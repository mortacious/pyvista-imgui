import typing as typ
from .imgui_render_window import RendererBackend, register_backend
from vtkmodules.vtkCommonCore import vtkCommand
from vtkmodules.vtkRenderingCore import vtkRenderWindow, vtkRenderWindowInteractor
import typing as typ
try:
    import imgui
except ImportError:
    imgui = None

__all__ = ['RendererBackendPyImgui']

@register_backend("pyimgui")
class RendererBackendPyImgui(RendererBackend):
    def __init__(self, 
                 interactor: vtkRenderWindowInteractor, 
                 render_window: vtkRenderWindow,
                 border = False) -> None:
        if not imgui:
            raise ModuleNotFoundError(f"{self.__class__.__name__} requires the 'pyimgui' package.")
        super().__init__(interactor, render_window, border=border)

    def render(self, size: tuple[int, int] | None = None):
        if size is None:
            # get the maximum available size
            size = imgui.get_content_region_available()
            size = (size.x, size.y)

        self.render_window.render(size)

        # adjust the size of this interactor as well
        self.interactor.SetSize(int(size[0]), int(size[1]))
        imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (0, 0))
        no_scroll_flags = imgui.WINDOW_NO_SCROLLBAR | imgui.WINDOW_NO_SCROLL_WITH_MOUSE
        imgui.begin_child("##Viewport", size[0], size[1], self.border, no_scroll_flags)
        image_size = imgui.get_content_region_available()
        imgui.image(self.render_window.texture_id, 
                    image_size.x, image_size.y,
                    (0, 1), (1, 0))
        # process the events of this widget
        self.process_events()
        imgui.end_child()
        imgui.pop_style_var()

    def _process_mouse_events(self, io):
        if imgui.is_window_hovered():
            if imgui.is_mouse_clicked(imgui.MOUSE_BUTTON_LEFT):
                self.interactor.InvokeEvent(vtkCommand.LeftButtonPressEvent)
            elif imgui.is_mouse_clicked(imgui.MOUSE_BUTTON_RIGHT):
                self.interactor.InvokeEvent(vtkCommand.RightButtonPressEvent)
            elif imgui.is_mouse_clicked(imgui.MOUSE_BUTTON_MIDDLE):
                self.interactor.InvokeEvent(vtkCommand.MiddleButtonPressEvent)
            elif io.mouse_wheel > 0:
                self.interactor.InvokeEvent(vtkCommand.MouseWheelForwardEvent)
            elif io.mouse_wheel < 0:
                self.interactor.InvokeEvent(vtkCommand.MouseWheelBackwardEvent)

        if imgui.is_mouse_released(imgui.MOUSE_BUTTON_LEFT):
            self.interactor.InvokeEvent(vtkCommand.LeftButtonReleaseEvent)
        elif imgui.is_mouse_released(imgui.MOUSE_BUTTON_RIGHT):
            self.interactor.InvokeEvent(vtkCommand.RightButtonReleaseEvent)
        elif imgui.is_mouse_released(imgui.MOUSE_BUTTON_MIDDLE):
            self.interactor.InvokeEvent(vtkCommand.MiddleButtonReleaseEvent)
        
        self.interactor.InvokeEvent(vtkCommand.MouseMoveEvent)

    def process_events(self):
        """
        Handle events by passing them to the underlying vtk interactor. This method is called automatically
        on rendering.
        """
        # do nothing as long as the mouse pointer is not within the current window or it is not focussed
        if not imgui.is_window_focused() and not imgui.is_window_hovered():
            return
        io = imgui.get_io()
        io.config_windows_move_from_title_bar_only = True # do not drag the window when clicking on the image
        viewport_pos = imgui.get_cursor_start_pos()

        xpos = int(io.mouse_pos.x - viewport_pos.x)
        ypos = int(io.mouse_pos.y - viewport_pos.y)

        ctrl = io.key_ctrl
        shift = io.key_shift
        
        repeat = 0
        #if io.mouse_double_clicked[0] or io.mouse_double_clicked[1] or io.mouse_double_clicked[2]:
        #    repeat = 1

        if xpos < 0 or ypos < 0:
            return 
        
        self.interactor.SetEventInformationFlipY(xpos, ypos, ctrl, shift, chr(0), repeat, None)

        self._process_mouse_events(io)
        # no keyboard events yet
        #self._process_keyboard_events(xpos, ypos, ctrl, shift)

    def show(self,
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
      