#!/bin/bash

set -eu

VER=$(grep -Po '(?<=^__version__ = ).*' ../heudiconv/info.py | sed 's/"//g')

docker run --rm kaczmarj/neurodocker:v0.3.2 generate -b debian:stretch -p apt \
    --dcm2niix version=v1.0.20180622 \
    --neurodebian os_codename=stretch download_server=usa-nh pkgs=git-annex-standalone \
    --install git gcc pigz \
    --copy . /src/heudiconv \
    --miniconda env_name=neuro conda_install="python=2 traits=4.6.0" activate=True \
      pip_install="https://github.com/moloney/dcmstack/tarball/master /src/heudiconv[all]" \
    --entrypoint "/neurodocker/startup.sh heudiconv" \
> ../Dockerfile
