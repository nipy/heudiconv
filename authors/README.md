
Some notes on the steps which were taken within the repo to make it fit
for running those scripts to collect all the authors info etc.
- TODO: describe how to get all the bugs
- Dataset created with -c text2git but modified .gitattributess to consider .json tobe large too
- Create venv: `py=3; d=venvs/dev$py; python$py -m venv $d && source $d/bin/activate && pip install -r tools/requirements.txt`
- `git config annex.addunlocked true` to commit by default unlocked
- GH_TOKEN to interact with github
