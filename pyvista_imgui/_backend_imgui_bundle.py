import typing as typ
from .imgui_render_window import RendererBackend, register_backend
from vtkmodules.vtkCommonCore import vtkCommand
from vtkmodules.vtkRenderingCore import vtkRenderWindow, vtkRenderWindowInteractor
import typing as typ

try:
    from imgui_bundle import imgui
except ImportError:
    imgui = None

if imgui: 
    _Key = imgui.Key
    _keysyms = {
        _Key.backspace: ('BackSpace', None),
        _Key.tab: ('Tab', None),
        _Key.enter: ('Return', None),
        _Key.keypad_enter: ('Return', None),
        _Key.left_shift: ('Shift_L', None),
        _Key.left_ctrl: ('Control_L', None),
        _Key.left_alt: ('Alt_L', None),
        _Key.pause: ('Pause', None),
        _Key.caps_lock: ('Caps_Lock', None),
        _Key.escape: ('Escape', None),
        _Key.space: ('space', ' '),
        # Key.Key_Prior : 'Prior',
        # Key.Key_Next : 'Next',
        _Key.end: ('End', None),
        _Key.home: ('Home', None),
        _Key.left_arrow: ('Left', None),
        _Key.up_arrow: ('Up', None),
        _Key.right_arrow: ('Right', None),
        _Key.down_arrow: ('Down', None),
        _Key.insert: ('Insert', None),
        _Key.delete: ('Delete', None),
        _Key._0: ('0', '0'),
        _Key._1: ('1', '1'),
        _Key._2: ('2', '2'),
        _Key._3: ('3', '3'),
        _Key._4: ('4', '4'),
        _Key._5: ('5', '5'),
        _Key._6: ('6', '6'),
        _Key._7: ('7', '7'),
        _Key._8: ('8', '8'),
        _Key._9: ('9', '9'),
        _Key.a: ('a', 'a'),
        _Key.b: ('b', 'b'),
        _Key.c: ('c', 'c'),
        _Key.d: ('d', 'd'),
        _Key.e: ('e', 'e'),
        _Key.f: ('f', 'f'),
        _Key.g: ('g', 'g'),
        _Key.h: ('h', 'h'),
        _Key.i: ('i', 'i'),
        _Key.j: ('j', 'j'),
        _Key.k: ('k', 'k'),
        _Key.l: ('l', 'l'),
        _Key.m: ('m', 'm'),
        _Key.n: ('n', 'n'),
        _Key.o: ('o', 'o'),
        _Key.p: ('p', 'p'),
        _Key.q: ('q', 'q'),
        _Key.r: ('r', 'r'),
        _Key.s: ('s', 's'),
        _Key.t: ('t', 't'),
        _Key.u: ('u', 'u'),
        _Key.v: ('v', 'v'),
        _Key.w: ('w', 'w'),
        _Key.x: ('x', 'x'),
        _Key.y: ('y', 'y'),
        _Key.z: ('z', 'z'),
        _Key.keypad_add: ('plus', '+'),
        _Key.right_bracket: ('plus', '+'),
        _Key.minus: ('minus', '-'),
        _Key.period: ('period', '~'),
        _Key.slash: ('slash', '/'),
        _Key.f1: ('F1', None),
        _Key.f2: ('F2', None),
        _Key.f3: ('F3', None),
        _Key.f4: ('F4', None),
        _Key.f5: ('F5', None),
        _Key.f6: ('F6', None),
        _Key.f7: ('F7', None),
        _Key.f8: ('F8', None),
        _Key.f9: ('F9', None),
        _Key.f10: ('F10', None),
        _Key.f11: ('F11', None),
        _Key.f12: ('F12', None),
        _Key.num_lock: ('Num_Lock', None),
        _Key.scroll_lock: ('Scroll_Lock', None),
    }

    _ignore_keys = {
        _Key.mouse_left,
        _Key.mouse_right,
        _Key.mouse_middle,
        _Key.mouse_wheel_x,
        _Key.mouse_wheel_y,
    }


__all__ = ['RendererBackendImguiBundle']

@register_backend("imgui_bundle")
class RendererBackendImguiBundle(RendererBackend):
    def __init__(self, 
                 interactor: vtkRenderWindowInteractor, 
                 render_window: vtkRenderWindow,
                 border = False) -> None:
        if not imgui:
            raise ModuleNotFoundError(f"{self.__class__.__name__} requires the 'imgui_bundle' package.")
        super().__init__(interactor, render_window, border=border)

    def render(self, size: tuple[int, int] | None = None):
        if size is None:
            # get the maximum available size
            size = imgui.get_content_region_avail()
            size = (size.x, size.y)

        self.render_window.render(size)

        # adjust the size of this interactor as well
        self.interactor.SetSize(int(size[0]), int(size[1]))
        self.interactor.ConfigureEvent()

        # render the texture with the vtk output into an image
        imgui.push_style_var(imgui.StyleVar_.window_padding, (0, 0))
        # make the image unscrollable to ensure correct mouse behavior
        no_scroll_flags = imgui.WindowFlags_.no_scrollbar | imgui.WindowFlags_.no_scroll_with_mouse
        imgui.begin_child("##Viewport", size, self.border, no_scroll_flags)
        imgui.image(self.render_window.texture_id, 
                    imgui.get_content_region_avail(), 
                    (0, 1), (1, 0))
        # process the events of this widget
        self.process_events()
        imgui.end_child()
        imgui.pop_style_var()

    def _process_mouse_events(self, io):
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

    def _process_keyboard_events(self, xpos, ypos, ctrl, shift):
        if imgui.is_window_hovered():
            key_start = imgui.Key.named_key_begin.value
            key_end = imgui.Key.named_key_end.value
            
            # for each valid key check if it's state changed and emit the appropriate vtk event
            for k in range(key_start, key_end):
                k = imgui.Key(k)
                if k in _ignore_keys:
                    continue

                if imgui.is_key_pressed(k) or imgui.is_key_released(k):
                    try:
                        keysym, keychar = _keysyms[k]
                    except (KeyError):
                        keysym = None
                        keychar = None

                    keychar = keychar or '\0'

                    self.interactor.SetEventInformationFlipY(xpos, ypos, ctrl, shift, keychar, 0, keysym)
                    if imgui.is_key_pressed(k):
                        self.interactor.KeyPressEvent()
                        self.interactor.CharEvent()
                    else:
                        self.interactor.KeyReleaseEvent()

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
        if io.mouse_double_clicked[0] or io.mouse_double_clicked[1] or io.mouse_double_clicked[2]:
            repeat = 1

        if xpos < 0 or ypos < 0:
            return 
        
        self.interactor.SetEventInformationFlipY(xpos, ypos, ctrl, shift, chr(0), repeat, None)

        self._process_mouse_events(io)
        self._process_keyboard_events(xpos, ypos, ctrl, shift)

    def show(self, 
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
      