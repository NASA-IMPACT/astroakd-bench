# AstroAKD-Bench documentation Makefile — invoke from any working directory:
#   make -C docs/sphinx html
#   cd docs/sphinx && make html
# The Sphinx source is docs/, and output is docs/_build/html/.
_THIS_MAKEFILE := $(abspath $(lastword $(MAKEFILE_LIST)))
ROOTDIR := $(abspath $(dir $(_THIS_MAKEFILE))/../..)
SOURCEDIR := $(ROOTDIR)/docs
BUILDDIR := $(SOURCEDIR)/_build
SPHINXBUILD ?= uv run --project $(ROOTDIR) --extra docs sphinx-build
SPHINXOPTS ?= -n -W --keep-going

.DEFAULT_GOAL := html
.PHONY: html clean linkcheck help

html:
	$(SPHINXBUILD) -b html $(SPHINXOPTS) $(SOURCEDIR) $(BUILDDIR)/html

linkcheck:
	$(SPHINXBUILD) -b linkcheck $(SOURCEDIR) $(BUILDDIR)/linkcheck

clean:
	rm -rf $(BUILDDIR)

help:
	@echo 'make -C docs/sphinx html                 Build HTML under docs/_build/html/'
	@echo 'make -C docs/sphinx clean                Remove all Sphinx build outputs'
	@echo 'make -C docs/sphinx linkcheck            Check remote URLs (network required)'
	@echo 'make -C docs/sphinx html SPHINXBUILD=sphinx-build  Use installed Sphinx'
