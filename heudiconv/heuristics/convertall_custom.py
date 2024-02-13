"""A demo convertall heuristic with custom_seqinfo extracting affine and sample DICOM path

This heuristic also demonstrates on how to create a "derived" heuristic which would augment
behavior of an already existing heuristic without complete rewrite.  Such approach could be
useful for heuristic like  reproin  to overload mapping etc.
"""

from .convertall import *  # noqa: F403


def custom_seqinfo(series_files, wrapper, **kw):  # noqa: U100
    """Demo for extracting custom header fields into custom_seqinfo field

    Operates on already loaded DICOM data.
    Origin: https://github.com/nipy/heudiconv/pull/333
    """

    from nibabel.nicom.dicomwrappers import WrapperError

    try:
        affine = str(wrapper.affine)
    except WrapperError:
        lgr.exception("Errored out while obtaining/converting affine")  # noqa: F405
        affine = None
    return affine, series_files[0]
