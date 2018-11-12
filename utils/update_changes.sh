#!/bin/bash
#
# Adapted from https://github.com/nipy/nipype/blob/master/tools/update_changes.sh
#
# This is a script to be run before releasing a new version.
#
# Usage /bin/bash update_changes.sh 0.5.1
#

# Setting      # $ help set
set -u         # Treat unset variables as an error when substituting.
set -x         # Print command traces before executing command.

CHANGES=../CHANGELOG.md


# Add changelog documentation
cat > newchanges <<'_EOF'
# Changelog
All notable changes to this project will be documented (for humans) in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

_EOF

# List all merged PRs
curl -s https://api.github.com/repos/nipy/heudiconv/pulls?state=closed+milestone=$1 | jq -r \
'.[] | "\(.title) #\(.number) milestone:\(.milestone.title) \(.merged_at)"' | sed '/null/d' | sed '/milestone:0.5 /d' >> newchanges
echo "" >> newchanges
echo "" >> newchanges


# Elaborate today's release header
HEADER="## [$1] - $(date '+%Y-%m-%d')"
echo $HEADER >> newchanges
echo "TODO Summary" >> newchanges
echo "### Added" >> newchanges
echo "" >> newchanges
echo "### Changed" >> newchanges
echo "" >> newchanges
echo "### Deprecated" >> newchanges
echo "" >> newchanges
echo "### Fixed" >> newchanges
echo "" >> newchanges
echo "### Removed" >> newchanges
echo "" >> newchanges
echo "### Security" >> newchanges
echo "" >> newchanges

# Append old CHANGES
tail -n+7 $CHANGES >> newchanges

# Replace old CHANGES with new file
mv newchanges $CHANGES
