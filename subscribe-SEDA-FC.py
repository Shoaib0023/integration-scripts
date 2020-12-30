#!/usr/bin/env python
import pika
import requests
import json
import base64
import psycopg2
from urllib.request import urlopen
from urllib.parse import urlparse
from os.path import splitext
import uuid

# RabbitMQ connection credentials
HOST = "3.126.254.35"
credentials = pika.PlainCredentials('signals', 'insecure')
parameters = pika.ConnectionParameters(HOST, 5672, 'vhost', credentials)


def callback(ch, method, properties, body):
    print("Creating a report in Facilitator ....")
    data = json.loads(body)['signals']
    print(data)
    url = data.pop('url', None)
    img_present = False

    if url:
        img_present = True
        img = urlopen(url)
        path = urlparse(url).path
        ext = splitext(path)[1]
        # print(img.headers)
        name = str(uuid.uuid4()) + ext
        
        files = {'report_pic': (name, img.read(), "multipart/form-data")}

    api = 'http://facilitator.dev.mcc.kpnappfactory.nl/index.php/apinewchanges/submit_report_api'
   
    try:
        if img_present:
            response = requests.post(api, data=data, files=files)
        else:
            response = requests.post(api, data=data)

        print(response.status_code)
        # print(response.text)
        if response.status_code == 201:
            print("Created.....")

    except:
        print("Image is not passed !!!")

    print("\n")


connection = pika.BlockingConnection(parameters)
channel = connection.channel()
channel.queue_declare(queue='SEDA-FC', durable=True)
channel.basic_consume(queue='SEDA-FC', on_message_callback=callback, auto_ack=True)

print(' [*] Waiting for messages. To exit press CTRL+C')
channel.start_consuming()