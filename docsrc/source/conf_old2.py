from pygments.lexers import CLexer
from pygments.token import Comment
from pygments.lexer import inherit, bygroups
from os.path import relpath, dirname
import inspect
import math
import numpy
import os
import re
import sys
import importlib

from distutils.util import convert_path
import os
import sys
sys.path.insert(0, os.path.abspath('../..'))

# Get the version from the _version file within the package directory
driptorch_ns = {}
version_path = convert_path('../../driptorch/_version.py')
with open(version_path) as f:
    exec(f.read(), driptorch_ns)

# -- Project information -----------------------------------------------------

project = 'DripTorch'
copyright = '2022, Silvx Labs LLC'

# The full version, including alpha/beta/rc tags
release = driptorch_ns['__version__']

# Minimum version, enforced by sphinx
needs_sphinx = '4.3'


# must be kept alive to hold the patched names
_name_cache = {}


# -----------------------------------------------------------------------------
# General configuration
# -----------------------------------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.

sys.path.insert(0, os.path.abspath('../sphinxext'))

extensions = [
    'sphinx.ext.autodoc',
    'numpydoc',
    'sphinx.ext.intersphinx',
    'sphinx.ext.coverage',
    'sphinx.ext.doctest',
    'sphinx.ext.autosummary',
    'sphinx.ext.graphviz',
    'sphinx.ext.ifconfig',
    'sphinx.ext.mathjax',
    'myst_parser'

]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

autosummary_generate = True

# The suffix of source filenames.
source_suffix = '.rst'


# There are two options for replacing |today|: either, you set today to some
# non-false value, then it is used:
#today = ''
# Else, today_fmt is used as the format for a strftime call.
today_fmt = '%B %d, %Y'

# List of documents that shouldn't be included in the build.
#unused_docs = []

# The reST default role (used for this markup: `text`) to use for all documents.
default_role = "autolink"

# List of directories, relative to source directories, that shouldn't be searched
# for source files.
exclude_dirs = []

# If true, '()' will be appended to :func: etc. cross-reference text.
add_function_parentheses = False

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
#add_module_names = True

# If true, sectionauthor and moduleauthor directives will be shown in the
# output. They are ignored by default.
#show_authors = False


# While these objects do have type `module`, the names are aliases for modules
# elsewhere. Sphinx does not support referring to modules by an aliases name,
# so we make the alias look like a "real" module for it.
# If we deemed it desirable, we could in future make these real modules, which
# would make `from numpy.char import split` work.
sys.modules['numpy.char'] = numpy.char
sys.modules['numpy.testing.dec'] = numpy.testing.dec

# -----------------------------------------------------------------------------
# HTML output
# -----------------------------------------------------------------------------

html_theme = 'pydata_sphinx_theme'

html_favicon = '_static/favicon/favicon.ico'

html_theme_options = {
    "logo": {
        "image_light": "logo.svg",
        "image_dark": "logo.svg",
    },
    "github_url": "https://github.com/numpy/numpy",
    "twitter_url": "https://twitter.com/numpy_team",
    "collapse_navigation": True,
    "external_links": [
        {"name": "Learn", "url": "https://numpy.org/numpy-tutorials/"}
    ],
    # Add light/dark mode and documentation version switcher:
    "navbar_end": ["theme-switcher", "navbar-icon-links"],
}

html_title = "%s Manual" % (project)
html_static_path = ['_static']
html_last_updated_fmt = '%b %d, %Y'
html_css_files = ["numpy.css"]
html_context = {"default_mode": "light"}
html_use_modindex = True
html_copy_source = False
html_domain_indices = False
html_file_suffix = '.html'

htmlhelp_basename = 'numpy'

if 'sphinx.ext.pngmath' in extensions:
    pngmath_use_preview = True
    pngmath_dvipng_args = ['-gamma', '1.5', '-D', '96', '-bg', 'Transparent']

mathjax_path = "scipy-mathjax/MathJax.js?config=scipy-mathjax"

plot_html_show_formats = False
plot_html_show_source_link = False


# -----------------------------------------------------------------------------
# Intersphinx configuration
# -----------------------------------------------------------------------------
intersphinx_mapping = {
    'neps': ('https://numpy.org/neps', None),
    'python': ('https://docs.python.org/3', None),
    'scipy': ('https://docs.scipy.org/doc/scipy', None),
    'matplotlib': ('https://matplotlib.org/stable', None),
    'imageio': ('https://imageio.readthedocs.io/en/stable', None),
    'skimage': ('https://scikit-image.org/docs/stable', None),
    'pandas': ('https://pandas.pydata.org/pandas-docs/stable', None),
    'scipy-lecture-notes': ('https://scipy-lectures.org', None),
    'pytest': ('https://docs.pytest.org/en/stable', None),
    'numpy-tutorials': ('https://numpy.org/numpy-tutorials', None),
    'numpydoc': ('https://numpydoc.readthedocs.io/en/latest', None),
    'dlpack': ('https://dmlc.github.io/dlpack/latest', None)
}


# -----------------------------------------------------------------------------
# NumPy extensions
# -----------------------------------------------------------------------------

# If we want to do a phantom import from an XML file for all autodocs
phantom_import_file = 'dump.xml'

# Make numpydoc to generate plots for example sections
numpydoc_use_plots = True

# -----------------------------------------------------------------------------
# Autosummary
# -----------------------------------------------------------------------------

autosummary_generate = True

# -----------------------------------------------------------------------------
# Coverage checker
# -----------------------------------------------------------------------------
coverage_ignore_modules = r"""
    """.split()
coverage_ignore_functions = r"""
    test($|_) (some|all)true bitwise_not cumproduct pkgload
    generic\.
    """.split()
coverage_ignore_classes = r"""
    """.split()
