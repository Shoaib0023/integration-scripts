FROM python:3.7.5-slim

WORKDIR /app

RUN apt-get update -y && \
    apt-get install -y python3-pip python3-dev

RUN pip3 install -r requirements.txt

COPY . /app

CMD [ "bash", '-c', "python", "/app/demo.py" ]