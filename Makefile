paper.pdf: paper.md paper.bib
	docker run --rm --volume ${PWD}/:/data --user $(id -u):$(id -g) --env JOURNAL=joss openjournals/inara

clean:
	rm -rf paper/
	paper.jats
