# hdn-research-environment
A Django app for supporting cloud-native research environments

# Publishing a new version

Create the package:
```
python setup.py sdist
```

Publish the package:
```
python -m twine upload dist/*
```
