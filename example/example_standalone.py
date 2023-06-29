import pyvista as pv
from pyvista_imgui import ImguiPlotter

sphere = pv.Sphere()

plotter = ImguiPlotter(backend='imgui_bundle')
plotter.add_axes()
plotter.add_mesh(sphere, render=False)
plotter.show()