FROM python:3.8-buster
WORKDIR /app

COPY requirements.txt /app
COPY mig-updater.py /app
COPY config.json /app

RUN  pip install --no-cache-dir -r /app/requirements.txt
RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] http://packages.cloud.google.com/apt cloud-sdk main" \
| tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && curl --silent https://packages.cloud.google.com/apt/doc/apt-key.gpg \
| apt-key --keyring /usr/share/keyrings/cloud.google.gpg  add - && apt-get update -y && apt-get install google-cloud-sdk -y
CMD ["/bin/bash"]