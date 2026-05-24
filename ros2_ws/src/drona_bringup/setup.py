from setuptools import find_packages, setup
import os
from glob import glob

package_name = "drona_bringup"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.py")),
        (os.path.join("share", package_name, "config"), glob("config/*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Trisan Wagle",
    maintainer_email="trisan.wagle@softwarica.edu.np",
    description="Launch files for D.R.O.N.A.",
    license="MIT",
)
