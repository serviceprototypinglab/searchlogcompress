# Build instructions: docker build -t slc .

FROM python:3-slim

LABEL maintainer="spio@zhaw.ch"

#RUN pip3 install pulsar-client

COPY *.py slc-init.sh /opt/

EXPOSE 7777

CMD ["/opt/slc-init.sh"]
