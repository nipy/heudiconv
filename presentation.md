name: inverse
layout: true
class: center, middle, inverse
---
# Sample Conversion
### Heudiconv 2018

---
name: content
class: center, middle
layout: false

## Prerequisites

* Docker
* Heudiconv image (`docker pull nipy/heudiconv:latest`)

---
## Before we start

This tutorial will focus on the conversion of DICOMs to BIDS format using a public scan.
If you wish to follow along, these DICOMs can downloaded using datalad.

```
docker run -it --rm -v /local/path/to/store/dicoms:/dicoms \
--entrypoint=bash nipy/heudiconv:latest

# Inside container
source activate neuro && cd /dicoms
git clone http://datasets.datalad.org/dicoms/dartmouth-phantoms/PHANTOM1_3/.git
cd PHANTOM1_3
datalad get -J6 YAROSLAV_DBIC-TEST1/ #ensure all the data is downloaded for the demo to work!
exit
```

---
class: middle
layout: true
---

### Step 1: Dry Pass

First, we will run a dry pass (no conversion), which will stack and group the DICOMs
into series.

```bash
docker run --rm -it -v /path/to/dicoms:/data:ro \
-v /path/to/output/directory:/output nipy/heudiconv:latest
...
```

---
### Step 1: Dry Pass

First, we will run a dry pass (no conversion), which will stack and group the DICOMs
into series.

```bash
docker run --rm -it -v /path/to/dicoms:/data:ro \
-v /path/to/output/directory:/output nipy/heudiconv:latest
-d /data/{subject}/YAROSLAV_DBIC-TEST1/*/*/*IMA -s PHANTOM1_3
...
```

---
### Step 1: Dry Pass

First, we will run a dry pass (no conversion), which will stack and group the DICOMs
into series.

```bash
docker run --rm -it -v /path/to/dicoms:/data:ro \
-v /path/to/output/directory:/output nipy/heudiconv:latest
-d /data/{subject}/YAROSLAV_DBIC-TEST1/*/*/*IMA -s PHANTOM1_3
-f convertall -c none -o /output
```

Run the command!

---
layout: false
### Sample conversion

After running the command, there will be a hidden folder within the specified output directory `.heudiconv`.

- Within `.heudiconv`, there will be a directory with your subject ID, and a subdirectory `info`. Inside this, you can see a `dicominfo.tsv` - we'll be using the information here to convert to a file structure (BIDS)

- The full specifications for BIDS can be found [here](http://bids.neuroimaging.io/bids_spec1.0.1.pdf)

---
### The heuristic file

```python
import os

def create_key(template, outtype=('nii.gz',), annotation_classes=None):
    if template is None or not template:
        raise ValueError('Template must be a valid format string')
    return template, outtype, annotation_classes

def infotodict(seqinfo):
    """Heuristic evaluator for determining which runs belong where

    allowed template fields - follow python string module:

    item: index within category
    subject: participant id
    seqitem: run number during scanning
    subindex: sub index within group
    """

    data = create_key('run{item:03d}')

    info = {data: []}

    for s in seqinfo:
        info[data].append(s.series_id)
    return info
```
---
### Creating heuristic keys

- Keys define type of scan

- Let's extract T1, diffusion, and rest scans

--
ex.
```python
t1w = create_key('sub-{subject}/anat/sub-{subject}_T1w')
```

--

```python
def infotodict(seqinfo):
    """Heuristic evaluator for determining which runs belong where

    allowed template fields - follow python string module:

    item: index within category
    subject: participant id
    seqitem: run number during scanning
    subindex: sub index within group
    """
    # paths done in BIDS format
    t1w = create_key('sub-{subject}/anat/sub-{subject}_T1w')
    dwi = create_key('sub-{subject}/dwi/sub-{subject}_run-{item:01d}_dwi')
    rest = create_key('sub-{subject}/func/sub-{subject}_task-rest_rec-{rec}_run-{item:01d}_bold')

    info = {t1w: [], dwi: [], rest: []}
```
---
### Sequence Info

  - And now for each key, we will look at the `dicominfo.tsv` and set a unique criteria that only that scan will meet.

--

```python
for idx, s in enumerate(seqinfo):
   # s is a namedtuple with fields equal to the names of the columns
   # found in the dicominfo.txt file
```

---
### Sequence Info

  - And now for each key, we will look at the `dicominfo.tsv` and set a unique criteria that only that scan will meet.


```python
for idx, s in enumerate(seqinfo): # each row of dicominfo.tsv
    if (s.dim3 == 176) and (s.dim4 == 1) and ('t1' in s.protocol_name):
      info[t1w] = [s.series_id] # assign if a single scan meets criteria
```

---
### Handling multiple runs

```python
for idx, s in enumerate(seqinfo): # each row of dicominfo.tsv
    if (s.dim3 == 176) and (s.dim4 == 1) and ('t1' in s.protocol_name):
      info[t1w] = [s.series_id] # assign if a single scan meets criteria
```
--

- Notice there are two diffusion scans shown in DICOM info

---
### Handling multiple runs

```python
for idx, s in enumerate(seqinfo): # each row of dicominfo.txt
    if (s.dim3 == 176) and (s.dim4 == 1) and ('t1' in s.protocol_name):
      info[t1w] = [s.series_id] # assign if a single scan meets criteria
    if (11 <= s.dim3 <= 22) and (s.dim4 == 1) and ('dti' in s.protocol_name):
      info[dwi].append(s.series_id) # append if multiple scans meet criteria
```

- Notice there are two diffusion scans shown in DICOM info

---
### Using custom formatting conditionally

```python
for idx, s in enumerate(seqinfo): # each row of dicominfo.tsv
    if (s.dim3 == 176) and (s.dim4 == 1) and ('t1' in s.protocol_name):
      info[t1w] = [s.series_id] # assign if a single scan meets criteria
    if (11 <= s.dim3 <= 22) and (s.dim4 == 1) and ('dti' in s.protocol_name):
      info[dwi].append(s.series_id) # append if multiple scans meet criteria
```

--

- Extract and label if resting state scans are motion corrected

---
### Using custom formatting conditionally

```python
for idx, s in enumerate(seqinfo): # each row of dicominfo.tsv
    if (s.dim3 == 176) and (s.dim4 == 1) and ('t1' in s.protocol_name):
      info[t1w] = [s.series_id] # assign if a single scan meets criteria
    if (11 <= s.dim3 <= 22) and (s.dim4 == 1) and ('dti' in s.protocol_name):
      info[dwi].append(s.series_id) # append if multiple scans meet criteria
    if (s.dim4 > 10) and ('taskrest' in s.protocol_name):
      if s.is_motion_corrected: # motion corrected
        # catch
      else:
        # catch
```

- Extract and label if resting state scans are motion corrected

---
### Using custom formatting conditionally

```python
for idx, s in enumerate(seqinfo): # each row of dicominfo.tsv
    if (s.dim3 == 176) and (s.dim4 == 1) and ('t1' in s.protocol_name):
      info[t1w] = [s.series_id] # assign if a single scan meets criteria
    if (11 <= s.dim3 <= 22) and (s.dim4 == 1) and ('dti' in s.protocol_name):
      info[dwi].append(s.series_id) # append if multiple scans meet criteria
    if (s.dim4 > 10) and ('taskrest' in s.protocol_name):
      if s.is_motion_corrected: # motion corrected
        info[rest].append({'item': s.series_id, 'rec': 'corrected'})
      else:
        info[rest].append({'item': s.series_id, 'rec': 'uncorrected'})
```

- Extract and label if resting state scans are motion corrected

---
### Our finished heuristic (`phantom_heuristic.py`)

```python
import os

def create_key(template, outtype=('nii.gz',), annotation_classes=None):
    if template is None or not template:
        raise ValueError('Template must be a valid format string')
    return template, outtype, annotation_classes

def infotodict(seqinfo):

    t1w = create_key('sub-{subject}/anat/sub-{subject}_T1w')
    dwi = create_key('sub-{subject}/dwi/sub-{subject}_run-{item:01d}_dwi')
    rest = create_key('sub-{subject}/func/sub-{subject}_task-rest_rec-{rec}_run-{item:01d}_bold')

    info = {t1w: [], dwi: [], rest: []}

    for s in seqinfo:
        if (s.dim3 == 176) and (s.dim4 == 1) and ('t1' in s.protocol_name):
          info[t1w] = [s.series_id] # assign if a single series meets criteria
        if (11 <= s.dim3 <= 22) and (s.dim4 == 1) and ('dti' in s.protocol_name):
          info[dwi].append(s.series_id) # append if multiple series meet criteria
        if (s.dim4 > 10) and ('taskrest' in s.protocol_name):
            if s.is_motion_corrected: # exclude non motion corrected series
                info[rest].append({'item': s.series_id, 'rec': 'corrected'})
            else:
                info[rest].append({'item': s.series_id, 'rec': 'uncorrected'})
    return info
```

---

### Step 2: Conversion

```bash
docker run --rm -it -v /path/to/dicoms:/data:ro \
-v /path/to/output/directory:/output nipy/heudiconv:latest \
-d /data/{subject}/YAROSLAV_DBIC-TEST1/*/*/*IMA -s PHANTOM1_3 \
-f /data/phantom_heuristic.py -b -o /output
```

--

- Clear old output directory
- Run the docker command!
- Something missing? Double check your `heuristic` and `dicominfo.tsv`!

---

# Questions?

If something is unclear, or you would like to contribute to this guide, please open an issue or pull request on our [Github repo](https://github.com/nipy/heudiconv)
