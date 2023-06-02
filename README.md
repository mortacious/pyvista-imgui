# Pyvista-Imgui

[![PyPi license](https://badgen.net/pypi/license/pyvista-imgui/)](https://pypi.org/project/pyvista-imgui/) [![PyPi version](https://badgen.net/pypi/v/pyvista-imgui/)](https://pypi.org/project/pyvista-imgui/)

`pyvista-imgui` is a small helper module for the [`pyvista`](https://github.com/pyvista/pyvista)-package to integrate it with the [imgui](https://github.com/ocornut/imgui)-library. 

It integrates a fully interactive `pyvista`-Plotter as an imgui-widget, by utilizing VTK's `vtkGenericOpenGLRenderWindow` to first render the output into an OpenGL texture and displaying it as a regular imgui-image widget.

It currently utilizes either the bindings provided by [`imgui-bundle`](https://github.com/ocornut/imgui), or by [`pyimgui`](https://github.com/pyimgui/pyimgui/tree/master).

This package is considered experimental at this moment, so expect issues.

## Installation5

To install this package using `pip` use:

```bash
pip install pyvista-imgui[imgui-bundle]
```

for the `imgui-bundle` bindings or:

```bash
pip install pyvista-imgui[imgui]
```

for the `pyimgui` bindings.

Alternatively the installation from source is also possible with:

```bash
git clone https://github.com/mortacious/pyvista-imgui
cd pyvista-imgui
pip install [-e] .[imgui-bundle / imgui] 
```

## Usage

The package includes the class `ImguiPlotter`, which can be used as a drop-in alternative to the regular `pyvista`-plotters:

```py
import pyvista as pv
from pyvista_imgui import ImguiPlotter

sphere = pv.Sphere()

plotter = ImguiPlotter()
plotter.add_axes()
plotter.add_mesh(sphere)
plotter.show()
```

Alternatively, an instance of `ImguiPlotter` can be integrated into an existing imgui-UI as a widget:

```py
imgui.begin("Imgui Plotter")
# render the plotter's contents here
plotter.render()
imgui.end()
```