Quickstart
==========

This tutorial is based on `Dianne Patterson's University of Arizona tutorials <https://neuroimaging-core-docs.readthedocs.io/en/latest/pages/heudiconv.html#lesson-3-reproin-py>`_

This guide assumes you have already :ref:`installed heudiconv and dcm2niix <install_local>` and 
demonstrates how to use the heudiconv tool with a provided `heuristic.py` to convert DICOMS into the BIDS data structure.

.. _prepare_dataset:

Prepare Dataset
***************

Download and unzip `sub-219_dicom.zip <https://datasets.datalad.org/?dir=/repronim/heudiconv-tutorial-example/>`_. 

We will be working from a directory called MRIS. Under the MRIS directory is the *dicom* subdirectory: Under the subject number *219* the session *itbs* is nested.  Each dicom sequence folder is nested under the session::

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
    Nifti
    └── code 
        └── heuristic1.py

Basic Conversion
****************

Next we will use heudiconv convert DICOMS into the BIDS data structure.
The example dataset includes an example heuristic file, `heuristic1.py`.
Typical use of heudiconv will require the creation and editing of your :doc:`heuristics file <heuristics>`, which we will cover
in a :doc:`later tutorial <custom-heuristic>`.

    .. note:: Heudiconv requires you to run the command from the parent
              directory of both the Dicom and Nifti directories, which is `MRIS` in
              our case.

Run the following command::

    heudiconv  --files dicom/219/itbs/*/*.dcm -o Nifti -f Nifti/code/heuristic1.py -s 219 -ss itbs -c dcm2niix -b --minmeta --overwrite


* We specify the dicom files to convert with `--files`
* The heuristic file is provided with the `-f` option
* We tell heudiconv to place our output in the Nifti dir with `-o`
* `-b` indicates that we want to output in BIDS format
* `--minmeta` guarantees that meta-information in the dcms does not get inserted into the JSON sidecar. This is good because the information is not needed but can overflow the JSON file causing some BIDS apps to crash.

Output
******
    
The *Nifti* directory will contain a bids-compliant subject directory::
    
    
        └── sub-219
            └── ses-itbs
                ├── anat
                ├── dwi
                ├── fmap
                └── func
    
The following required BIDS text files are also created in the Nifti directory. Details for filling in these skeleton text files can be found under `tabular files <https://bids-specification.readthedocs.io/en/stable/02-common-principles.html#tabular-files>`_ in the BIDS specification::
    
        CHANGES
        README
        dataset_description.json
        participants.json
        participants.tsv
        task-rest_bold.json
    
Validation
**********

Ensure that everything is according to spec by using `bids validator <https://bids-standard.github.io/bids-validator/>`_ 

Click `Choose File` and then select the *Nifti* directory.  There should be no errors (though there are a couple of warnings).
    
      .. Note:: Your files are not uploaded to the BIDS validator, so there are no privacy concerns!
    
Next 
****

In the following sections, you will modify *heuristic.py* yourself so you can test different options and understand how to work with your own data.
