PREFIX ?= /usr/local

all:

install:
	mkdir -p $(DESTDIR)$(PREFIX)/share/heudiconv/heuristics
	mkdir -p $(DESTDIR)$(PREFIX)/share/doc/heudiconv/examples/heuristics
	mkdir -p $(DESTDIR)$(PREFIX)/bin
	install bin/heudiconv $(DESTDIR)$(PREFIX)/bin
	install -m 644 heuristics/* $(DESTDIR)$(PREFIX)/share/heudiconv/heuristics

uninstall:
	rm -f $(DESTDIR)$(PREFIX)/bin/heudiconv
	rm -fr $(DESTDIR)$(PREFIX)/share/heudiconv
	rm -fr $(DESTDIR)$(PREFIX)/share/doc/heudiconv
