from .texture_render_window import VTKOpenGLTextureRenderWindow
from vtkmodules.vtkRenderingUI import vtkGenericRenderWindowInteractor
from vtkmodules.vtkCommonCore import vtkCommand
import enum

BACKEND_IMGUI_BUNDLE = 0
BACKEND_PYIMGUI = 1

try:
    from imgui_bundle import imgui
    _imgui_backend = BACKEND_IMGUI_BUNDLE
except ImportError:
    # fall back to the pyimgui package
    try:
        import imgui
        _imgui_backend = BACKEND_PYIMGUI
    except ImportError:
        raise ImportError("Could not find a supported imgui package.")


import typing as typ

__all__ = ['VTKImguiRenderWindowInteractor', 'BACKEND_IMGUI_BUNDLE', 'BACKEND_PYIMGUI']


class VTKImguiRenderWindowInteractor(object):
    """
    A RenderWindowInteractor to integrate VTK's rendering within an existing imgui ui.
    It uses the VTKOpenGLTextureRenderWindow to render VTK's output into an openGl-texture,
    which is displayed as an image within imgui.

    All interaction events are passed to the underlying interactor to be handled, so all
    mouse interactions are the same as in regular VTK.

    Parameters
    ----------
    border, optional
        display a border around the created imgui widget, by default False
    """
    def __init__(self, 
                 border: bool = False) -> None:
        self.imgui_backed = _imgui_backend
        self.border = border
        self.renwin = VTKOpenGLTextureRenderWindow(viewport_size=(0, 0))

        self.interactor = vtkGenericRenderWindowInteractor()
        # do not render unless explicitly requested, as imgui has control over the event loop
        self.interactor.EnableRenderOff()
        self.renwin.SetInteractor(self.interactor)
    
    def __getattr__(self, attr):
        """
        Makes the object behave like a vtkRenderWindowInteractor
        """
        if attr == '__vtk__':
            return lambda t=self.interactor: t
        elif hasattr(self.interactor, attr):
            return getattr(self.interactor, attr)
        else:
            raise AttributeError(self.__class__.__name__ +
                  " has no attribute named " + attr)
        
    def _render_imgui_bundle(self, size: typ.Optional[tuple[int, int]] = None):
        if size is None:
            # get the maximum available size
            size = imgui.get_content_region_avail()
            size = (size.x, size.y)

        self.renwin.render(size)

        # adjust the size of this interactor as well
        self.interactor.SetSize(int(size[0]), int(size[1]))
        # render the texture with the vtk output into an image
        imgui.push_style_var(imgui.StyleVar_.window_padding, (0, 0))
        # make the image unscrollable to ensure correct mouse behavior
        no_scroll_flags = imgui.WindowFlags_.no_scrollbar | imgui.WindowFlags_.no_scroll_with_mouse
        imgui.begin_child("##Viewport", size, self.border, no_scroll_flags)
        imgui.image(self.renwin.texture_id, 
                    imgui.get_content_region_avail(), 
                    (0, 1), (1, 0))
        # process the events of this widget
        self.process_events()
        imgui.end_child()
        imgui.pop_style_var()

    def _render_pyimgui(self, size: typ.Optional[tuple[int, int]] = None):
        if size is None:
            # get the maximum available size
            size = imgui.get_content_region_available()
            size = (size.x, size.y)

        self.renwin.render(size)

        # adjust the size of this interactor as well
        self.interactor.SetSize(int(size[0]), int(size[1]))
        imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (0, 0))
        no_scroll_flags = imgui.WINDOW_NO_SCROLLBAR | imgui.WINDOW_NO_SCROLL_WITH_MOUSE
        imgui.begin_child("##Viewport", size[0], size[1], self.border, no_scroll_flags)
        image_size = imgui.get_content_region_available()
        imgui.image(self.renwin.texture_id, 
                    image_size.x, image_size.y,
                    (0, 1), (1, 0))
        # process the events of this widget
        self.process_events()
        imgui.end_child()
        imgui.pop_style_var()


    def render(self, size: typ.Optional[tuple[int, int]] = None) -> None:
        """
        Renders the contents of the internal render window into an existing imgui ui 
        with the specified size. This method should be called when building 
        and updating the ui.

        Parameters
        ----------
        size, optional
            the size of the result in the ui in pixels, 
            if None (default) the maximum available size is used.
        """
        if self.imgui_backed == BACKEND_IMGUI_BUNDLE:
            self._render_imgui_bundle(size)
        else:
            self._render_pyimgui(size)

    def _process_events_imgui_bundle(self, io):
        if imgui.is_window_hovered():
            if io.mouse_clicked[imgui.MouseButton_.left]:
                self.interactor.InvokeEvent(vtkCommand.LeftButtonPressEvent)
            elif io.mouse_clicked[imgui.MouseButton_.right]:
                self.interactor.InvokeEvent(vtkCommand.RightButtonPressEvent)
            elif io.mouse_clicked[imgui.MouseButton_.middle]:
                self.interactor.InvokeEvent(vtkCommand.MiddleButtonPressEvent)
            elif io.mouse_wheel > 0:
                self.interactor.InvokeEvent(vtkCommand.MouseWheelForwardEvent)
            elif io.mouse_wheel < 0:
                self.interactor.InvokeEvent(vtkCommand.MouseWheelBackwardEvent)

        if io.mouse_released[imgui.MouseButton_.left]:
            self.interactor.InvokeEvent(vtkCommand.LeftButtonReleaseEvent)
        elif io.mouse_released[imgui.MouseButton_.right]:
            self.interactor.InvokeEvent(vtkCommand.RightButtonReleaseEvent)
        elif io.mouse_released[imgui.MouseButton_.middle]:
            self.interactor.InvokeEvent(vtkCommand.MiddleButtonReleaseEvent)
        
        self.interactor.InvokeEvent(vtkCommand.MouseMoveEvent)

    def _process_events_pyimgui(self, io) -> None:
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

    def process_events(self) -> None:
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
        #dclick = io.mouse_double_clicked[0] or io.mouse_double_clicked[1] or io.mouse_double_clicked[2]
        
        self.interactor.SetEventInformationFlipY(xpos, ypos, ctrl, shift, chr(0), 0, None)

        if self.imgui_backed == BACKEND_IMGUI_BUNDLE:
            self._process_events_imgui_bundle(io)
        else:
            self._process_events_pyimgui(io)