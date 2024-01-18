================
Reproin 
================

If you don't want to modify a Python file as you did for *heuristic.py*, an alternative is to name your image sequences at the scanner using the *reproin* naming convention. Take some time getting the scanner protocol right, because it is the critical job for running *reproin*. Then a single Docker command converts your DICOMS to the BIDS data structure. There are more details about *reproin* in the 
.. TODO new link ref:`Links <heudiconv_links>` section above.

* You should already have Docker installed and have downloaded HeuDiConv as described in Lesson 1.
* Download and unzip the phantom dataset: `reproin_dicom.zip <https://osf.io/4jwk5/>`_ generated here at the University of Arizona on our Siemens Skyra 3T with Syngo MR VE11c software on 2018_02_08.
* You should see a new directory *REPROIN*. This is a simple reproin-compliant dataset without sessions. Derived dwi images (ADC, FA etc.) that the scanner produced were removed.
* Change directory to *REPROIN*. The directory structure should look like this::

    REPROIN
    ├── data
    └── dicom
        └── 001
            └── Patterson_Coben\ -\ 1
                ├── Localizers_4
                ├── anatT1w_acqMPRAGE_6
                ├── dwi_dirAP_9
                ├── fmap_acq4mm_7
                ├── fmap_acq4mm_8
                ├── fmap_dirPA_15
                └── func_taskrest_16

* From the *REPROIN* directory, run this Docker command::

    docker run --rm -it -v ${PWD}:/base nipy/heudiconv:latest -f reproin --bids  -o /base/data --files /base/dicom/001 --minmeta
* ``--rm`` means Docker should cleanup after itself
* ``-it`` means Docker should run interactively
* ``-v ${PWD}:/base`` binds your current directory to ``/base`` inside the container.  Alternatively, you could provide an **absolute path** to the *REPROIN* directory.
* ``nipy/heudiconv:latest`` identifies the Docker container to run (the latest version of heudiconv).
* ``-f reproin`` specifies the converter file to use
* ``-o /base/data/`` specifies the output directory *data*.  If the output directory does not exist, it will be created.
* ``--files /base/dicom/001`` identifies the path to the DICOM files.
*  ``--minmeta`` ensures that only the minimum necessary amount of data gets added to the JSON file when created.  On the off chance that there is a LOT of meta-information in the DICOM header, the JSON file will not get swamped by it. fmriprep and mriqc are very sensitive to this information overload and will crash, so minmeta provides a layer of protection against such corruption.

That's it.  Below we'll unpack what happened.

Output Directory Structure
===============================

*Reproin* produces a hierarchy of BIDS directories like this::

    data
    └── Patterson
        └── Coben
            ├── sourcedata
            │   └── sub-001
            │       ├── anat
            │       ├── dwi
            │       ├── fmap
            │       └── func
            └── sub-001
                ├── anat
                ├── dwi
                ├── fmap
                └── func


* The dataset is nested under two levels in the output directory: *Region* (Patterson) and *Exam* (Coben). *Tree* is reserved for other purposes at the UA research scanner.
* Although the Program *Patient* is not visible in the output hierarchy, it is important.  If you have separate sessions, then each session should have its own Program name.
* **sourcedata** contains tarred gzipped (tgz) sets of DICOM images corresponding to each NIFTI image.
* **sub-001** contains the BIDS dataset.
* The hidden directory is generated: *REPROIN/data/Patterson/Coben/.heudiconv*.

At the Scanner
====================

Here is this phantom dataset displayed in the scanner dot cockpit.  The directory structure is defined at the top: *Patterson >> Coben >> Patient*

* *Region* = *Patterson*
* *Exam* = *Coben*
* *Program* = *Patient*



Reproin Scanner File Names
==============================

* For both BIDS and *reproin*, names are composed of an ordered series of key-value pairs.  Each key and its value are joined with a dash ``-`` (e.g., ``acq-MPRAGE``, ``dir-AP``).  These key-value pairs are joined to other key-value pairs with underscores ``_``. The exception is the modality label, which is discussed more below.
* *Reproin* scanner sequence names are simplified relative to the final BIDS output and generally conform to this scheme (but consult the `reference <https://github.com/nipy/heudiconv/blob/master/heudiconv/heuristics/reproin.py>`_ for additional options): ``sequence type-modality label`` _ ``session-session name`` _ ``task-task name`` _ ``acquisition-acquisition detail`` _ ``run-run number`` _ ``direction-direction label``::

    | func-bold_ses-pre_task-faces_acq-1mm_run-01_dir-AP

* Each sequence name begins with the seqtype key. The seqtype key is the modality and corresponds to the name of the BIDS directory where the sequence belongs, e.g., ``anat``, ``dwi``, ``fmap`` or ``func``.
* The seqtype key is optionally followed by a dash ``-`` and a modality label value (e.g., ``anat-scout`` or ``anat-T2W``). Often, the modality label is not needed because there is a predictable default for most seqtypes:
* For **anat** the default modality is ``T1W``.  Thus a sequence named ``anat`` will have the same output BIDS files as a sequence named ``anat-T1w``: *sub-001_T1w.nii.gz*.
* For **fmap** the default modality is ``epi``.  Thus ``fmap_dir-PA`` will have the same output as ``fmap-epi_dir-PA``: *sub-001_dir-PA_epi.nii.gz*.
* For **func** the default modality is ``bold``. Thus, ``func-bold_task-rest`` will have the same output as ``func_task-rest``: *sub-001_task-rest_bold.nii.gz*.
* *Reproin* gets the subject number from the DICOM metadata.
* If you have multiple sessions, the session name does not need to be included in every sequence name in the program (i.e., Program= *Patient* level mentioned above).  Instead, the session can be added to a single sequence name, usually the scout (localizer) sequence e.g. ``anat-scout_ses-pre``, and *reproin* will propagate the session information to the other sequence names in the *Program*. Interestingly, *reproin* does not add the localizer to your BIDS output.
* When our scanner exports the DICOM sequences, all dashes are removed. But don't worry, *reproin* handles this just fine.
* In the UA phantom reproin data, the subject was named ``01``.  Horos reports the subject number as ``01`` but exports the DICOMS into a directory ``001``.  If the data are copied to an external drive at the scanner, then the subject number is reported as ``001_001`` and the images are ``*.IMA`` instead of ``*.dcm``.  *Reproin* does not care, it handles all of this gracefully.  Your output tree (excluding *sourcedata* and *.heudiconv*) should look like this::

    .
    |-- CHANGES
    |-- README
    |-- dataset_description.json
    |-- participants.tsv
    |-- sub-001
    |   |-- anat
    |   |   |-- sub-001_acq-MPRAGE_T1w.json
    |   |   `-- sub-001_acq-MPRAGE_T1w.nii.gz
    |   |-- dwi
    |   |   |-- sub-001_dir-AP_dwi.bval
    |   |   |-- sub-001_dir-AP_dwi.bvec
    |   |   |-- sub-001_dir-AP_dwi.json
    |   |   `-- sub-001_dir-AP_dwi.nii.gz
    |   |-- fmap
    |   |   |-- sub-001_acq-4mm_magnitude1.json
    |   |   |-- sub-001_acq-4mm_magnitude1.nii.gz
    |   |   |-- sub-001_acq-4mm_magnitude2.json
    |   |   |-- sub-001_acq-4mm_magnitude2.nii.gz
    |   |   |-- sub-001_acq-4mm_phasediff.json
    |   |   |-- sub-001_acq-4mm_phasediff.nii.gz
    |   |   |-- sub-001_dir-PA_epi.json
    |   |   `-- sub-001_dir-PA_epi.nii.gz
    |   |-- func
    |   |   |-- sub-001_task-rest_bold.json
    |   |   |-- sub-001_task-rest_bold.nii.gz
    |   |   `-- sub-001_task-rest_events.tsv
    |   `-- sub-001_scans.tsv
    `-- task-rest_bold.json

* Note that despite all the the different subject names (e.g., ``01``, ``001`` and ``001_001``), the subject is labeled ``sub-001``.


