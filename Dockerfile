
FROM continuumio/miniconda

MAINTAINER <satra@mit.edu>

RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y g++ pkg-config make && \
    apt-get clean -y && apt-get autoclean -y && apt-get autoremove -y
RUN (wget -O- http://neuro.debian.net/lists/jessie.us-nh.full | tee /etc/apt/sources.list.d/neurodebian.sources.list) && \
    apt-key adv --recv-keys --keyserver hkp://pool.sks-keyservers.net:80 0xA5D32F012649A5A9 && \
    apt-get update -qq && apt-get install -y git-annex-standalone && \
    apt-get clean -y && apt-get autoclean -y && apt-get autoremove -y
RUN conda install -y -c conda-forge nipype && \
    conda install cmake && \
    pip install https://github.com/moloney/dcmstack/archive/c12d27d2c802d75a33ad70110124500a83e851ee.zip && \
    pip install datalad && \
    conda clean -tipsy && rm -rf ~/.pip/
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y pigz && \
    apt-get clean -y && apt-get autoclean -y && apt-get autoremove -y && \
    cd /tmp && git clone https://github.com/neurolabusc/dcm2niix.git && \
    cd dcm2niix && \
    git checkout 6ba27b9befcbae925209664bb8acbb00e266114a && \
    mkdir build && cd build && cmake -DBATCH_VERSION=ON .. && \
    make && make install && \
    cd / && rm -rf /tmp/dcm2niix

COPY bin/heudiconv /usr/local/bin/heudiconv
RUN chmod +x /usr/local/bin/heudiconv
RUN mkdir /heuristics
COPY heuristics/convertall.py /heuristics
RUN chmod +x /heuristics/convertall.py
RUN git config --global user.email "test@docker.land" && \
    git config --global user.name "Docker Almighty"

ENTRYPOINT ["/usr/local/bin/heudiconv"]
