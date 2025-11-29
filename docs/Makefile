html:
	sphinx-build -b html . _build/html

clean:
	rm -rf _build

pdf:
	sphinx-build -b latex . _build/latex && make -C _build/latex all-pdf
