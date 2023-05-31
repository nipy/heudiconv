paper.pdf: paper.md paper.bib
	docker run --rm --volume ${PWD}:/data:Z --user $(shell id -u):$(shell id -g) --env JOURNAL=joss openjournals/inara

clean:
	rm -rf paper/
	paper.jats

upload: paper.pdf
	chmod a+r paper.pdf; scp -p paper.pdf  oneukrainian.com:www/tmp/heudiconv-joss-paper.pdf
	echo "URL: http://oneukrainian.com/tmp/heudiconv-joss-paper.pdf"
