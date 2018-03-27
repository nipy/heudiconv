#!/bin/bash
# A script which is for now very ad-hoc and to be ran outside of this codebase and
# assumes having two repos of heudiconv -- one under heudiconv and another heudiconv-master
# with virtualenvs setup inside under venvs/dev.
# Was used for https://github.com/nipy/heudiconv/pull/129

PS1=+
set -eu

outdir=${OUTDIR:=compare-versions}

RUN=echo
RUN=

#if [ -e $outdir ]; then
#   # just fail if exists already
#   echo "$outdir exists already -- remove if you want to run the comparison" >&2
#   exit 1
#fi

mkdir -p $outdir

function run() {
   heudiconvdir="$1"
   out=$outdir/$2
   shift
   shift
   source $heudiconvdir/venvs/dev/bin/activate
   whichheudiconv=$(which heudiconv)

   # just do full conversion
   echo "Running $whichheudiconv with log in $out.log"
   $RUN heudiconv --random-seed 1 -c dcm2niix -o $out --datalad --bids "$@" >| $out.log 2>&1
}

other=other
run heudiconv        $other "$@"
run heudiconv-master master "$@"

cd $outdir
#git remote add rolando "$outdir/rolando"
#git fetch rolando
# git diff --stat rolando/master..
if diff  -Naur --exclude=.git --ignore-matching-lines='^\s*id\s*=.*' $other master >| diff.patch; then
    echo "Results are identical"
else
    echo "Results differ: $PWD/diff.patch"
    cat diff.patch | diffstat
fi

