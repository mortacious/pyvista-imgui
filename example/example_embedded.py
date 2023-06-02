import pyvista as pv
import vtk
from imgui_pyvista import ImguiPlotter
from imgui_bundle import immapp, imgui, hello_imgui

sphere = pv.Sphere()


plotter = ImguiPlotter()
plotter.add_axes()
plotter.add_mesh(sphere, render=False)

runner_params = hello_imgui.RunnerParams()
runner_params.app_window_params.window_title = "Viewer"
runner_params.app_window_params.window_geometry.size = (1400, 1080)
runner_params.imgui_window_params.show_status_bar = True

def gui():
    hello_imgui.apply_theme(hello_imgui.ImGuiTheme_.imgui_colors_dark)
    vec = imgui.get_main_viewport().pos
    imgui.set_next_window_pos(vec, imgui.Cond_.once)
    imgui.set_next_window_size(imgui.get_main_viewport().size)
    imgui.set_next_window_bg_alpha(1.0)
    imgui.begin("Imgui Plotter", flags=imgui.WindowFlags_.no_bring_to_front_on_focus | imgui.WindowFlags_.no_title_bar | imgui.WindowFlags_.no_decoration | imgui.WindowFlags_.no_resize | imgui.WindowFlags_.no_move)

    # render the plotter's contents here
    plotter.render()

    imgui.end()
    imgui.show_demo_window()


runner_params.callbacks.show_gui = gui
# IMPORTANT: hello_imgui has a special default window type, that prevets interaction when the Plotter is forced to the background. To prevent this, we disable it here.
runner_params.imgui_window_params.default_imgui_window_type = hello_imgui.DefaultImGuiWindowType.no_default_window
immapp.run(runner_params=runner_params, add_ons_params=addons)