import pathlib
from setuptools import setup, find_packages
from distutils.util import convert_path

# Get the version from the _version file within the package directory
driptorch_ns = {}
version_path = convert_path('driptorch/_version.py')
with open(version_path) as f:
    exec(f.read(), driptorch_ns)

# The directory containing this file
HERE = pathlib.Path(__file__).parent

# The text of the README file
README = (HERE / "README.md").read_text()

# Set 'er up
setup(
    name='driptorch',
    packages=find_packages(),
    version=driptorch_ns['__version__'],
    license='MIT',
    description='Ignition pattern simulator for prescribed firing techniques',
    long_description=README,
    long_description_content_type="text/markdown",
    author='Silvx Labs',
    author_email='lucas@silvxlabs.com',
    url='https://github.com/silvxlabs/DripTorch',
    keywords=['ignition pattern', 'fire',
              'firing techniques', 'prescribed burn'],
    install_requires=[
        'Shapely==1.8.2',
        'awkward==1.8.0',
        'numpy==1.22.4',
        'pandas==1.4.2',
        'pyproj==3.3.1',
        'folium==0.12.1.post1'
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
)
