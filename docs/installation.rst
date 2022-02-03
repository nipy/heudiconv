============
Installation
============

``Heudiconv`` is packaged and available from many different sources.


Local
=====
Released versions of HeuDiConv are available on `PyPI <https://pypi.org/project/heudiconv/>`_
and `conda <https://github.com/conda-forge/heudiconv-feedstock#installing-heudiconv>`_.
If installing through ``PyPI``, eg::

    pip install heudiconv[all]

Manual installation of `dcm2niix <https://github.com/rordenlab/dcm2niix#install>`_
is required.

On Debian-based systems we recommend using `NeuroDebian <http://neuro.debian.net>`_
which provides the `heudiconv package <http://neuro.debian.net/pkgs/heudiconv.html>`_.


Docker
======
If `Docker <https://docs.docker.com/install/>`_ is available on your system, you
can visit `our page on Docker Hub <https://hub.docker.com/r/nipy/heudiconv/tags>`_
to view available releases. To pull the latest release, run::

    $ docker pull nipy/heudiconv:0.10.0


Singularity
===========
If `Singularity <https://www.sylabs.io/singularity/>`_ is available on your system,
you can use it to pull and convert our Docker images! For example, to pull and
build the latest release, you can run::

    $ singularity pull docker://nipy/heudiconv:0.10.0
