from setuptools import setup
from pybind11.setup_helpers import Pybind11Extension

ext_modules = [
    Pybind11Extension(
        "backtester_cpp",
        ["cpp/backtester_cpp.cpp"],
    ),
]

setup(
    name="backtester_cpp",
    version="0.1.0",
    author="ATH Project",
    description="C++ accelerated backtesting extension for the ATH trading project.",
    ext_modules=ext_modules,
    zip_safe=False,
)
