# coding=utf-8
from setuptools import setup

setup(
    name="OctoPrint-CamToggle",
    version="0.2.0",
    description="Active/désactive le service caméra du Raspberry Pi depuis OctoPrint",
    license="MIT",
    packages=["octoprint_camtoggle"],
    include_package_data=True,
    package_data={"octoprint_camtoggle": ["templates/*", "static/js/*"]},
    python_requires=">=3.7,<4",
    install_requires=["OctoPrint>=1.5.0"],
    entry_points={"octoprint.plugin": ["camtoggle = octoprint_camtoggle"]},
    zip_safe=False,
)
