=========================
Custom Heuristics
=========================

This tutorial is based on `Dianne Patterson's University of Arizona tutorials <https://neuroimaging-core-docs.readthedocs.io/en/latest/pages/heudiconv.html#lesson-3-reproin-py>`_


In this tutorial we go more in depth, creating our own *heuristic.py* and modifying it for our needs:

1. :ref:`Step1 <heudiconv_step1>` Generate a heuristic (translation) file skeleton and some associated descriptor text files.
2. :ref:`Step2 <heudiconv_step2>` Modify the *heuristic.py* to specify BIDS output names and directories, and the input DICOM characteristics.
3. :ref:`Step3 <heudiconv_step3>` Call HeuDiConv to run on more subjects and sessions.

**Prerequisites**:

1. Ensure :ref:`heudiconv and dcm2niix <install_local>` is installed.
2. :ref:`Prepare the dataset <prepare_dataset>` used in the quickstart.

.. _heudiconv_step1:

Step 1: Generate Skeleton
*************************

.. note:: Step 1 only needs to be completed once for each project.
   If repeating this step, ensure that the .heudiconv directory is removed.

From the *MRIS* directory, run the following command to process the ``dcm`` files that you downloaded and unzipped for this tutorial.::

    heudiconv --files dicom/219/*/*/*.dcm -o Nifti/ -f convertall -s 219 -c none

* ``--files dicom/{subject}/*/*/*.dcm`` identifies the path to the DICOM files and specifies that they have the extension ``.dcm`` in this case.
* ``-o Nifti/`` is the output in *Nifti*.  If the output directory does not exist, it will be created.
* ``-f convertall`` This creates a *heuristic.py* template from an existing heuristic module. There are `other heuristic modules <https://github.com/nipy/heudiconv/tree/master/heudiconv/heuristics>`_ , but *convertall* is a good default.
* ``-s 219`` specifies the subject number.
* ``-c none`` indicates you are not actually doing any conversion right now.

You will now have a heudiconv skeleton in the `<output_dir>/.heudiconv` directory, in our case `Nifti/.heudiconv`

The ``.heudiconv`` hidden directory
======================================

Take a look at *MRIS/Nifti/.heudiconv/219/info/*, heudiconv has produced two files of interest: a skeleton *heuristic.py* and a *dicominfo.tsv* file.
The generated heuristic file template contains comments explaining usage.

.. warning::
    * **The Good** Every time you run conversion to create the BIDS NIfTI files and directories, a detailed record of what you did is recorded in the *.heudiconv* directory.  This includes a copy of the *heuristic.py* module that you ran for each subject and session. Keep in mind that the hidden *.heudiconv* directory gets updated every time you run heudiconv. Together your *code* and *.heudiconv* directories provide valuable provenance information that should remain with your data.
    * **The Bad** If you rerun *heuristic.py* for some subject and session that has already been run, heudiconv quietly uses the conversion routines it stored in *.heudiconv*.  This can be really annoying if you are troubleshooting *heuristic.py*.
    * **More Good** You can remove subject and session information from *.heudiconv* and run it fresh.  In fact, you can entirely remove the *.heudiconv* directory and still run the *heuristic.py* you put in the *code* directory.


.. _heudiconv_step2:

Step 2: Modify Heuristic
************************

.. TODO Lets remove heuristic1 and heuristic2 and create a 2nd example
   dataset? or branch?

We will modify the generated *heuristic.py* so heudiconv will arrange the output in a BIDS directory structure.

It is okay to rename this file, or to have several versions with different names, just be sure to pass the intended filename with `-f`. See :doc:`heuristics` docs for more info.

* I provide three section labels (1, 1b and 2) to facilitate exposition here. Each of these sections should be manually modified by you for your project.

Section 1
==============

* This *heuristic.py* does not import all sequences in the example *Dicom* directory. This is a feature of heudiconv: You do not need to import scouts, motion corrected images or other DICOMs of no interest.
* You may wish to add, modify or remove keys from this section for your own data::

    # Section 1: These key definitions should be revised by the user
    ###################################################################
    # For each sequence, define a key variables (e.g., t1w, dwi etc) and template using the create_key function:
    # key = create_key(output_directory_path_and_name).

    ###### TIPS #######
    # If there are sessions, then session must be subfolder name.
    # Do not prepend the ses key to the session! It will be prepended automatically for the subfolder and the filename.
    # The final value in the filename should be the modality.  It does not have a key, just a value.
    # Otherwise, there is a key for every value.
    # Filenames always start with subject, optionally followed by session, and end with modality.

    ###### Definitions #######
    # The "data" key creates sequential numbers which can be used for naming sequences.
    # This is especially valuable if you run the same sequence multiple times at the scanner.
    data = create_key('run-{item:03d}')

    t1w = create_key('sub-{subject}/{session}/anat/sub-{subject}_{session}_T1w')

    dwi = create_key('sub-{subject}/{session}/dwi/sub-{subject}_{session}_dir-AP_dwi')

    # Save the RPE (reverse phase-encode) B0 image as a fieldmap (fmap).  It will be used to correct
    # the distortion in the DWI
    fmap_rev_phase =  create_key('sub-{subject}/{session}/fmap/sub-{subject}_{session}_dir-PA_epi')

    fmap_mag =  create_key('sub-{subject}/{session}/fmap/sub-{subject}_{session}_magnitude')

    fmap_phase = create_key('sub-{subject}/{session}/fmap/sub-{subject}_{session}_phasediff')

    # Even if this is resting state, you still need a task key
    func_rest = create_key('sub-{subject}/{session}/func/sub-{subject}_{session}_task-rest_run-01_bold')
    func_rest_post = create_key('sub-{subject}/{session}/func/sub-{subject}_{session}_task-rest_run-02_bold')

* **Key**

  * Define a short informative key variable name for each image sequence you wish to export. Note that you can use any key names you want (e.g. *foo* would work as well as *fmap_phase*), but you need to be consistent.
  * The ``key`` name is to the left of the ``=`` for each row in the above example.
* **Template**

  * Use the variable ``{subject}`` to make the code general purpose, so you can apply it to different subjects in Step 3.
  * Use the variable ``{session}`` to make the code general purpose only if you have multiple sessions for each subject.

    * Once you use the variable ``{session}``:
    * Ensure that a session gets added to the **output path**, e.g., ``sub-{subject}/{session}/anat/`` AND
    * Session gets added to the **output filename**: ``sub-{subject}_{session}_T1w`` for every image in the session.
    * Otherwise you will get `bids validator errors <https://bids-standard.github.io/bids-validator/>`_

  * Define the output directories and file names according to the `BIDS specification <https://bids-specification.readthedocs.io/en/stable/modality-specific-files/magnetic-resonance-imaging-data.html>`_
  * Note the output names for the fieldmap images (e.g., *sub-219_ses-itbs_dir-PA_epi.nii.gz*, *sub-219_ses-itbs_magnitude1.nii.gz*, *sub-219_ses-itbs_magnitude2.nii.gz*, *sub-219_ses-itbs_phasediff.nii.gz*).
  * The reverse_phase encode dwi image (e.g., *sub-219_ses-itbs_dir-PA_epi.nii.gz*) is grouped with the fieldmaps because it is used to correct other images.
  * Data that is not yet defined in the BIDS specification will cause the bids-validator to produce an error unless you include it in a `.bidsignore <https://github.com/bids-standard/bids-validator?#bidsignore>`_ file.

* **data**

  * a key definition that creates sequential numbering
  * ``03d`` means *create three slots for digits* ``3d``, *and pad with zeros* ``0``.
  * This is useful if you have a scanner sequence with a single name but you run it repeatedly and need to generate separate files for each run. For example, you might define a single functional sequence at the scanner and then run it several times instead of creating separate names for each run.

  .. Note:: It is usually better to name your sequences explicitly (e.g., run-01, run-02 etc.) rather than depending on sequential numbering. There will be less confusion later.

  * If you have a sequence with the same name that you run repeatedly WITHOUT the sequential numbering, HeuDiConv will overwrite earlier sequences with later ones.
  * To ensure that a sequence includes sequential numbering, you also need to add ``run-{item:03d}`` (for example) to the key-value specification for that sequence.
  * Here I illustrate with the t1w key-value pair:

    * If you started with:

      * ``t1w = create_key('sub-{subject}/anat/sub-{subject}_T1w')``,
    * You could add sequence numbering like this:

      * ``t1w = create_key('sub-{subject}/anat/sub-{subject}_run-{item:03d}_T1w')``.
    * Now if you export several T1w images for the same subject and session, using the exact same protocol, each will get a separate run number like this:

      * *sub-219_ses_run-001_T1w.nii.gz, sub-219_ses_run-002_T1w.nii.gz* etc.

Section 1b
====================

* Based on your chosen keys, create a data dictionary called *info*::

    # Section 1b: This data dictionary (below) should be revised by the user.
    ###########################################################################
    # info is a Python dictionary containing the following keys from the infotodict defined above.
    # This list should contain all and only the sequences you want to export from the dicom directory.
    info = {t1w: [], dwi: [], fmap_rev_phase: [], fmap_mag: [], fmap_phase: [], func_rest: [], func_rest_post: []}

    # The following line does no harm, but it is not part of the dictionary.
    last_run = len(seqinfo)

* Enter each key in the dictionary in this format ``key: []``, for example, ``t1w: []``.
* Separate the entries with commas as illustrated above.

Section 2
===============

* Define the criteria for identifying each DICOM series that corresponds to one of the keys you want to export::

    # Section 2: These criteria should be revised by the user.
    ##########################################################
    # Define test criteria to check that each DICOM sequence is correct
    # seqinfo (s) refers to information in dicominfo.tsv. Consult that file for
    # available criteria.
    # Each sequence to export must have been defined in Section 1 and included in Section 1b.
    # The following illustrates the use of multiple criteria:
    for idx, s in enumerate(seqinfo):
        # Dimension 3 must equal 176 and the string 'mprage' must appear somewhere in the protocol_name
        if (s.dim3 == 176) and ('mprage' in s.protocol_name):
            info[t1w].append(s.series_id)

        # Dimension 3 must equal 74 and dimension 4 must equal 32, and the string 'DTI' must appear somewhere in the protocol_name
        if (s.dim3 == 74) and (s.dim4 == 32) and ('DTI' in s.protocol_name):
            info[dwi].append(s.series_id)

        # The string 'verify_P-A' must appear somewhere in the protocol_name
        if ('verify_P-A' in s.protocol_name):
            info[fmap_rev_phase] = [s.series_id]

        # Dimension 3 must equal 64, and the string 'field_mapping' must appear somewhere in the protocol_name
        if (s.dim3 == 64) and ('field_mapping' in s.protocol_name):
            info[fmap_mag] = [s.series_id]

        # Dimension 3 must equal 32, and the string 'field_mapping' must appear somewhere in the protocol_name
        if (s.dim3 == 32) and ('field_mapping' in s.protocol_name):
            info[fmap_phase] = [s.series_id]

        # The string 'resting_state' must appear somewhere in the protocol_name and the Boolean field is_motion_corrected must be False (i.e. not motion corrected)
        # This ensures I do NOT get the motion corrected MOCO series instead of the raw series!
        if ('restingstate' == s.protocol_name) and (not s.is_motion_corrected):
            info[func_rest].append(s.series_id)

        # The string 'Post_TMS_resting_state' must appear somewhere in the protocol_name and the Boolean field is_motion_corrected must be False (i.e. not motion corrected)

        # This ensures I do NOT get the motion corrected MOCO series instead of the raw series.
        if ('Post_TMS_restingstate' == s.protocol_name) and (not s.is_motion_corrected):
            info[func_rest_post].append(s.series_id)

  * To define the criteria, look at *dicominfo.tsv* in *.heudiconv/info*. This file contains tab-separated values so you can easily view it in Excel or any similar spreadsheet program. *dicominfo.tsv* is not used programmatically to run heudiconv (i.e., you could delete it with no adverse consequences), but it is very useful for defining the test criteria for Section 2 of *heuristic.py*.
  * Some values in *dicominfo.tsv* might be wrong. For example, my reverse phase encode sequence with two acquisitions of 74 slices each is reported as one acquisition with 148 slices (2018_12_11). Hopefully they'll fix this. Despite the error in *dicominfo.tsv*, dcm2niix reconstructed the images correctly.
  * You will be adding, removing or altering values in conditional statements based on the information you find in *dicominfo.tsv*.
  * ``seqinfo`` (s) refers to the same information you can view in *dicominfo.tsv* (although seqinfo does not rely on *dicominfo.tsv*).
  * Here are two types of criteria:

    * ``s.dim3 == 176`` is an **equivalence** (e.g., good for checking dimensions for a numerical data type).  For our sample T1w image to be exported from DICOM, it must have 176 slices in the third dimension.
    * ``'mprage' in s.protocol_name`` says the protocol name string must **include** the word *mprage* for the *T1w* image to be exported from DICOM. This criterion string is case-sensitive.

  * ``info[t1w].append(s.series_id)`` Given that the criteria are satisfied, the series should be named and organized as described in *Section 1* and referenced by the info dictionary. The information about the processing steps is saved in the *.heudiconv* subdirectory.
  * Here I have organized each conditional statement so that the sequence protocol name comes first followed by other criteria if relevant.  This is not necessary, though it does make the resulting code easier to read.


.. _heudiconv_step3:

Step 3:
*******************

* You have now done all the hard work for your project. When you want to add a subject or session, you only need to run this third step for that subject or session (A record of each run is kept in .heudiconv for you)::

    heudiconv --files dicom/{subject}/*/*.dcm -o Nifti/ -f Nifti/code/heuristic.py -s 219 -ss itbs -c dcm2niix -b --minmeta --overwrite

* The first time you run this step, several important text files are generated (e.g., CHANGES, dataset_description.json, participants.tsv, README etc.).
  On subsequent runs, information may be added (e.g., *participants.tsv* will be updated).
  Other files, like the *README* and *dataset_description.json* should be updated manually.
* This Docker command is slightly different from the previous Docker command you ran.

  * ``-f Nifti/code/heuristic.py`` now tells HeuDiConv to use your revised *heuristic.py* in the *code* directory.
  * In this case, we specify the subject we wish to process ``-s 219`` and the name of the session ``-ss itbs``.
  * We could specify multiple subjects like this: ``-s 219 220 -ss itbs``
  * ``-c dcm2niix -b`` indicates that we want to use the dcm2niix converter with the -b flag (which creates BIDS).
  * ``--minmeta`` ensures that only the minimum necessary amount of data gets added to the JSON file when created.  On the off chance that there is a LOT of meta-information in the DICOM header, the JSON file will not get swamped by it. fmriprep and mriqc are very sensitive to this information overload and will crash, so *minmeta* provides a layer of protection against such corruption.
  * ``--overwrite`` This is a peculiar option. Without it, I have found the second run of a sequence does not get generated. But with it, everything gets written again (even if it already exists).  I don't know if this is my problem or the tool...but for now, I'm using ``--overwrite``.
  * Step 3 should produce a tree like this::

       Nifti
      ├── CHANGES
      ├── README
      ├── code
      │   ├── __pycache__
      │   │   └── heuristic1.cpython-36.pyc
      │   ├── heuristic1.py
      │   └── heuristic2.py
      ├── dataset_description.json
      ├── participants.json
      ├── participants.tsv
      ├── sub-219
      │   └── ses-itbs
      │       ├── anat
      │       │   ├── sub-219_ses-itbs_T1w.json
      │       │   └── sub-219_ses-itbs_T1w.nii.gz
      │       ├── dwi
      │       │   ├── sub-219_ses-itbs_dir-AP_dwi.bval
      │       │   ├── sub-219_ses-itbs_dir-AP_dwi.bvec
      │       │   ├── sub-219_ses-itbs_dir-AP_dwi.json
      │       │   └── sub-219_ses-itbs_dir-AP_dwi.nii.gz
      │       ├── fmap
      │       │   ├── sub-219_ses-itbs_dir-PA_epi.json
      │       │   ├── sub-219_ses-itbs_dir-PA_epi.nii.gz
      │       │   ├── sub-219_ses-itbs_magnitude1.json
      │       │   ├── sub-219_ses-itbs_magnitude1.nii.gz
      │       │   ├── sub-219_ses-itbs_magnitude2.json
      │       │   ├── sub-219_ses-itbs_magnitude2.nii.gz
      │       │   ├── sub-219_ses-itbs_phasediff.json
      │       │   └── sub-219_ses-itbs_phasediff.nii.gz
      │       ├── func
      │       │   ├── sub-219_ses-itbs_task-rest_run-01_bold.json
      │       │   ├── sub-219_ses-itbs_task-rest_run-01_bold.nii.gz
      │       │   ├── sub-219_ses-itbs_task-rest_run-01_events.tsv
      │       │   ├── sub-219_ses-itbs_task-rest_run-02_bold.json
      │       │   ├── sub-219_ses-itbs_task-rest_run-02_bold.nii.gz
      │       │   └── sub-219_ses-itbs_task-rest_run-02_events.tsv
      │       ├── sub-219_ses-itbs_scans.json
      │       └── sub-219_ses-itbs_scans.tsv
      └── task-rest_bold.json

TIPS
======

* **Name Directories as you wish**: You can name the project directory (e.g., **MRIS**)  and the output directory (e.g., **Nifti**) as you wish (just don't put spaces in the names!).
* **Age and Sex Extraction**: Heudiconv will extract age and sex info from the DICOM header.  If there is any reason to believe this information is wrong in the DICOM header (for example, it was made-up because no one knew how old the subject was, or it was considered a privacy concern), then you need to check the output.  If you have Horos (or another DICOM editor), you can edit the values in the DICOM headers, otherwise you need to edit the values in the BIDS text file *participants.tsv*.
* **Separating Sessions**: If you have multiple sessions at the scanner, you should create an *Exam* folder for each session.  This will help you to keep the data organized and *Exam* will be reported in the *study_description* in your *dicominfo.tsv*, so that you can use it as a criterion.
* **Don't manually combine DICOMS from different sessions**: If you combine multiple sessions in one subject DICOM folder, heudiconv will fail to run and will complain about ``conflicting study identifiers``. You can get around the problem by figuring out which DICOMs are from different sessions and separating them so you deal with one set at a time.  This may mean you have to manually edit the BIDS output.

    * Why might you manually combine sessions you ask? Because you never intended to have multiple sessions, but the subject had to complete some scans the next day. Or, because the scanner had to be rebooted.
* **Don't assume all your subjects' dicoms have the same names or that the sequences were always run in the same order**: If you develop a *heuristic.py* on one subject, try it and carefully evaluate the results on your other subjects.  This is especially true if you already collected the data before you started thinking about automating the output.  Every time you run HeuDiConv with *heuristic.py*, a new *dicominfo.tsv* file is generated.  Inspect this for differences in protocol names and series descriptions etc.
* **Decompressing DICOMS**: Decompress your data, heudiconv does not yet support compressed DICOM conversion. https://github.com/nipy/heudiconv/issues/287
* **Create unique DICOM protocol names at the scanner** If you have the opportunity to influence the DICOM naming strategies, then try to ensure that there is a unique protocol name for every run.  For example, if you repeat the fmri protocol three times, name the first one fmri_1, the next fmri_2, and the last fmri_3 (or any variation on this theme).  This will make it much easier to uniquely specify the sequences when you convert and reduce your chance of errors.


Exploring Criteria
**********************

*dicominfo.tsv* contains a human readable version of seqinfo.  Each column of data can be used as criteria for identifying the correct DICOM image. We have already provided examples of using string types, numbers, and Booleans (True-False). Tuples (immutable lists) are also available and examples of using these are provided below. To ensure that you are extracting the images you want, you need to be very careful about creating your initial *heuristic.py*.

Why Experiment?
====================

* Criteria can be tricky.  Ensure the NIfTI files you create are the correct ones (for example, not the derived or motion corrected if you didn't want that). In addition to looking at the images created (which tells you whether you have a fieldmap or T1w etc.), you should look at the dimensions of the image. Not only the dimensions, but the range of intensity values and the size of the image on disk should match for dcm2niix and heudiconv's *heuristic.py*.
* For really tricky cases, download and install dcm2niix on your local machine and run it for a sequence of concern (in my experience, it is usually fieldmaps that go wrong).
* Although Python does not require you to use parentheses while defining criteria, parentheses are a good idea.  Parentheses will help ensure that complex criteria involving multiple logical operators ``and, or, not`` make sense and behave as expected.

Tuples
---------

Suppose you want to use the values in the field ``image_type``?  It is not a number or string or Boolean.  To discover the data type of a column, you can add a statement like this ``print(type(s.image_type))`` to the for loop in Section 2 of *heuristic.py*. Then run *heuristic.py* (preferably without any actual conversions) and you should see an output like this ``<class 'tuple'>``.  Here is an example of using a value from ``image_type`` as a criterion::

  if ('ASL_3D_tra_iso' == s.protocol_name) and ('TTEST' in s.image_type):
     info[asl_der].append(s.series_id)

Note that this differs from testing for a string because you cannot test for any substring (e.g., 'TEST' would not work).  String tests will not work on a tuple datatype.

.. Note:: *image_type* is described in the `DICOM specification <https://dicom.innolitics.com/ciods/mr-image/general-image/00080008>`_

