---
title: 'HeuDiConv — flexible DICOM conversion into structured directory layouts'
tags:
  - Python
  - neuroscience
  - standardization
  - DICOM
  - BIDS
  - open science
  - FOSS
authors:
  - name: TODO
    orcid: 0000-0000-0000-0000
    equal-contrib: true
    affiliation: "1, 2" # (Multiple affiliations must be quoted)
  - name: Author Without ORCID
    equal-contrib: true # (This is how you can denote equal contributions between multiple authors)
    affiliation: 2
  - name: Author with no affiliation
    corresponding: true # (This is how to denote the corresponding author)
    affiliation: 3
affiliations:
 - name: TODO
   index: 1
 - name: Institution Name, Country
   index: 2
 - name: Independent Researcher, Country
   index: 3
date: 2023-01-31
bibliography: paper.bib

# Optional fields if submitting to a AAS journal too, see this blog post:
# https://blog.joss.theoj.org/2018/12/a-new-collaboration-with-aas-publishing
aas-doi: 10.3847/xxxxx <- update this with the DOI from AAS once you know it.
aas-journal: Astrophysical Journal <- The name of the AAS journal.
---

# Summary

The forces on stars, galaxies, and dark matter under external gravitational
fields lead to the dynamical evolution of structures in the universe. The orbits
of these bodies are therefore key to understanding the formation, history, and
future state of galaxies. The field of "galactic dynamics," which aims to model
the gravitating components of galaxies to study their structure and evolution,
is now well-established, commonly taught, and frequently used in astronomy.
Aside from toy problems and demonstrations, the majority of problems require
efficient numerical tools, many of which require the same base code (e.g., for
performing numerical orbit integration).

# Statement of need

Neuroimaging is an empirical field of science heavily relying on efficient data acquisition, harmonization, and processing.
Neuroimaging data acquired by MRI scanners usually are exported from them in a set of formats, with DICOM (Digital Imaging and Communications in Medicine) being the standard metadata-rich form.
Data in DICOM format is usually transmitted to PACS (Picture Archiving and Communication Systems) servers.
Unlike in clinical settings, where data is interfaced directly from PACS in DICOM format, in neuroimaging research tools typically expect data in much simpler NIfTI [@TODOnifti] format.
NIfTI file format carries only basic metadata and does not instruct how to organize multiple files within a study.
HeuDiConv was developer to provide flexible tooling for labs to be able efficiently and consistently convert collections of DICOM files into collections of NIfTI (and compressed archives of DICOMs) files in desired file system hierarchies.
Since the inception of HeuDiConv in 2014, a community-driven standard Brain Imaging Data Structure (BIDS) [@TODO] was established, which formalized such datasets layout and storage of metadata.
Since then the most frequent use-case for HeuDiConv became conversion of DICOM files into BIDS datasets.
Standardization into BIDS facilitated not only reuse of already shared datasets but also facilitate data validation, curation, analysis, etc.

`Gala` was designed to be used by both astronomical researchers and by
students in courses on gravitational dynamics or astronomy. It has already been
used in a number of scientific publications [@Pearson:2017] and has also been
used in graduate courses on Galactic dynamics to, e.g., provide interactive
visualizations of textbook material [@Binney:2008]. The combination of speed,
design, and support for Astropy functionality in `Gala` will enable exciting
scientific explorations of forthcoming data releases from the *Gaia* mission
[@gaia] by students and experts alike.

# Mathematics

Single dollars ($) are required for inline mathematics e.g. $f(x) = e^{\pi/x}$

Double dollars make self-standing equations:

$$\Theta(x) = \left\{\begin{array}{l}
0\textrm{ if } x < 0\cr
1\textrm{ else}
\end{array}\right.$$

You can also use plain \LaTeX for equations
\begin{equation}\label{eq:fourier}
\hat f(\omega) = \int_{-\infty}^{\infty} f(x) e^{i\omega x} dx
\end{equation}
and refer to \autoref{eq:fourier} from text.

# Citations

Citations to entries in paper.bib should be in
[rMarkdown](http://rmarkdown.rstudio.com/authoring_bibliographies_and_citations.html)
format.

If you want to cite a software repository URL (e.g. something on GitHub without a preferred
citation) then you can do it with the example BibTeX entry below for @fidgit.

For a quick reference, the following citation commands can be used:
- `@author:2001`  ->  "Author et al. (2001)"
- `[@author:2001]` -> "(Author et al., 2001)"
- `[@author1:2001; @author2:2001]` -> "(Author1 et al., 2001; Author2 et al., 2002)"

# Figures

Figures can be included like this:
![Caption for example figure.\label{fig:example}](figure.png)
and referenced from text using \autoref{fig:example}.

Figure sizes can be customized by adding an optional second parameter:
![Caption for example figure.](figure.png){ width=20% }

# Conflicts of interest

There are no conflicts to declare.

# Acknowledgements

We would like to extend our gratitude to
TODO
for notable contributions to the codebase, bug reports, recommendations, and promotion of HeuDiConv.

HeuDiConv development was primarily done under the umbrella of the NIH funded ReproNim [1P41EB019936-01A1](https://projectreporter.nih.gov/project_info_details.cfm?aid=8999833&map=y) and [TODO - renewal](TODO) (PI: Kennedy).
It also received contributions from the ...

# References
