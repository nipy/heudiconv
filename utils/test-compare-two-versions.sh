#!/bin/bash
# A script which is for now very ad-hoc and to be ran outside of this codebase and
# be provided with two repos of heudiconv,
# with virtualenvs setup inside under venvs/dev3.
# Was used for https://github.com/nipy/heudiconv/pull/129
#
# Sample invocation
#  $> datalad install -g ///dicoms/dartmouth-phantoms/bids_test4-20161014/phantom-1
#  $> heudiconv/utils/test-compare-two-versions.sh heudiconv-{0.5.x,master} --bids -f reproin --files dartmouth-phantoms/bids_test4-20161014/phantom-1
# where heudiconv-0.5.x and heudiconv-master have two worktrees with different
# branches checked out and envs/dev3 environments in each

PS1=+
set -eu

outdir=${OUTDIR:=compare-versions}

RUN=echo
RUN=time


function run() {
   heudiconvdir="$1"
   out=$outdir/$2
   shift
   shift
   source $heudiconvdir/venvs/dev3/bin/activate
   whichheudiconv=$(which heudiconv)
   # to get "reproducible" dataset UUIDs (might be detrimental if we had multiple datalad calls
   # but since we use python API for datalad, should be Ok)
   export DATALAD_SEED=1


   if [ ! -e "$out" ]; then
	  # just do full conversion
	  echo "Running $whichheudiconv with log in $out.log"
	  $RUN heudiconv --random-seed 1 -o $out "$@" >| $out.log 2>&1 \
	  || {
		  echo "Exited with $?  Check $out.log" >&2
		  exit $?
	  }
   else
	   echo "Not running heudiconv since $out already exists"
   fi
}

d1=$1; v1=$(git -C "$d1" describe); shift
d2=$1; v2=$(git -C "$d2" describe); shift
diff="$v1-$v2.diff"

function show_diff() {
	cd $outdir
	diff_full="$PWD/$diff"
	#git remote add rolando "$outdir/rolando"
	#git fetch rolando
	# git diff --stat rolando/master..
	if diff  -Naur --exclude=.git  --ignore-matching-lines='^\s*\(id\s*=.*\|"HeudiconvVersion": \)' "$v1" "$v2" >| "$diff_full"; then
		echo "Results are identical"
	else
		echo "Results differ: $diff_full"
		cat "$diff_full" | diffstat
	fi
	if hash xsel; then
		echo "$diff_full" | xsel -i
	fi
}

mkdir -p $outdir

if [ ! -e "$outdir/$diff" ]; then
	run "$d1" "$v1" "$@"
	run "$d2" "$v2" "$@"
fi

show_diff
