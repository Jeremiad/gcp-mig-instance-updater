FROM google/cloud-sdk:latest
WORKDIR /app

COPY requirements.txt /app
COPY mig-updater.py /app
COPY config.json /app

RUN  apt-get update && \
     apt-get install python-pip -y && \
     apt-get install libmariadbclient-dev -y && \
     pip install --no-cache-dir -r /app/requirements.txt
CMD ["/bin/bash"]