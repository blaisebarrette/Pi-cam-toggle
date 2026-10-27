# coding=utf-8
from setuptools import setup

setup(
    name="OctoPrint-CamToggle",
    version="0.3.2",
    description="Turn the Raspberry Pi camera service on/off from OctoPrint",
    license="MIT",
    packages=["octoprint_camtoggle"],
    include_package_data=True,
    package_data={"octoprint_camtoggle": ["templates/*", "static/js/*"]},
    python_requires=">=3.7,<4",
    install_requires=["OctoPrint>=1.5.0"],
    entry_points={"octoprint.plugin": ["camtoggle = octoprint_camtoggle"]},
    zip_safe=False,
)
