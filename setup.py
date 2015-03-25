import os
from setuptools import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "bureaucrat",
    version = "0.0.1",
    author = "Dmitry Rozhkov",
    author_email = "dmitry.rojkov@gmail.com",
    description = ("Workflow engine."),
    license = "GPL",
    keywords = "workflow",
    url = "http://packages.python.org/an_example_pypi_project",
    packages = ['bureaucrat', 'bureaucrat.workers'],
    install_requires = [],
    long_description=read('README.rst'),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Utilities",
        "License :: OSI Approved :: GPL License",
    ],
    entry_points={
        'worker.plugins': [
            'participant1 = bureaucrat.workers.participant1:Worker.factory',
            'participant2 = bureaucrat.workers.participant2:Worker.factory'
        ]
    }
)
