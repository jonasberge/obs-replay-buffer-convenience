# Make sure to create a Python 3.6 virtualenv first and activate it before running any of these targets!

pip-install:
	pip install -r requirements.txt

local-python-packages:
	pip install -r requirements.txt --target ./replay-buffer-convenience/python-packages --upgrade

install-only:
	cp -rf replay-buffer-convenience* "C:\\Program Files\\obs-studio\\data\\obs-plugins\\frontend-tools\\scripts"

install: local-python-packages install-only

.PHONY: pip-install local-python-packages install install-only
