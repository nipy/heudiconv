FROM continuumio/miniconda

MAINTAINER <satra@mit.edu>

RUN apt-get update && apt-get upgrade -y && apt-get install -y g++ && apt-get clean -y && apt-get autoclean -y && apt-get autoremove -y
RUN cd /tmp && git clone https://github.com/neurolabusc/dcm2niix.git && cd dcm2niix/console/ && git checkout 99bf011380c579c70323171f1aceb074ddbeb263 && g++ -O3 -I. main_console.cpp nii_dicom.cpp jpg_0XC3.cpp ujpeg.cpp nifti1_io_core.cpp nii_ortho.cpp nii_dicom_batch.cpp  -o dcm2niix -DmyDisableOpenJPEG -DmyDisableJasper && cp dcm2niix /usr/local/bin/ 
RUN conda install -y -c conda-forge nipype && pip install https://github.com/moloney/dcmstack/archive/c12d27d2c802d75a33ad70110124500a83e851ee.zip
RUN curl -O https://raw.githubusercontent.com/nipy/heudiconv/master/bin/heudiconv && chmod +x heudiconv && cp heudiconv /usr/local/bin/

ENTRYPOINT ["/usr/local/bin/heudiconv"]
