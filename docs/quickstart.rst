Quickstart
==========

Heudiconv Hello World: Using `heuristic.py`

.. TODO convert to a datalad dataset 
.. TODO ``datalad install https://osf.io/mqgzh/``
.. TODO delete any sequences of no interest prior to push, lets make the
   example ds only contain what is needed for these tutorials
.. TODO create a docker/podman section explaining how to use containers
   in lieu of `heudiconv`, change the tutorials to `heudiconv`, not
   container.
.. TODO convert bash script to docs

This section demonstrates how to use the heudiconv tool with `heuristic.py` to convert DICOMS into the BIDS data structure.

* Download and unzip `sub-219_dicom.zip <https://osf.io/mqgzh/>`_. You will see a directory called MRIS.
* Under the MRIS directory, is the *dicom* subdirectory: Under the subject number *219* the session *itbs* is nested.  Each dicom sequence folder is nested under the session.  You can delete sequences folders if they are of no interest::

    dicom
    └── 219
        └── itbs
            ├── Bzero_verify_PA_17
            ├── DTI_30_DIRs_AP_15
            ├── Localizers_1
            ├── MoCoSeries_19
            ├── MoCoSeries_31
            ├── Post_TMS_restingstate_30
            ├── T1_mprage_1mm_13
            ├── field_mapping_20
            ├── field_mapping_21
            └── restingstate_18


* Pull the HeuDiConv Docker container to your machine::

    docker pull nipy/heudiconv

* From a BASH shell (no, zsh will not do), navigate to the MRIS directory and run the ``hdc_run.sh`` script for subject *219*, session *itbs*, like this::

    #!/bin/bash
    
    : <<COMMENTBLOCK
    This code calls the docker heudiconv tool to convert DICOMS into the BIDS data structure.
    It requires that you are in the parent directory of both the Dicom and Nifti directories 
    AND that your Nifti directory contain a subdirectory called code with the conversion routine, e.g., heuristic.py in it. 
    See https://neuroimaging-core-docs.readthedocs.io/en/latest/pages/heudiconv.html.
    See also https://heudiconv.readthedocs.io/en/latest/
    COMMENTBLOCK
    
    
    # Exit if number of arguments is less than 3
    if [ $# -lt 3 ]
        then
            echo "======================================================"
            echo "Three arguments are required:"
            echo "argument 1: name of conversion file in the Nifti/code directory, e.g., heuristic.py"
            echo "argument 2: name of subject dicom folder to convert"
            echo "argument 3: optional name of the session"
            echo "e.g., $0 heuristic.py 219 itbs"
            echo "output will be a BIDS directory under the Nifti folder"
            echo "This assumes you are running docker"
            echo "and have downloaded heudiconv: docker pull nipy/heudiconv"
            echo "It also assumes that you are running from the parent directory to both dicom and Nifti"
            echo "If you have a session argument, this assumes your DICOMS are nested under subject and then session"
            echo "Finally, note that the dicoms are assumed to be *.dcm files"
            echo "======================================================"
            exit 1
    fi
    
    # Define the three variables
    converter=${1}
    subject=${2}
    session=${3}
    
    echo "Nifti/code/${converter} will be used to convert subject ${subject} and session ${session} under dicom"
    echo "to BIDS output under Nifti/sub-${subject} and session ${session}"
    
    # This docker command assumes you are in in the bound (-v) base directory, e.g., the unzipped MRIS directory (PWD).
    # dicom files are under dicom in a directory labeled with the subject number and session number (e.g. 219/itbs)
    # output (-o) will  be placed in the directory labeled Nifti
    # The conversion file is in Nifti/code 
    # dcm2niix is the engine that does the conversion
    # --minmeta guarantees that meta-information in the dcms does not get inserted into the JSON sidecar.
    # This is good because the information is not needed but can overflow the JSON file causing some BIDS apps to crash.
    
    docker run --rm -it -v ${PWD}:/base nipy/heudiconv:latest -d /base/dicom/{subject}/{session}/*/*.dcm -o /base/Nifti/ -f /base/Nifti/code/${converter} -s ${subject} -ss ${session} -c dcm2niix -b --minmeta --overwrite


.. TODO rm this command (note the args tho)
  ./hdc_run.sh heuristic1.py 219 itbs

* This should complete the conversion. After running, the *Nifti* directory will contain a bids-compliant subject directory::


    └── sub-219
        └── ses-itbs
            ├── anat
            ├── dwi
            ├── fmap
            └── func

* The following required BIDS text files are also created in the Nifti directory. Details for filling in these skeleton text files can be found under `tabular files <https://bids-specification.readthedocs.io/en/stable/02-common-principles.html#tabular-files>`_ in the BIDS specification::

    CHANGES
    README
    dataset_description.json
    participants.json
    participants.tsv
    task-rest_bold.json

* Next, visit the `bids validator <https://bids-standard.github.io/bids-validator/>`_.
* Click `Choose File` and then select the *Nifti* directory.  There should be no errors (though there are a couple of warnings).

  .. Note:: Your files are not uploaded to the BIDS validator, so there are no privacy concerns!
* Look at the directory structure and files that were generated.
* When you are ready, remove everything that was just created::

    rm -rf Nifti/sub-* Nifti/.heudiconv Nifti/code/__pycache__ Nifti/*.json Nifti/*.tsv Nifti/README Nifti/CHANGE

* Now you know what the results should look like.
* In the following sections, you will build *heuristic.py* yourself so you can test different options and understand how to work with your own data.



