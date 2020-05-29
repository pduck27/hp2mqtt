FROM python:alpine

RUN pip install paho.mqtt pyyaml requests

RUN mkdir /opt/hp2mqtt
RUN mkdir /opt/hp2mqtt/data
RUN mkdir /opt/hp2mqtt/log

ADD hp2mqtt.py /opt/hp2mqtt

# Create User
RUN addgroup --system --gid 1000 hp2mqtt
RUN adduser --system --no-create-home --disabled-password --home /opt/hp2mqtt --shell /bin/sh --uid 1000 --ingroup hp2mqtt hp2mqtt
RUN chown -R hp2mqtt:hp2mqtt /opt/hp2mqtt

# Define Volumes
VOLUME /opt/hp2mqtt/data
VOLUME /opt/hp2mqtt/log

WORKDIR /opt/hp2mqtt
USER hp2mqtt

CMD python hp2mqtt.py