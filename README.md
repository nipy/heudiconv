This gist describes a flexible dicom converter for organizing brain imaging data into structured directory layouts.

- it allows customizable directory layouts and naming schemes through heuristic file
- it only converts the necessary dicoms, not everything in a directory
- you can keep links to dicom files in the participant layout
- it's faster than parsesdicomdir or mri_convert if you use dcm2nii option
- it tracks the provenance of the conversion from dicom to nifti in w3c prov format
- the example shows a conversion to openfmri layout structure

outputs:

The outputs are stored per participant. An `info` directory contains a copy of the heuristic script as well as the dicomseries information. In addition there are two files NAME.auto.txt and NAME.edit.txt. You can change series number assignments in NAME.edit.txt and rerun the converter to apply the changes. To start from scratch remove the participant directory.  

soon you'll be able to:
- add more tags to the metadata representation of the files
- and push the metadata to a provenance store
