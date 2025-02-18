
Some notes on the steps which were taken within the repo to make it fit
for running those scripts to collect all the authors info etc.
- TODO: describe how to get all the bugs
  - commit a4317f81b846f91070aa71f98336c8ee4c4bf17c
    has record of
    `git -C ../heudiconv-bugs bug bug -f json > all-bugs.json`
    where https://github.com/git-bug/git-bug was used to fetch all issues
    for the repo
- Dataset created with -c text2git but modified .gitattributess to consider .json tobe large too
- Create venv: `py=3; d=venvs/dev$py; python$py -m venv $d && source $d/bin/activate && pip install -r tools/requirements.txt`
- `git config annex.addunlocked true` to commit by default unlocked
- GH_TOKEN to interact with github
