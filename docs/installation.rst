============
Installation
============

``Heudiconv`` is packaged and available from many different sources.

.. _install_local:

Local
=====
Released versions of HeuDiConv are available on `PyPI <https://pypi.org/project/heudiconv/>`_
and `conda <https://github.com/conda-forge/heudiconv-feedstock#installing-heudiconv>`_.
If installing through ``PyPI``, eg::

    pip install heudiconv[all]

Manual installation of `dcm2niix <https://github.com/rordenlab/dcm2niix#install>`_
is required. You can also benefit from an installer/downloader helper ``dcm2niix`` package
on ``PyPI``, so you can simply ``pip install dcm2niix`` if you are installing in user space so
subsequently it would be able to download and install dcm2niix binary.

On Debian-based systems, we recommend using `NeuroDebian <http://neuro.debian.net>`_,
which provides the `heudiconv package <http://neuro.debian.net/pkgs/heudiconv.html>`_.

.. _install_container:

Containers
==========

Our container image releases are availe on `our Docker Hub <https://hub.docker.com/r/nipy/heudiconv/tags>`_

If `Docker <https://docs.docker.com/install/>`_ is available on your system, you can pull the latest release::

    $ docker pull nipy/heudiconv:latest

Additionally, HeuDiConv is available through the Docker image at `repronim/reproin <https://hub.docker.com/r/repronim/reproin>`_ provided by
`ReproIn heuristic project <http://reproin.repronim.org>`_, which develops the ``reproin`` heuristic.

To maintain provenance, it is recommended that you use the ``latest`` tag only when testing out heudiconv. 
Otherwise, it is recommended that you use an explicit version and record that information alongside the produced data.


Singularity
===========
If `Singularity <https://www.sylabs.io/singularity/>`_ is available on your system,
you can use it to pull and convert our Docker images! For example, to pull and
build the latest release, you can run::

    $ singularity pull docker://nipy/heudiconv:latest


Singularity YODA style using ///repronim/containers
===================================================
`ReproNim <https://www.repronim.org/>`_ provides a large collection of Singularity container images of popular
neuroimaging tools, e.g. all the BIDS-Apps. This collection also includes the forementioned container
images for `HeuDiConv <https://github.com/ReproNim/containers/tree/master/images/nipy>`_ and
`ReproIn <https://github.com/ReproNim/containers/tree/master/images/repronim>`_ in the Singularity image format. This collection is available as a
`DataLad <https://datalad.org>`_ dataset at `///repronim/containers <http://datasets.datalad.org/?dir=/repronim/containers>`_
on `datasets.datalad.org <http://datasets.datalad.org>`_ and as `a GitHub repo <https://github.com/ReproNim/containers>`_.
The HeuDiConv and ReproIn container images are named ``nipy-heudiconv`` and ``repronim-reproin``, respectively, in this collection.
To use them, you can install the DataLad dataset and then use the ``datalad containers-run`` command to run.
For a more detailed example of using images from this collection while fulfilling
the `YODA Principles <https://github.com/myyoda/poster/blob/master/ohbm2018.pdf>`_, please check out
`A typical YODA workflow <https://github.com/ReproNim/containers#a-typical-yoda-workflow>`_ in
the documentation of this collection.

**Note:** With the ``datalad containers-run`` command, the images in this collection work on macOS (OSX)
as well for ``repronim/containers`` helpers automagically take care of running the Singularity containers via Docker.
