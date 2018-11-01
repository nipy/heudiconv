#!/bin/bash

set -eu

VER=$(grep -Po '(?<=^__version__ = ).*' ../heudiconv/info.py | sed 's/"//g')

docker run --rm kaczmarj/neurodocker:0.4.1 generate docker -b neurodebian:stretch -p apt \
    --dcm2niix version=v1.0.20180622 method=source \
    --install git gcc pigz liblzma-dev libc-dev git-annex-standalone \
    --copy . /src/heudiconv \
    --miniconda create_env=neuro conda_install="python=3.6 traits>=4.6.0" activate=True \
      pip_install="/src/heudiconv[all]" \
    --entrypoint "/neurodocker/startup.sh heudiconv" \
> ../Dockerfile
