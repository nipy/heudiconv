FROM python:3.10-alpine AS builder

RUN apk add bash \
  gcc \
  g++ \
  libc-dev \
  make \
  cmake \
  util-linux-dev \
  curl \
  git
RUN pip install --no-cache-dir pylibjpeg-libjpeg traits==6.3.2

ARG DCM2NIIX_VERSION=v1.0.20240202
RUN git clone https://github.com/rordenlab/dcm2niix /tmp/dcm2niix \
  && cd /tmp/dcm2niix \
  && git fetch --tags \
  && git checkout $DCM2NIIX_VERSION \
  && mkdir /tmp/dcm2niix/build \
  && cd /tmp/dcm2niix/build \
  && cmake -DZLIB_IMPLEMENTATION=Cloudflare -DUSE_JPEGLS=ON -DUSE_OPENJPEG=ON -DCMAKE_INSTALL_PREFIX:PATH=/usr/ .. \
  && make -j1 \
  && make install \
  && rm -rf /tmp/dcm2niix

FROM python:3.10-alpine
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/bin/dcm2niix /usr/bin/dcm2niix

RUN apk update && apk add --no-cache git git-annex pigz gcompat

RUN pip install --no-cache-dir heudiconv

ENTRYPOINT ["heudiconv"]
