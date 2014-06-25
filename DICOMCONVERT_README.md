This gist describes a flexible dicom converter for organizing brain imaging data into structured directory layouts.

- it allows customizable directory layouts and naming schemes through heuristic file
- it only converts the necessary dicoms, not everything in a directory
- you can keep links to dicom files in the participant layout
- it's faster than parsesdicomdir or mri_convert if you use dcm2nii option
- it embeds all the dicom metadata inside the nifti header using dcmstack
- it tracks the provenance of the conversion from dicom to nifti in w3c prov format
- the example shows a conversion to openfmri layout structure

soon you'll be able to:
- add more tags to the metadata representation of the files
- and push the metadata to a provenance store