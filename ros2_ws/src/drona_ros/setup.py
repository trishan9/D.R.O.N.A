from setuptools import find_packages, setup

package_name = "drona_ros"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Trisan Wagle",
    maintainer_email="trisan.wagle@softwarica.edu.np",
    description="ROS2 nodes for D.R.O.N.A.",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "advising_node    = drona_ros.advising_node:main",
            "gesture_node     = drona_ros.gesture_node:main",
            "perception_node  = drona_ros.perception_node:main",
            "orchestrator_node = drona_ros.orchestrator_node:main",
        ],
    },
)
