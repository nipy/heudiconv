#!/usr/bin/env bash

dot -Tpng ../data/environment.dot -o ../figs/environment.png
dot -Tpdf ../data/environment.dot -o ../figs/environment.pdf
