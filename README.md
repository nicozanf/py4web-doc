# py4web-doc
[![docs_pages_workflow](https://github.com/nicozanf/py4web-doc/actions/workflows/docs_pages_workflow.yml/badge.svg)](https://github.com/nicozanf/py4web-doc/actions/workflows/docs_pages_workflow.yml)

## py4web documentation with rtd style

See it  [here](https://nicozanf.github.io/py4web-doc)!


Created with sources from the py4web official documentation (https://github.com/web2py/py4web/tree/master/apps/_documentation) in MarkMin format plus regex magic
to obtain standard MarkDown documents. Then I've shrunk them with Pandoc (https://pandoc.org/) to obtain the rst files.

Finally I've followed the excellent work of Michael Altfield on https://tech.michaelaltfield.net/2020/07/18/sphinx-rtd-github-pages-1/ in order to have HTML, PDF and EPUB
automagically published and updated on GitHub pages at https://nicozanf.github.io/py4web-doc



** Using the project locally 

You can download this project, change it and test the results (english and HTML only) on Linux with a 'make clean && make html' command on the docs folder. The HTML output is under the _build folder.
Sphinx libraries are needed - see Michael's work. 

** MarkMin converter

The attached mm-converter.py program is a simple MarkMin to MarkDown (+ RST & HTML, using Pandoc) converter. Just place it in the same folder of the .mm files and it will try to conver them in the related subfolders. Tested with Ubuntu 20.04 an Python 3.8.4. It needs Pandoc modules installed.
