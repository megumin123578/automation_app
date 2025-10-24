# setup.py
from setuptools import setup
from Cython.Build import cythonize

setup(
  ext_modules=cythonize(["mymodule.pyx"], compiler_directives={'language_level': "4"})
)
