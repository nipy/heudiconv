import os
import os.path as op

import logging

lgr = logging.getLogger(__name__)

# start with SLURM but extend past that #TODO
def queue_conversion(progname, queue, outdir, heuristic, dicoms, sid,
                     anon_cmd, converter, session,with_prov, bids):

        # Rework this...
        convertcmd = ' '.join(['python', progname,
                               '-o', outdir,
                               '-f', heuristic,
                               '-s', sid,
                               '--anon-cmd', anon_cmd,
                               '-c', converter])
        if session:
            convertcmd += " --ses '%s'" % session
        if with_prov:
            convertcmd += " --with-prov"
        if bids:
            convertcmd += " --bids"
        if dicoms:
            convertcmd += " --files"
            convertcmd += [" '%s'" % f for f in dicoms]

        script_file = 'dicom-%s.sh' % sid
        with open(script_file, 'wt') as fp:
            fp.writelines(['#!/bin/bash\n', convertcmd])
        outcmd = 'sbatch -J dicom-%s -p %s -N1 -c2 --mem=20G %s' \
                 % (sid, queue, script_file)

        os.system(outcmd)
