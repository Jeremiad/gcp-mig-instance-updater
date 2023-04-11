# GCP Managed Instance updater

Update GCP Managed instance group instances easily

## Requirements

* Python 2.7+
* Required Python modules: https://github.com/Jeremiad/mig-updater/blob/master/requirements.txt
* Google Cloud SDK installed https://cloud.google.com/sdk/install
* Authenticated Cloud SDK https://cloud.google.com/sdk/docs/authorizing

## Virtualenv setup
```virtualenv .```
or
```python -m virtualenv .```
Linux:
```.\bin\pip.exe install -r requirements.txt```
Windows:
```.\Scripts\pip.exe install -r .\requirements.txt```

## Usage

Can be used with gcloud **application-default-credentials** or by specifying **GOOGLE_APPLICATION_CREDENTIALS=** before command.

Database settings can be used from config.json or from environment variables.

### Normal

```
$ python mig-updater <friendly_name> <ssh username> <path to ssh key>
```

### Docker

```
$ docker build . -t mig-updater
```

```
$ docker run -it mig-updater python /app/mig-updater.py <friendly_name> <ssh username> <path to ssh key>
```


