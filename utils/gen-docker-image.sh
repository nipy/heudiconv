#!/bin/bash

set -eu

thisd=$(dirname $0)
VER=$(grep -Po '(?<=^__version__ = ).*' $thisd/../heudiconv/info.py | sed 's/"//g')

image="kaczmarj/neurodocker:0.9.1"

if hash podman; then
    OCI_BINARY=podman
elif hash docker; then
    OCI_BINARY=docker
else
    echo "ERROR: no podman or docker found" >&2
    exit 1
fi

${OCI_BINARY:-docker} run --rm $image generate docker \
    --base-image neurodebian:bookworm \
    --pkg-manager apt \
    --dcm2niix \
        version=v1.0.20240202 \
        method=source \
        cmake_opts="-DZLIB_IMPLEMENTATION=Cloudflare -DUSE_JPEGLS=ON -DUSE_OPENJPEG=ON" \
    --install \
        git \
        gcc \
        pigz \
        liblzma-dev \
        libc-dev \
        git-annex-standalone \
        netbase \
    --copy . /src/heudiconv \
    --miniconda \
        version="py39_4.12.0" \
        conda_install="python=3.9 traits>=4.6.0 scipy numpy nomkl pandas gdcm" \
        pip_install="/src/heudiconv[all]" \
        pip_opts="--editable" \
    --entrypoint "heudiconv" \
> $thisd/../Dockerfile
