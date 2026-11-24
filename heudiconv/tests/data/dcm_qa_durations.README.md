# Provenance of `dcm_qa_durations.json`

`dcm_qa_durations.json` has, for each of the 404 DICOM series of the
`dcm_qa*` validation collections by Chris Rorden et al.
(https://github.com/neurolabusc, see
[Li et al., 2025](https://doi.org/10.1038/s41597-025-05503-w)), what
`heudiconv.duration` goes by to establish the duration of the series, and
what it gives.  It contains no DICOMs and no image data, only values derived
from their headers, per series:

- `first`: path, within the directory with clones of the collections, of the
  first of its files; `description`: its SeriesDescription; `n_files`.
- `header`: the fields of `heudiconv.duration.SeriesHeader` which are set,
  from the header of that first file.
- `timings`: for the files of the series, the distinct
  `[seconds since the earliest of them, AcquisitionNumber,
  TemporalPositionIdentifier, number of files with those]`.
- `duration`: `[seconds, source]` which `heudiconv.duration.estimate()` gave
  for the above, or `null`.  This is a record of what the code gives, to
  notice it change, not a truth of its own.
- `dcm2niix`: `[number of volumes, RepetitionTime]` of the NIfTI and sidecar
  which dcm2niix v1.0.20261029 made of the series, where it made a single 4D
  image of it.  This is independent of the code under test.

It was produced by `_read_dcm_qa()` of `heudiconv/tests/test_duration.py`,
which regenerates it with `HEUDICONV_TEST_DCM_QA` set to the directory with
the clones and `HEUDICONV_TEST_DCM_QA_REGENERATE` set (keeping `dcm2niix`),
and checks it against them with just the former set.

Collections, each a repository of https://github.com/neurolabusc, at the
commit used, with the license it is under and the number of its series:

| Collection | Commit | License | Series |
|---|---|---|---|
| [dcm_qa](https://github.com/neurolabusc/dcm_qa) | `8215e3e991c699b4b14f8114087d6f9c52dad428` | BSD-2-Clause | 52 |
| [dcm_qa_12bit](https://github.com/neurolabusc/dcm_qa_12bit) | `953703a78f01324bb8e5ea71edc4beb75bae8cef` | BSD-2-Clause | 1 |
| [dcm_qa_agfa](https://github.com/neurolabusc/dcm_qa_agfa) | `a8463172dd352280242535ee153f3b7ccf0c1664` | BSD-2-Clause | 2 |
| [dcm_qa_asl](https://github.com/neurolabusc/dcm_qa_asl) | `cf418ac5e7c5e101cb293754cf05f7736382d5f8` | BSD-2-Clause | 11 |
| [dcm_qa_canon](https://github.com/neurolabusc/dcm_qa_canon) | `1dc19c806d0347e9eb41db2edeb2db51365b5304` | BSD-2-Clause | 11 |
| [dcm_qa_canon_enh](https://github.com/neurolabusc/dcm_qa_canon_enh) | `504ac92670465861c3c5169c4b7e3433fc3e18a3` | BSD-2-Clause | 11 |
| [dcm_qa_ct](https://github.com/neurolabusc/dcm_qa_ct) | `8209e86f0374cd651cedba1bfc179ccf3451eba9` | BSD-2-Clause | 26 |
| [dcm_qa_decubitus](https://github.com/neurolabusc/dcm_qa_decubitus) | `973be5a41dae0ab154f87ad42c9d70d649e61984` | BSD-2-Clause | 8 |
| [dcm_qa_deident](https://github.com/neurolabusc/dcm_qa_deident) | `ce4cbe7cd86dbf7e5b650464f298f9c7062f8574` | BSD-2-Clause | 1 |
| [dcm_qa_dti](https://github.com/neurolabusc/dcm_qa_dti) | `d550755681dfe10ea7b49426f37c12c77492df64` | BSD-2-Clause | 5 |
| [dcm_qa_enh](https://github.com/neurolabusc/dcm_qa_enh) | `4b9200ef6438365c10e3582b31f6ad5cfee64672` | BSD-2-Clause | 5 |
| [dcm_qa_enh_compressed](https://github.com/neurolabusc/dcm_qa_enh_compressed) | `3f1cc2005a39835541b0dbf732de36e6a25a57a4` | BSD-2-Clause | 3 |
| [dcm_qa_ep3d](https://github.com/neurolabusc/dcm_qa_ep3d) | `9e59eeb8db7060af020a190c8fcf4f8d8fa9b084` | BSD-2-Clause | 7 |
| [dcm_qa_fmap](https://github.com/neurolabusc/dcm_qa_fmap) | `fb6f3f58e073664c6fe98f1357498c279f103862` | BSD-2-Clause | 8 |
| [dcm_qa_frag](https://github.com/neurolabusc/dcm_qa_frag) | `805434046dee0ca6d7f680b1ab41377c62527d8e` | BSD-2-Clause | 2 |
| [dcm_qa_ge](https://github.com/neurolabusc/dcm_qa_ge) | `e92133ae414e2b23e8c4d07a4030ab4dbb41518e` | BSD-2-Clause | 29 |
| [dcm_qa_jpg](https://github.com/neurolabusc/dcm_qa_jpg) | `982b8dccbc206e02f22846cef18db99321b86526` | CC0-1.0 | 3 |
| [dcm_qa_me](https://github.com/neurolabusc/dcm_qa_me) | `4e66e8635cc8dfc7a22654480f748839fe38d822` | BSD-2-Clause | 3 |
| [dcm_qa_mosaic](https://github.com/neurolabusc/dcm_qa_mosaic) | `8d2dfb0efce9145e2912eed31838e0eb52c7b42a` | BSD-2-Clause | 8 |
| [dcm_qa_nih](https://github.com/neurolabusc/dcm_qa_nih) | `fc359a0960f005a1a5d894a09041863d4a5882d3` | BSD-2-Clause | 8 |
| [dcm_qa_noRF](https://github.com/neurolabusc/dcm_qa_noRF) | `adb4e8083b4c9bf3754cb2121c32f5fc6a8ad406` | CC0-1.0 | 3 |
| [dcm_qa_parametermap](https://github.com/neurolabusc/dcm_qa_parametermap) | `8ea1702d83c66c12f04a29f95a707157c5760e29` | BSD-2-Clause | 8 |
| [dcm_qa_pdt2](https://github.com/neurolabusc/dcm_qa_pdt2) | `3b5868414f0bf79bdb4bc9d8f2dc665c9fea5567` | BSD-2-Clause | 1 |
| [dcm_qa_philips](https://github.com/neurolabusc/dcm_qa_philips) | `1a851fb2e9cf9cc2432fb0264e724da29c4bcf51` | BSD-2-Clause | 4 |
| [dcm_qa_philips_asl](https://github.com/neurolabusc/dcm_qa_philips_asl) | `409ce675e04a94e82b774a1ff0443e879c12a454` | BSD-2-Clause | 8 |
| [dcm_qa_physio](https://github.com/neurolabusc/dcm_qa_physio) | `736fa7502e48482076a17551e25a058fed4f2bcb` | CC0-1.0 | 10 |
| [dcm_qa_polar](https://github.com/neurolabusc/dcm_qa_polar) | `cda2bc7a4c13c065ffc264db84613c666e36b226` | BSD-2-Clause | 4 |
| [dcm_qa_rgb](https://github.com/neurolabusc/dcm_qa_rgb) | `31368e48d8a3713bc37806f1606515dd189006dc` | BSD-2-Clause | 13 |
| [dcm_qa_sag](https://github.com/neurolabusc/dcm_qa_sag) | `6995df4a895b7cf34ef321b248ad7cdfb8bc2069` | BSD-2-Clause | 19 |
| [dcm_qa_seg](https://github.com/neurolabusc/dcm_qa_seg) | `01486269280e02137bd13530487418c21fc4aae5` | BSD-2-Clause | 16 |
| [dcm_qa_spec](https://github.com/neurolabusc/dcm_qa_spec) | `edd37a6dd2b01d37bd10a24e6a0b4fc68278bb45` | CC0-1.0 | 2 |
| [dcm_qa_stc](https://github.com/neurolabusc/dcm_qa_stc) | `aead26b7426932c74aaf80a17c6f45daebab94b4` | BSD-2-Clause | 18 |
| [dcm_qa_table](https://github.com/neurolabusc/dcm_qa_table) | `f2efcdeb0674557ce84dd3246420679cc315fad7` | BSD-2-Clause | 22 |
| [dcm_qa_toshiba](https://github.com/neurolabusc/dcm_qa_toshiba) | `41f7b5143f376de81c3221275ef8576598063c56` | BSD-2-Clause | 5 |
| [dcm_qa_trt](https://github.com/neurolabusc/dcm_qa_trt) | `6d7467ac173e8e8109509ad88e12587e066024e1` | BSD-2-Clause | 13 |
| [dcm_qa_ts](https://github.com/neurolabusc/dcm_qa_ts) | `5ba8c4d8d3c9831b4fd4a2e5f9b842ee00098b13` | BSD-2-Clause | 1 |
| [dcm_qa_uih](https://github.com/neurolabusc/dcm_qa_uih) | `f3bd991a98eaf49a6f928f276a41f666d658a64b` | BSD-2-Clause | 6 |
| [dcm_qa_xa30](https://github.com/neurolabusc/dcm_qa_xa30) | `371ab3071aa9270d23b99fca5f83fe0c35932182` | BSD-2-Clause | 23 |
| [dcm_qa_xa60](https://github.com/neurolabusc/dcm_qa_xa60) | `5c3a8ea47daee2e9fc97b91746126f73f7bd91f7` | BSD-2-Clause | 24 |
