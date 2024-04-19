FROM python:3.11

RUN apt-get update && apt-get install -y vim
RUN pip install --upgrade pip

RUN mkdir /app
WORKDIR /app

RUN python -mvenv venv
RUN . venv/bin/activate
COPY *.py /app

RUN pip install flask elasticsearch lxml oai_repo requests
COPY *.py /app


CMD ["python", "/app/oaiserver.py"]
