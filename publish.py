import pika

HOST = '10.0.18.16'

credentials = pika.PlainCredentials('signals', 'insecure')
parameters = pika.ConnectionParameters(HOST, 5672, 'vhost', credentials)
connection = pika.BlockingConnection(parameters)
channel = connection.channel()
channel.queue_declare(queue='seda-mb', durable=True)
channel.basic_publish(exchange='seda-mb-exchange', routing_key='hello', body="Hello $

print("Data is successfully published to MB queue !!")
connection.close()