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

    $ docker pull nipy/heudiconv:latest

Note that when using via ``docker run`` you might need to provide your user and group IDs so they map correspondingly
within container, i.e. like::

    $ docker run --user=$(id -u):$(id -g) -e "UID=$(id -u)" -e "GID=$(id -g)" --rm -t -v $PWD:$PWD nipy/heudiconv:latest [OPTIONS TO FOLLOW]

`ReproIn heuristic project <https://reproin.repronim.org>`_ provides its own Docker images from
Docker Hub `repronim/reproin` which bundle its `reproin` helper.

Singularity
===========
If `Singularity <https://www.sylabs.io/singularity/>`_ is available on your system,
you can use it to pull and convert our Docker images! For example, to pull and
build the latest release, you can run::

    $ singularity pull docker://nipy/heudiconv:latest

Singularity YODA style using ///repronim/containers
===================================================

ReproNim project provides `///repronim/containers <http://datasets.datalad.org/?dir=/repronim/containers>`_
(git clone present also on `GitHub <https://github.com/ReproNim/containers>`__) `DataLad
<https://datalad.org>`_ dataset with Singularity containers for many popular neuroimaging tools, e.g. all BIDS-Apps.
It also contains converted from Docker singularity images for stock heudiconv images (as `nipy-heudiconv
<https://github.com/ReproNim/containers/tree/master/images/nipy>`__) and reproin images (as `repronim-reproin
<https://github.com/ReproNim/containers/tree/master/images/repronim>`__). Please see `"A typical workflow"
<https://github.com/ReproNim/containers#a-typical-workflow>`_ section for a prototypical example of using
`datalad-container <https://github.com/datalad/datalad-container/>`_ extension with this dataset, while fulfilling
`YODA principles <https://github.com/myyoda/poster/blob/master/ohbm2018.pdf>`_.  **Note** that it should also work on
OSX with ``///repronim/containers`` automagically taking care about running those Singularity containers via Docker.