FROM python:3.11

ENV TZ=Europe/Stockholm

RUN apt-get update && apt-get install -y vim
RUN pip install --upgrade pip

RUN mkdir /app
WORKDIR /app

RUN python -mvenv venv
RUN . venv/bin/activate
RUN pip install flask elasticsearch lxml oai_repo requests

COPY *.py /app

# TBD : Fix this, point oai_repo so a local fork / copy
COPY oai_repo/*.py venv/lib/python3.11/site-packages/oai_repo/
COPY oai_repo/*.py /usr/local/lib/python3.11/site-packages/oai_repo/

CMD ["python", "/app/oaiserver.py"]
