coverage erase
python -m coverage run -m unittest discover -s tests -v
coverage report -m --include="bureaucrat*"
