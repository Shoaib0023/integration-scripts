import pika
import json
import dateutil.parser
import schedule
import time
import datetime
import requests
import pytz
from urllib.parse import urlparse 
from os.path import splitext
import uuid
import base64
import strgen
import string
import random 
import urllib.request as urllib


tz = pytz.timezone("Europe/Amsterdam")
last_executed_datetime = datetime.datetime.now(tz=tz)


def filter_category(cat):
    cat = cat.lstrip()
    filter_cat = []

    # Case 1: When there is a backslash between category name
    if '/' in cat:
        for cat_split in cat.split('/'):
            cat_split = cat_split.lstrip()
            if not cat_split.isupper():
            	cat_split = cat_split.capitalize()
            
            filter_cat.append(cat_split)

        return '-'.join(filter_cat)


    # Case 3: When there is already a hyphen in name ex. Bouw- en sloopafval
    elif '-' in cat:
    	return cat


    # Case 2: When there is a space between category names 
    else:
        for cat_split in cat.split(' '):
            cat_split = cat_split.lstrip()
            if not cat_split.isupper():
            	cat_split = cat_split.capitalize()
            
            filter_cat.append(cat_split)

        return ' '.join(filter_cat)



def checkFacilitatorChange():
    global last_executed_datetime

    year = last_executed_datetime.year
    month = last_executed_datetime.month
    day = last_executed_datetime.day
    hour = last_executed_datetime.hour
    minute = last_executed_datetime.minute
    second = last_executed_datetime.second
    startDate = f'{year}-{month}-{day} {hour}:{minute}:{second}'

    now = datetime.datetime.now(tz=tz)
    year = now.year
    month = now.month
    day = now.day
    hour = now.hour
    minute = now.minute
    second = now.second

    endDate = f'{year}-{month}-{day} {hour}:{minute}:{second}'
    print(startDate)
    print(endDate)

    SEDA_API = 'http://seda-backend-api-nodeport:8080/signals/v1/public'
    MB_API = 'https://admindev.haagsebeheerder.nl/index.php/api/cronapi'
    IMAGE_URL = "https://admindev.haagsebeheerder.nl/uploadimages/reportedIssue/"

    payload = {'startDate': startDate  , 'endDate': endDate}

    try:
        response = requests.post(MB_API, json=payload)                             # api to capture the updates in MB
        print("Updates: ", response.status_code)
        print(len(response.json()["data"]))

        objects = response.json()["data"]
        for obj in objects:
            # print(obj)
            if "sedaId" in obj:
                seda_id = obj["sedaId"]

            else:
                mb_signal_id = obj["_id"]
                response = requests.get(f'{SEDA_API}/idmapping/{mb_signal_id}')    # api call to get the seda_id from idmapping table
                if response.status_code == 200:
                    seda_id = response.json()["seda_signal_id"]
                else:
                    print("Seda id not found ....")
                    continue

            print(seda_id)        
            if seda_id == '':
                print("Seda Id is empty")
                continue

            dept_mapping = {"HVB": "24", "HWB": "25", "Milieubeheer": "22", "Waterbeheersing": "26", "Handhavingsorganisatie": "27", "HMS": "28"}

            res_seda = requests.get(f'{SEDA_API}/signals/{seda_id}')            # api call to get the signal with id as seda_id
            if res_seda.status_code == 200:
                signal = res_seda.json()

                if signal["text"] != obj["description"]:
                    payload = {
                        "text": obj["description"],
                        "updated_by": "MB Desc"
                    }
                    
                    response = requests.put(f"{SEDA_API}/signals/{seda_id}", json=payload)              # to update the description
                    if response.status_code == 200:
                        print("Report Description is updated !!")
                    else:
                        print("Report Description is not updated !!")


                cat1 = filter_category(obj["category"])
                cat2 = filter_category(obj["sub_category"])
                cat3 = filter_category(obj["sub_category1"])
                cat4 = filter_category(obj["sub_category2"])
                
                update_category = False
                if signal["category"]["category_level_name1"] != obj["category"]:
                    update_category = True
                if signal["category"]["category_level_name2"] != obj["sub_category"]:
                    update_category = True
                if signal["category"]["category_level_name3"] != obj["sub_category1"]:
                    update_category = True
                if signal["category"]["category_level_name4"] != obj["sub_category2"]:
                    update_category = True

                if cat4:
                    category_url = f"{SEDA_API}/terms/categories/{cat1}/{cat2}/{cat3}/{cat4}"      # get the category
                else:
                    category_url = f"{SEDA_API}/terms/categories/{cat1}/{cat2}/{cat3}"             # get the category

                print("Category changed : ", update_category)
                print("Category Url : ", category_url)

                if update_category:
                    payload =  {
                                "category" : { "category_url": category_url },
                                "updated_by": "MB Category"  
                                }

                    response = requests.put(f"{SEDA_API}/signals/{seda_id}", json=payload)              # to update the category 
                    if response.status_code == 200:
                        print("Report Category is updated !!")
                    
                    else:
                        category_url = f'{SEDA_API}/terms/categories/Other/Other/Other'
                        payload =  {
                                "category" : { "category_url": category_url },
                                "updated_by": "MB Category"  
                                }

                        response = requests.put(f"{SEDA_API}/signals/{seda_id}", json=payload) 
                        print("Category Not Found so updated to Other !!")


            #? Checks if report Object is updated
            # if obj["status"] == "IN BEHANDELING":                
                #! TODO

            #? Checks if report is closed
            if obj["status"] == "AFGEROND":
                if "issue_image_finish" in obj:
                    url = IMAGE_URL + obj["issue_image_finish"]

                    if "sedaId" in obj:
                        payload = {
                            "seda_signal_id" : obj["sedaId"],
                            "mb_signal_id": obj["_id"]
                        }

                        path = urlparse(url).path
                        ext = splitext(path)[1]
                        # print("Ext : ", ext)
                        img = urllib.urlopen(url)
                        imgHeaders = img.headers
                        # print(imgHeaders)
                        name = str(uuid.uuid4()) + ext

                        files = {'issue_final_image': (name, img.read(), img.headers["Content-Type"])}

                        response = requests.post(f'{SEDA_API}/idmapping/', data=payload, files=files)          # uploading issue final image in SEDA 
                        if response.status_code == 201:
                            print("Final Issue image is Uploaded !")
                        else:
                            print("Final Issue image is not Uploaded !")
 

                    else:
                        mb_signal_id = obj["_id"]
                        payload = {
                            "mb_signal_id": mb_signal_id,
                        }

                        path = urlparse(url).path
                        ext = splitext(path)[1]
                        # print("Ext : ", ext)
                        img = urllib.urlopen(url)
                        imgHeaders = img.headers
                        # print(imgHeaders)

                        name = str(uuid.uuid4()) + ext
                        files = {'issue_final_image': (name, img.read(), img.headers["Content-Type"])}

                        response = requests.put(f'{SEDA_API}/idmapping/{seda_id}', data=payload, files=files)      # uploading issue final image in SEDA 
                        if response.status_code == 200:
                            print("Final Issue image is Uploaded !")
                        else:
                            print("Final Issue image is not Uploaded !")

                
                payload = {
                    "status": {
                        "state": "o",
                        "state_display": "AFGEHANDELD",
                        "text": obj["issue_desc"] if "issue_desc" in obj else "Melding is afgehandeld"
                    },
                    "updated_by": "MB Closed"
                }

                response = requests.put(f'{SEDA_API}/signals/{seda_id}', json=payload)               # changed status to closed 
                print(response.status_code)
                if response.status_code == 200:
                    print("Report is closed in SEDA")


            #? Checks if report is routed
            if obj["status"] == "GEROUTEERD":
                routed_to = obj["routed_to"]
                payload = {
                    "directing_departments" : [{
                        "id": dept_mapping[routed_to]
                    }],
                    "updated_by": "MB Dept"
                }

                response = requests.put(f'{SEDA_API}/signals/{seda_id}', json=payload)                # update department in Seda 
                print("Report routed status : ", response.status_code)

                if response.status_code == 200:
                    print("Report Department is updated in SEDA")
                else:
                    print(response.json())


    except Exception as error:
        print("Some error occured : ", error)


    last_executed_datetime = now
    print("---------------------------------------------------")
    print("  [*] Waiting for some change in Facilitator. To exit press CTRL+C")


print("  [*] Waiting for some change in Facilitator. To exit press CTRL+C")
checkFacilitatorChange()
# schedule.every(1).minute.do(checkFacilitatorChange)
# while True:
#     schedule.run_pending()
#     time.sleep(1)