#!/usr/bin/env bash

dot -Tpdf ../data/workflow.dot -o ../figs/workflow.pdf
dot -Tpng ../data/workflow.dot -o ../figs/workflow.png
