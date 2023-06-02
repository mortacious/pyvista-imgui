from .texture_render_window import VTKOpenGLTextureRenderWindow
from vtkmodules.vtkRenderingUI import vtkGenericRenderWindowInteractor
from vtkmodules.vtkRenderingCore import vtkRenderer
from vtkmodules.vtkCommonCore import vtkCommand
from imgui_bundle import imgui
import typing as typ

__all__ = ['VTKImguiRenderWindowInteractor']


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
        if size is None:
            # get the maximum available size
            size = imgui.get_content_region_avail()
            size = (size.x, size.y)

        self.renwin.render(size)

        # adjust the size of this interactor as well
        viewport_size = self.renwin.viewport_size
        self.interactor.SetSize(int(size[0]), int(size[1]))

        # render the texture with the vtk output into an image
        imgui.push_style_var(imgui.StyleVar_.window_padding, imgui.ImVec2(0, 0))
        imgui.begin_child("##Viewport", size, self.border, self._no_scroll_flags())
        imgui.image(self.renwin.texture_id, 
                    imgui.get_content_region_avail(), 
                    imgui.ImVec2(0, 1), imgui.ImVec2(1, 0))
        # process the events of this widget
        self.process_events()
        imgui.end_child()
        imgui.pop_style_var()

    def _no_scroll_flags(self) -> int:
        """
        Returns the imgui flags required for the rendererd texture to behave correctly.
        """
        return imgui.WindowFlags_.no_scrollbar | imgui.WindowFlags_.no_scroll_with_mouse

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