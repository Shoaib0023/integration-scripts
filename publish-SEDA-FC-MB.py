import psycopg2
from psycopg2 import sql
import psycopg2.extras
import pika
import json
from urllib.request import urlopen
import schedule
import time
import datetime
import os
import base64
import requests
import pytz

tz = pytz.timezone("Europe/Amsterdam")
last_executed_datetime = datetime.datetime.now(tz=tz)

# DB Host
DB_HOST = "seda-backend-db"
DB_PORT = 5409

# SEDA api Host
SEDA_HOST = "seda-backend-api-nodeport"
SEDA_PORT = 8080

# Rabbitmq Host
RABBIT_HOST = "10.0.18.16"
RABBIT_PORT = 5672


def publish():
    global last_executed_datetime
    current = datetime.datetime.now(tz=tz)
    print("Last time : ", last_executed_datetime)
    print("Current Time : ", current)

    connection = False
    try:
        connection = psycopg2.connect(user='signals', password='insecure', host=DB_HOST, port=DB_PORT, database="signals")
        cursor = connection.cursor(cursor_factory = psycopg2.extras.NamedTupleCursor)
        data = {"signals": {}}
        signal_data = data["signals"]

        # ? Fetching a Signal created ones from PostgreSQL
        cursor.execute(sql.SQL('SELECT * FROM signals_signal WHERE created_at BETWEEN (%s) AND (%s) AND source != (%s) '), [last_executed_datetime, current, "MB"])
        signals = cursor.fetchall()
        print(len(signals))

        # ? Fetching a Signal updated ones from PostgreSQL
        cursor.execute(sql.SQL('SELECT * FROM signals_signal WHERE updated_at BETWEEN (%s) AND (%s) AND updated_by = (%s)'), [last_executed_datetime, current, "MB Dept"])
        updated_signals = cursor.fetchall()
        print(len(updated_signals))
        for signal in updated_signals:
            if not (signal.created_at.hour == signal.updated_at.hour and signal.created_at.minute == signal.updated_at.minute):
                signals.append(signal)

        for signal in signals:
            print("Signal : ", signal)
            print("-----------------------------------------------")

            # ? Fetching Location from PostgreSQL
            location_id = signal.location_id
            postgreSQL_select_Query = f"Select * from signals_location where id={location_id}"
            cursor.execute(postgreSQL_select_Query)
            location = cursor.fetchone()
            print("Location : ", location)
            print("-----------------------------------------------")

            postgreSQL_select_Query = f"Select ST_X(signals_location.geometrie) AS X1, ST_Y(signals_location.geometrie) AS Y1 from signals_location where id={location_id}"
            cursor.execute(postgreSQL_select_Query)
            coordinatesObj = cursor.fetchone()
            coordinates = [coordinatesObj[1], coordinatesObj[0]]
            print(type(coordinatesObj[1]))
            coordinates_str = [str(coordinatesObj[1]), str(coordinatesObj[0])]
            print("Coordinates : ", coordinates)

            stadsdeel = location.stadsdeel
            if stadsdeel is None:
                stadsdeel = "Centrum"

            # ? Fetching directing department Object from PostgreSQL 
            directing_department_id = signal.directing_departments_assignment_id
            if directing_department_id:
                cursor.execute(sql.SQL('Select * from signals_directingdepartments_departments where directingdepartments_id=(%s)'), [directing_department_id])
                directingdepartments = cursor.fetchone()
                department_id = directingdepartments.department_id

                postgreSQL_select_Query = f"Select * from signals_department where id={department_id}"
                cursor.execute(postgreSQL_select_Query)
                directing_department = cursor.fetchone()
                print("Directing Departments : ", directing_department)
    
            
            # ? Fetching District Object from PostgreSQL using district assigned 
            # postgreSQL_select_Query = f"Select * from signals_district where name = {stadsdeel}"
            # cursor.execute(postgreSQL_select_Query)
            cursor.execute(sql.SQL('Select * from signals_district where name=(%s)'), [stadsdeel])
            stadsdeelObj = cursor.fetchone()
            print("Stadsdeel : ", stadsdeelObj)
            print("-----------------------------------------------")

            # ? Fetching user associated with district for MB from PostgreSQL
            # postgreSQL_select_Query = f"Select * from users_profile where district={stadsdeelObj}"
            # cursor.execute(postgreSQL_select_Query)
            cursor.execute(sql.SQL('Select * from users_profile where district_id=(%s) AND facilitator_role = (%s)'), [stadsdeelObj.id, "not admin"])
            mbuserProfile = cursor.fetchone()
            print("MB UserProfile : ", mbuserProfile)   

            # ? Fetching user associated with district for FAC from PostgreSQL
            cursor.execute(sql.SQL('Select * from users_profile where district_id=(%s) AND facilitator_role = (%s)'), [stadsdeelObj.id, "admin"])
            facuserProfile = cursor.fetchone()
            print("FAC UserProfile : ", facuserProfile)    

            # ? Fetching Category, Department from PostgreSQL
            categoryassignment_id = signal.category_assignment_id
            postgreSQL_select_Query = f"Select * from signals_categoryassignment where id={categoryassignment_id}"
            cursor.execute(postgreSQL_select_Query)
            categoryassignment = cursor.fetchone()
            #  print(categoryassignment)
            category_id = categoryassignment.category_id
            postgreSQL_select_Query = f"Select * from signals_category where id={category_id}"
            cursor.execute(postgreSQL_select_Query)
            category = cursor.fetchone()

            postgreSQL_select_Query = f"Select * from signals_categorydepartment where category_id={category_id}"
            cursor.execute(postgreSQL_select_Query)
            categorydepartment = cursor.fetchone()
            # print(categorydepartment)
            if categorydepartment:
                department_id = categorydepartment.department_id
                postgreSQL_select_Query = f"Select * from signals_department where id={department_id}"
                cursor.execute(postgreSQL_select_Query)
                department = cursor.fetchone()
                print(department)

            # ? Fetching image from PostgreSQL
            postgreSQL_select_Query = f"Select * from signals_attachment where _signal_id={signal.id}"
            cursor.execute(postgreSQL_select_Query)
            attachment = cursor.fetchone()
            if attachment and attachment.file:
                url = f'http://{SEDA_HOST}/signals/media/' + attachment.file
            else:
                url = ''

            fc_coordinates = '&'.join(coordinates_str)

            # ? Check for APP routing ----
            if directing_department_id:
                if directing_department.app == "FC":
                    signal_data["sedaId"] = signal.signal_id
                    signal_data["source"] = "Seda"
                    signal_data["team_id"] = 0
                    signal_data["tool_id"] = ""
                    signal_data["locations"] = fc_coordinates
                    signal_data["report_type"] = ""
                    signal_data["used_map_type"] = "2",
                    signal_data["language"] = "1"
                    signal_data["description"] = signal.text
                    signal_data["location_type"] = "1"
                    signal_data["map_image_name"] = ""
                    signal_data["url"] = url

                    if facuserProfile:
                        signal_data["districtId"] = facuserProfile.fac_district_id
                        signal_data["neighbourhoodId"] = facuserProfile.fac_neighbourhood_id
                        signal_data["userId"] = facuserProfile.fac_user_id
                    
                    else:
                        signal_data["userId"] = "5f7f2acb00456a103b7b23d3"
                        signal_data["districtId"] = "5c4bed08798064a42b000029"
                        signal_data["neighbourhoodId"] = "5c4c32ad798064601500002d"

                
                    connect_rabbitmq_FC(data)


            elif department.app == "MB":
                signal_data["sedaId"] = signal.signal_id
                signal_data["seda_report_id"] = signal.id
                signal_data["image_url"] = url
                signal_data["description"] = signal.text
                signal_data["address"] = location.address_text
                signal_data["category"] = category.category_level_name1
                signal_data["sub_category"] = category.category_level_name2
                signal_data["sub_category1"] = category.category_level_name3
                signal_data["sub_category2"] = category.category_level_name4
                signal_data["location"] = coordinates
                signal_data["language"] = "1"
                signal_data["source"] = "Seda"
                
                if mbuserProfile:
                    signal_data["user_id"] = mbuserProfile.mb_user_id
                    signal_data["district_id"] = mbuserProfile.mb_district_id 
                    signal_data["neighbourhood_id"] = mbuserProfile.mb_neighbourhood_id

                else:
                    signal_data["user_id"] = "5f86b231646050a801d8dec5"
                    signal_data["district_id"] = "5c4bece1798064240800002c" 
                    signal_data["neighbourhood_id"] = "5f86b231646050a801d8dec4"
                    

                connect_rabbitmq_MB(data)


            elif department.app == "FC":
                signal_data["sedaId"] = signal.signal_id
                signal_data["source"] = "Seda"
                signal_data["team_id"] = 0
                signal_data["tool_id"] = ""
                signal_data["locations"] = fc_coordinates
                signal_data["report_type"] = ""
                signal_data["used_map_type"] = "2",
                signal_data["language"] = "1"
                signal_data["description"] = signal.text
                signal_data["location_type"] = "1"
                signal_data["map_image_name"] = ""
                signal_data["url"] = url

                if facuserProfile:
                    signal_data["districtId"] = facuserProfile.fac_district_id
                    signal_data["neighbourhoodId"] = facuserProfile.fac_neighbourhood_id
                    signal_data["userId"] = facuserProfile.fac_user_id
                    
                else:
                    signal_data["userId"] = "5f7f2acb00456a103b7b23d3"
                    signal_data["districtId"] = "5c4bed08798064a42b000029"
                    signal_data["neighbourhoodId"] = "5c4c32ad798064601500002d"

                connect_rabbitmq_FC(data)


    except (Exception, psycopg2.Error) as error :
        print ("Error while connecting to PostgreSQL", error)

    finally:
        if(connection):
            cursor.close()
            connection.close()

    last_executed_datetime = current - datetime.timedelta(microseconds=1)
    print("---------------------------------------------------")
    print("  [*] Waiting for new signals. To exit press CTRL+C")



# Function to publish data to rabbitmq
def connect_rabbitmq_MB(data):
    print("Data Published : ", data)
    credentials = pika.PlainCredentials('signals', 'insecure')
    parameters = pika.ConnectionParameters(RABBIT_HOST, RABBIT_PORT, 'vhost', credentials)

    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    channel.queue_declare(queue='SEDA-MB', durable=True)
    channel.basic_publish(exchange='SEDA-MB-exchange', routing_key='insecure', body=json.dumps(data, indent=4, sort_keys=True, default=str))

    print("Data is successfully published to MB queue !!")
    connection.close()



# Function to publish data to rabbitmq
def connect_rabbitmq_FC(data):
    print("Data Published : ", data)
    try:
        credentials = pika.PlainCredentials('signals', 'insecure')
        parameters = pika.ConnectionParameters(RABBIT_HOST, RABBIT_PORT, 'vhost', credentials)
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        channel.queue_declare(queue='SEDA-FC', durable=True)
        channel.basic_publish(exchange='SEDA-FC-exchange', routing_key='insecure', body=json.dumps(data, indent=4, sort_keys=True, default=str))

        print("Data is successfully published to FC queue !!")
        connection.close()

    except:
        print("ERROR occured in rabbitmq ... !!!! ")


print("  [*] Waiting for new signals. To exit press CTRL+C")
publish()
# schedule.every(1).minutes.do(publish)
# while True:
#     schedule.run_pending()
#     time.sleep(1)