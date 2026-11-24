.. _Tutorials:

=========
Tutorials
=========

.. toctree::

  quickstart
  custom-heuristic
  reproin


Sample DICOM data
*****************

To try HeuDiConv without your own scans, start with the dataset and heuristic
in the :ref:`quickstart tutorial <prepare_dataset>`. Additional public samples
are available from the DataLad catalog:

* `DBIC quality-assurance data <https://datasets.datalad.org/?dir=/dbic/QA>`_
  contains DICOM archives under ``sourcedata/``. These scans use the naming
  conventions supported by the :doc:`ReproIn heuristic <reproin>` and can be
  converted again with ``-f reproin``.
* `The DICOM collection <https://datasets.datalad.org/?dir=/dicoms>`_ contains
  samples from different scanners and acquisition protocols. It is useful for
  exploring data and developing heuristics, but there is no single heuristic
  that maps every dataset in this collection to BIDS. Inspect a sample's
  sequence information and choose or adapt a :doc:`heuristic <heuristics>`.

These datasets use git-annex to store file content separately from Git
metadata. Use DataLad to clone the dataset linked from the catalog, inspect its
files, and retrieve the desired DICOMs with ``datalad get``. A clone alone does
not download the annexed file content. Git and git-annex can also be used
directly. Retrieve only the series or archives you need; complete datasets
can be large.

Pass retrieved DICOMs or DICOM archives to ``heudiconv --files`` and choose a
separate output directory with ``-o`` to keep the sample source data intact.
See :doc:`quickstart` for a conversion example and archive handling.


External Tutorials
******************

Luckily(?), we live in an era of plentiful information. Below are some links to
other users' tutorials covering their experience with ``heudiconv``.

- `YouTube tutorial <https://www.youtube.com/watch?v=O1kZAuR7E00>`_ by `James Kent <https://github.com/jdkent>`_.

- `Walkthrough <http://reproducibility.stanford.edu/bids-tutorial-series-part-2a/>`_ by the `Stanford Center for Reproducible Neuroscience <http://reproducibility.stanford.edu/>`_.

- `U of A Neuroimaging Core <https://neuroimaging-core-docs.readthedocs.io/en/latest/pages/heudiconv.html>`_ by `Dianne Patterson <https://github.com/dkp>`_.

- `Sample Conversion: Coastal Coding 2019 <http://www.repronim.org/coco2019-training/presentations/heudiconv/#1>`_.

- `A joined DataLad and HeuDiConv tutorial for reproducible fMRI studies <http://www.repronim.org/coco2019-training/04-02-reproin/>`_.

- `The ReproIn conversion workflow overview <https://github.com/repronim/reproin#conversion>`_.

- `Slides <https://docs.google.com/presentation/d/14UNWQVY49c9Xc-7sj1FkoILXnt-wYjW404oqT-FtCW8/edit#slide=id.p>`_ and
  `recording <https://www.youtube.com/watch?v=j2SKX37-w4c&list=PLs3CA4ShM1DUX0nTMKfoB8Z6kdrZpByLa&index=5&t=0s>`_
  of a ReproNim Webinar on ``heudiconv``.

.. caution::
    Some of these tutorials may not be up to date with
    the latest releases of ``heudiconv``.
