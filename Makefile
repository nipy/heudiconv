OCI_BINARY?=docker

.PHONY: paper
paper: paper.md paper.bib
	$(OCI_BINARY) run --rm --volume ${PWD}:/data:Z --user $(shell id -u):$(shell id -g) --env JOURNAL=joss openjournals/inara

.PHONY: clean
clean:
	rm -rf paper/
	paper.jats

upload: paper.pdf
	chmod a+r paper.pdf; scp -p paper.pdf  oneukrainian.com:www/tmp/heudiconv-joss-paper.pdf
	echo "URL: http://oneukrainian.com/tmp/heudiconv-joss-paper.pdf"
