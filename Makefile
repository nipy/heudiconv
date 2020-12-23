PYTHON ?= python3

all:
	echo 'nothing by default'

prep_release:
	# take previous one, and replace with the next one
	utils/prep_release

release-pypi: prep_release
	# avoid upload of stale builds
	test ! -e dist
	# make sure all is still clean/committed
	! bash -c 'git diff | grep -q .'
	$(PYTHON) setup.py sdist
	$(PYTHON) setup.py bdist_wheel
	twine upload dist/*

