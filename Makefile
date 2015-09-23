PREFIX ?= /usr/local

all:

install:
	mkdir -p $(DESTDIR)$(PREFIX)/share/heudiconv/heuristics
	mkdir -p $(DESTDIR)$(PREFIX)/share/doc/heudiconv/examples/heuristics
	mkdir -p $(DESTDIR)$(PREFIX)/bin
	install -t $(DESTDIR)$(PREFIX)/bin bin/heudiconv
	install -m 644 -t $(DESTDIR)$(PREFIX)/share/heudiconv/heuristics heuristics/*
	install -m 644 -t $(DESTDIR)$(PREFIX)/share/doc/heudiconv/examples/heuristics/  examples/heuristics/*

uninstall:
	rm -f $(DESTDIR)$(PREFIX)/bin/heudiconv
	rm -fr $(DESTDIR)$(PREFIX)/share/heudiconv
	rm -fr $(DESTDIR)$(PREFIX)/share/doc/heudiconv
