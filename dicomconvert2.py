#!/software/python/anaconda/envs/resting/bin/python

"""Convert dicom TimTrio dirs based on heuristic info

This function uses DicomStack and mri_convert to convert Siemens
TrioTim directories. It proceeeds by extracting dicominfo from each
subject and writing a config file $subject_id/$subject_id.auto.txt in
the output directory. Users can create a copy of the file called
$subject_id.edit.txt and modify it to change the files that are
converted. This edited file will always overwrite the original file. If
there is a need to revert to original state, please delete this edit.txt
file and rerun the conversion

"""

import argparse
from copy import deepcopy
from glob import glob
import inspect
import json
import os
import shutil
import sys
from tempfile import mkdtemp

import dicom as dcm
import dcmstack as ds
from dcmstack import DcmMetaExtension
import nibabel as nb
import numpy as np

def save_json(filename, data):
    """Save data to a json file

    Parameters
    ----------
    filename : str
        Filename to save data in.
    data : dict
        Dictionary to save in json file.

    """

    fp = file(filename, 'w')
    json.dump(data, fp, sort_keys=True, indent=4)
    fp.close()


def load_json(filename):
    """Load data from a json file

    Parameters
    ----------
    filename : str
        Filename to load data from.

    Returns
    -------
    data : dict

    """

    fp = file(filename, 'r')
    data = json.load(fp)
    fp.close()
    return data


def process_dicoms(fl):
    groups = [[], []]
    mwgroup = []
    for fidx, filename in enumerate(fl):
        mw = ds.wrapper_from_data(dcm.read_file(filename, force=True))
        try:
            del mw.series_signature['iop']
        except:
            pass
        try:
            del mw.series_signature['ICE_Dims']
        except:
            pass
        try:
            del mw.series_signature['SequenceName']
        except:
            pass
        if not groups:
            mwgroup.append(mw)
            groups[0].append(int(mw.dcm_data.SeriesNumber))
            groups[1].append(len(mwgroup) - 1)
            continue
        N = len(mwgroup)
        #print fidx, N, filename
        ingrp = False
        for idx in range(N):
            same = mw.is_same_series(mwgroup[idx])
            #print idx, same, groups[idx][0] 
            if same:
                groups[0].append(int(mwgroup[idx].dcm_data.SeriesNumber))
                groups[1].append(idx)
                ingrp = True
        if not ingrp:
            mwgroup.append(mw)
            groups[0].append(int(mw.dcm_data.SeriesNumber))
            groups[1].append(len(mwgroup) - 1)

    group_map = dict(zip(groups[0], groups[1]))
    
    total = 0
    filegroup = {}
    seqinfo = []
    for series, mwidx in sorted(group_map.items()):
        mw = mwgroup[mwidx]
        dcminfo = mw.dcm_data
        files = np.array(fl)[np.array(groups[0]) == series].tolist()
        filegroup[series] = files
        size = list(mw.image_shape) + [len(files)]
        total += size[-1]
        if len(size) < 4:
            size.append(1)
        try:
            TR = float(dcminfo.RepetitionTime)/1000.
        except AttributeError:
            TR = -1
        try:
            TE = float(dcminfo.EchoTime)
        except AttributeError:
            TE = -1
        info = [total, os.path.split(files[0])[1], series, '-', '-', '-'] + \
               size + [TR, TE, dcminfo.ProtocolName, 'MoCo' in dcminfo.SeriesDescription]
        seqinfo.append(info)
    return seqinfo, filegroup


def write_config(outfile, info):
    from pprint import PrettyPrinter
    with open(outfile, 'wt') as fp:
        fp.writelines(PrettyPrinter().pformat(info))

def read_config(infile):
    info = None
    with open(infile, 'rt') as fp:
        info = eval(fp.read())
    return info

def conversion_info(subject, outdir, info, filegroup):
    convert_info = []
    for key, items in info.items():
        if not items:
            continue
        template = key[0]
        outtype = key[1]
        outpath = outdir
        for idx, itemgroup in enumerate(items):
            if not isinstance(itemgroup, list):
                itemgroup = [itemgroup]
            for subindex, item in enumerate(itemgroup):
                outprefix = template.format(item=idx + 1, subject=subject, seqitem=item, subindex=subindex + 1)
                try:
                    convert_info.append((os.path.join(outpath, outprefix), outtype, filegroup[item]))
                except KeyError:
                    convert_info.append((os.path.join(outpath, outprefix), outtype, filegroup[unicode(item)]))
    return convert_info


def embed_nifti(dcmfiles, niftifile, infofile, force=False):
    import dcmstack as ds
    import nibabel as nb
    import os
    stack = ds.parse_and_stack(dcmfiles, force=force).values()
    if len(stack) > 1:
        raise ValueError('Found multiple series')
    stack = stack[0]
        
    #Create the nifti image using the data array
    if not os.path.exists(niftifile):
        nifti_image = stack.to_nifti(embed_meta=True)
        nifti_image.to_filename(niftifile)
        return ds.NiftiWrapper(nifti_image).meta_ext.to_json()
    orig_nii = nb.load(niftifile)
    orig_hdr = orig_nii.get_header()
    aff = orig_nii.get_affine()
    ornt = nb.orientations.io_orientation(aff)
    axcodes = nb.orientations.ornt2axcodes(ornt)
    new_nii = stack.to_nifti(voxel_order=''.join(axcodes), embed_meta=True)
    new_hdr = new_nii.get_header()
    #orig_hdr.extensions = new_hdr.extensions
    #orig_nii.update_header()
    #orig_nii.to_filename(niftifile)
    meta = ds.NiftiWrapper(new_nii).meta_ext.to_json()
    with open(infofile, 'wt') as fp:
        fp.writelines(meta)
    return niftifile, infofile

def convert(items, anonymizer=None, symlink=True, converter=None):
    prov_files = []
    tmpdir = mkdtemp()
    for item in items:
        if isinstance(item[1], (list, tuple)):
            outtypes = item[1]
        else:
            outtypes = [item[1]]
        prefix = item[0]
        print('Converting %s' % prefix)
        dirname = os.path.dirname(prefix + '.ext')
        print(dirname)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        for outtype in outtypes:
            print(outtype)
            if outtype == 'dicom':
                dicomdir = prefix + '_dicom'
                if os.path.exists(dicomdir):
                    shutil.rmtree(dicomdir)
                os.mkdir(dicomdir)
                for filename in item[2]:
                    outfile = os.path.join(dicomdir, os.path.split(filename)[1])
                    if not os.path.islink(outfile):
                        if symlink:
                            os.symlink(filename, outfile)
                        else:
                            os.link(filename, outfile)
            elif outtype in ['nii', 'nii.gz']:
                outname = prefix + '.' + outtype
                scaninfo = prefix + '_scaninfo.json'
                if not os.path.exists(outname):
                    from nipype import config
                    config.enable_provenance()
                    from nipype import Function, Node
                    from nipype.interfaces.base import isdefined
                    print converter
                    if converter == 'mri_convert':
                        from nipype.interfaces.freesurfer.preprocess import MRIConvert
                        convertnode = Node(MRIConvert(), name = 'convert')
                        convertnode.base_dir = tmpdir
                        if outtype == 'nii.gz':
                            convertnode.inputs.out_type = 'niigz'
                        convertnode.inputs.in_file = item[2][0]
                        convertnode.inputs.out_file = outname
                        #cmd = 'mri_convert %s %s' % (item[2][0], outname)
                        #print(cmd)
                        #os.system(cmd)
                        res=convertnode.run()
                    elif converter == 'dcm2nii':
                        from nipype.interfaces.dcm2nii import Dcm2nii
                        convertnode = Node(Dcm2nii(), name='convert')
                        convertnode.base_dir = tmpdir
                        convertnode.inputs.source_names = item[2]
                        convertnode.inputs.gzip_output = outtype == 'nii.gz'
                        convertnode.inputs.terminal_output = 'allatonce'
                        res = convertnode.run()
                        if isinstance(res.outputs.converted_files, list):
                            print("Cannot convert dicom files - series likely has multiple orientations: ", item[2])
                            continue
                        else:
                            shutil.copyfile(res.outputs.converted_files, outname)
                        if isdefined(res.outputs.bvecs):
                            outname_bvecs = prefix + '.bvecs'
                            outname_bvals = prefix + '.bvals'
                            shutil.copyfile(res.outputs.bvecs, outname_bvecs)
                            shutil.copyfile(res.outputs.bvals, outname_bvals)
                    prov_file = prefix + '_prov.ttl'
                    shutil.copyfile(os.path.join(convertnode.base_dir,
                                                 convertnode.name,
                                                 'provenance.ttl'),
                                    prov_file)
                    prov_files.append(prov_file)
                    embedfunc = Node(Function(input_names=['dcmfiles',
                                                           'niftifile',
                                                           'infofile',
                                                           'force'],
                                              output_names=['outfile',
                                                            'meta'],
                                              function=embed_nifti),
                                     name='embedder')
                    embedfunc.inputs.dcmfiles = item[2]
                    embedfunc.inputs.niftifile = outname
                    embedfunc.inputs.infofile = scaninfo
                    embedfunc.inputs.force = True
                    embedfunc.base_dir = tmpdir
                    res = embedfunc.run()
                    g = res.provenance.rdf()
                    g.parse(prov_file,
                            format='turtle')
                    g.serialize(prov_file, format='turtle')
                    #out_file, meta_dict = embed_nifti(item[2], outname, force=True)
                    os.chmod(outname, 0440)
                    os.chmod(scaninfo, 0440)
                    os.chmod(prov_file, 0440)
    shutil.rmtree(tmpdir)


def convert_dicoms(subjs, dicom_dir_template, outdir, heuristic_file, converter,
                   queue=None):
    for sid in subjs:
        if queue:
            progname = os.path.abspath(inspect.getfile(inspect.currentframe()))
            convertcmd = ' '.join(['python', progname, '-d', dicom_dir_template,
                                   '-o', outdir, '-f', heuristic_file, '-s', sid, 
                                   '-c', converter])
            script_file = 'sg-%s.sh' % sid
            with open(script_file, 'wt') as fp:
                fp.writelines(['#!/bin/bash\n', convertcmd])
            outcmd = 'sbatch -J sg-%s -p %s -N1 -c2 --mem=20G %s' % (sid, queue, script_file)
            os.system(outcmd)
            continue
        sdir = dicom_dir_template % sid
        fl = sorted(glob(sdir))
        #dcmfile = dcm.read_file(fl[0], force=True)
        #print sid, 'Dicom: ', dcmfile.PatientName, sid == dcmfile.PatientName 
        tdir = os.path.join(outdir, sid)
        idir = os.path.join(tdir, 'info')
        if not os.path.exists(idir):
            os.makedirs(idir)
        shutil.copy(heuristic_file, idir)
        path, fname = os.path.split(heuristic_file)
        sys.path.append(path)
        mod = __import__(fname.split('.')[0])

        infofile =  os.path.join(idir, '%s.auto.txt' % sid)
        editfile =  os.path.join(idir, '%s.edit.txt' % sid)
        if os.path.exists(editfile):
            info = read_config(editfile)
            filegroup = load_json(os.path.join(idir, 'filegroup.json'))
        else:
            seqinfo, filegroup = process_dicoms(fl)
            save_json(os.path.join(idir, 'filegroup.json'), filegroup)
            with open(os.path.join(idir, 'dicominfo.txt'), 'wt') as fp:
                for seq in seqinfo:
                    fp.write('\t'.join([str(val) for val in seq]) + '\n')
            info = mod.infotodict(seqinfo)
            write_config(infofile, info)
            write_config(editfile, info)
        cinfo = conversion_info(sid, tdir, info, filegroup)
        convert(cinfo, converter=converter)


if __name__ == '__main__':
    docstr= '\n'.join((__doc__,
"""
           Example:

           dicomconvert2.py -d rawdata/%s -o . -f heuristic.py -s s1 s2
s3
"""))
    parser = argparse.ArgumentParser(description=docstr)
    parser.add_argument('-d','--dicom_dir_template',
                        dest='dicom_dir_template',
                        required=True,
                        help='location of dicomdir that can be indexed with subject id'
                        )
    parser.add_argument('-s','--subjects',dest='subjs', required=True,
                        type=str, nargs='+', help='list of subjects')
    parser.add_argument('-c','--converter', dest='converter',
                        default='dcm2nii',
                        choices=('mri_convert', 'dcmstack', 'dcm2nii'),
                        help='tool to use for dicom conversion')
    parser.add_argument('-o','--outdir', dest='outputdir',
                        default=os.getcwd(),
                        help='output directory for conversion')
    parser.add_argument('-f','--heuristic', dest='heuristic_file', required=True,
                        help='python script containing heuristic')
    parser.add_argument('-q','--queue',dest='queue',
                        help='SLURM partition to use if available')
    args = parser.parse_args()
    convert_dicoms(args.subjs, os.path.abspath(args.dicom_dir_template),
                   os.path.abspath(args.outputdir),
                   heuristic_file=os.path.realpath(args.heuristic_file),
                   converter=args.converter,
                   queue=args.queue)
