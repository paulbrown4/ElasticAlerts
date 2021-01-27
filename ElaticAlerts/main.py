#!/bin/python

import smtplib, socket
import yaml, json, requests, urllib3
from requests.auth import HTTPBasicAuth
#from dictor import dictor


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Import the alerts configuration
file = open('config/test2.yml','r')
cfg = yaml.load(file, Loader=yaml.FullLoader)
    
#def alertQuery(index_pattern,time_period,frequency, query):
def alertQuery(index_pattern, field, term, negate) :
    
    if negate == True :
        operator = "must_not"
    if negate == False :
        operator = "must"

    jquery = json.loads('{  "query": { "bool": {"' + operator + '": [{"term": {"' + field + '": "' + term + '"}}],"filter":[{"exists":{"field": "' + field + '"}}]}}}')
    headers = {'Accept': 'application/json', 'Content-type': 'application/json'}
    
    if cfg['elasticsearch']['ssl'] == True: 
        queryURL = "https://"  + cfg["elasticsearch"]["host"]  + ":" + cfg["elasticsearch"]["port"] + "/" + index_pattern + "/_search"
        try:
            response = requests.get(queryURL, auth=HTTPBasicAuth(cfg["elasticsearch"]["username"], cfg["elasticsearch"]["password"] ), verify=False, data=json.dumps(jquery), headers=headers)
        except requests.exceptions.SSLError:
            pass
    if cfg['elasticsearch']['ssl'] == False: 
        queryURL = "http://"  + cfg["elasticsearch"]["host"]  + ":" + cfg["elasticsearch"]["port"] + "/" + index_pattern + "/_search"
        try:
            response = requests.get(queryURL, data=json.dumps(jquery), headers=headers)
        except requests.exceptions.SSLError:
            pass
        
    return json.loads(response.text)
    
# Dissescts the field names. Will be used later on to print specific values.    
def getFieldNames(field) :
    if '.' not in field :
        return field
    else :
        values = field.split(".")
        field = "['" + values[0] + "']['" + values[1] + "']"
        return field

def sendEvents(host, port, username, password, message) :
    #sender = socket.getfqdn()
    
    sent_from = username
    to = [username]
    subject = 'Elastic Alert Message'
    body = message
    
    email_text = """\
From: %s
To: %s
Subject: %s

%s
""" % (sent_from, ", ".join(to), subject, body)
    
    try:
        smtpObj = smtplib.SMTP(host, port)
        smtpObj.ehlo()
        smtpObj.starttls()
        smtpObj.login(username, password)
        smtpObj.sendmail(sent_from, to, email_text)    
        smtpObj.close()     
        
        print("Successfully sent email")
    except smtplib.SMTPException :
        print("Error: unable to send email")

# This is where we check all configured alerts.
for alert in cfg['alerts'] :
    json_response = alertQuery(alert['index_pattern'],alert['field'],alert['term'],alert['negate'])
    
    for hit in json_response['hits']['hits'] :
        print(hit['_source'])
        if cfg['output']['smtp']['enabled'] :
            sendEvents(cfg['output']['smtp']['host'] , cfg['output']['smtp']['port'] , cfg['output']['smtp']['username'] , cfg['output']['smtp']['password'] , hit['_source'])
        
