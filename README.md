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

# Credentials

HDN is using sops to manage credentials internally in the project

### Prerequisites

Install sops:

```commandline
brew install sops
```

Establish connection with GCP as sops are using GCP Cloud Key Management to ensure security of encryption key.

### Credentials Management

To decrypt credentials in directory `./credentials/dev` or `./credentials/prod` use

```commandline
sops --decrypt credentials.enc.json > credentials.json
```

To update credentials decrypt them using above command, change or add new value in `credentials.json` file, and encrypt using:

```commandline
sops --encrypt credentials.json > credentials.enc.json
```

*REMEMBER THAT ONLY ENCRYPTED FILE NEEDS TO BE PUSHED TO REMOTE REPOSITORY*
