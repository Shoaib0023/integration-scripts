import pika

HOST = '10.0.18.16'

credentials = pika.PlainCredentials('signals', 'insecure')
parameters = pika.ConnectionParameters(HOST, 5672, 'vhost', credentials)


def callback(ch, method, properties, body):
    print("Received : ", body)

connection = pika.BlockingConnection(parameters)
channel = connection.channel()
channel.queue_declare(queue='SEDA-MB', durable=True)
channel.basic_consume(queue='SEDA-MB', on_message_callback=callback, auto_ack=Tr$


print('[*] Waiting for messages. To exit press CTRL+C')
channel.start_consuming()