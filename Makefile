OCI_BINARY?=docker
# For docker, we must specify user so resultant file is not owned by root.
ifeq ($OCI_BINARY,docker)
USER_ARG="--user $(id -u):$(id -g)"
else
# For Podman, the root user maps to the user running podman.
# We should not specify a user, it will map to a different UID
USER_ARG=
endif


.PHONY: paper
paper: paper.md paper.bib
	$(OCI_BINARY) run $(USER_ARG) --rm --volume ${PWD}:/data:Z --env JOURNAL=joss docker.io/openjournals/inara

.PHONY: clean
clean:
	rm -rf paper/
	paper.jats

upload: paper.pdf
	chmod a+r paper.pdf; scp -p paper.pdf  oneukrainian.com:www/tmp/heudiconv-joss-paper.pdf
	echo "URL: http://oneukrainian.com/tmp/heudiconv-joss-paper.pdf"
