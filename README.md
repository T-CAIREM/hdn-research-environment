# hdn-research-environment
A Django app for supporting cloud-native research environments

## Deployment configuration

The host Django project supplies the site's branding and cloud identity domain:

- `SITE_NAME` supplies the name shown in billing instructions (and existing emails).
- `SUPPORT_EMAIL`, if set, supplies support links and error messages. Otherwise
  `CONTACT_EMAIL`, then `DEFAULT_FROM_EMAIL`, is used. Display-name addresses such
  as `PhysioNet Support <help@physionet.org>` are accepted; links use the bare email.
- `CLOUD_RESEARCH_ENVIRONMENTS_ORGANIZATION_DOMAIN` optionally overrides the domain
  used by the collaborator forms, for example `physionet.org`. When unset or empty,
  it is derived from the signed-in user's **cloud identity** email, not their login
  email or the site's hostname. Without either source, the forms use ordinary
  email validation; server-side collaborator access checks still apply.

These are Django settings, not environment variables read by this package. No
additional context processor is required. The owner is identified by their full
cloud identity email and is excluded from collaborator removal controls.

### Feature settings

- `CLOUD_RESEARCH_ENVIRONMENTS_ENABLE_DRAFT_WORKBENCHES` (default `False`) lets
  researchers attach their own editable draft projects to new Jupyter and RStudio
  workbenches with a read-write mount. While it is off, the creation form offers
  only published projects, a draft selection is rejected, and draft state changes
  queue no background work. Workbenches created while it was on are left as they are.

## Regression tests

The Python tests run in a configured PhysioNet Django host with this checkout on
`PYTHONPATH` and cloud research environments enabled. Use a dedicated test
database (not the host's development database):

```sh
python manage.py test environment.tests.test_deployment_config environment.tests.test_services.CreateCloudIdentityTestCase --settings=<host_test_settings>
```

The collaborator submit handlers also have dependency-free tests using Node.js
18 or newer:

```sh
node --test environment/tests/test_collaborator_domains.cjs
```

# Publishing a new version

Create the package:
```
python setup.py sdist
```

Publish the package:
```
python -m twine upload dist/*
```
