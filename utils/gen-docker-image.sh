#!/bin/bash

set -eu

thisd=$(dirname $0)
VER=$(grep -Po '(?<=^__version__ = ).*' $thisd/../heudiconv/info.py | sed 's/"//g')

image="kaczmarj/neurodocker:0.9.1"

docker run --rm $image generate docker -b neurodebian:bullseye -p apt \
    --dcm2niix version=v1.0.20220720 method=source \
    --install git gcc pigz liblzma-dev libc-dev git-annex-standalone netbase \
    --copy . /src/heudiconv \
    --miniconda version="py39_4.12.0" conda_install="python=3.9 traits>=4.6.0 scipy numpy nomkl pandas" \
      pip_install="/src/heudiconv[all]" \
      pip_opts="--editable" \
    --entrypoint "heudiconv" \
> $thisd/../Dockerfile
