#!/bin/python

import smtplib, time
import yaml, json, requests, urllib3
from requests.auth import HTTPBasicAuth
from jsonpath_rw import parse
#from dictor import dictor

# Disable SSL certificate warnings in case self-signed certificates are being used
# It is recommended to use a valid certificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Import the alerts configuration
file = open('config/test.yml','r')
cfg = yaml.load(file, Loader=yaml.FullLoader)
    
#def alertQuery(index_pattern,time_period,frequency, query):
def alertQuery(index_pattern, field, term,time_period, negate) :
    
    if negate == True :
        operator = "must_not"
    if negate == False :
        operator = "must"

    jquery = json.loads('{  "query": { "bool": {"' + operator + '": [{"match": {"' + field + '": "' + term + '"}}],"filter":[{"exists":{ "field": "' + field + '" }},{ "range": { "@timestamp":{ "gte": "now-' + time_period + '" }}}]}}}')
    headers = {'Accept': 'application/json', 'Content-type': 'application/json'}
    #print(jquery)
    
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
        parsedField = ""
        values = field.split(".")
        for v in values :
            parsedField += "'" + v + "'"
        
        return parsedField
            
def sendEvents(host, port, username, recipient, password, message) :
    #sender = socket.getfqdn()
    
    sent_from = username
    to = [recipient]
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

def main():
    # This is where we check all configured alerts.
    for alert in cfg['alerts'] :
        json_response = alertQuery(alert['index_pattern'],alert['field'],alert['term'],alert['time_period'], alert['negate'])
        #print(json.dumps(json_response, indent=4))
        
        for hit in json_response['hits']['hits'] :
            #print(json.dumps(hit['_index'], indent=2))
            alertValue = parse(alert['field']).find(hit['_source'])
            
            alertOut = "Alert matched: " + str(alertValue[0].value) + "\n" + "Time: " + hit['_source']['@timestamp'] + "\n\n" + "Full message: \n\n" + json.dumps(hit['_source'], indent=2)
            #alertOut = "Alert matched: " + str(alertValue[0].value) + "\n" + "Time: " + hit['_source']['@timestamp'] + "\n\n" + "Full message: \n\n" + json.dumps(hit['_source'])
            
            if cfg['output']['console']['enabled'] :
                print(alertOut)
            
            if cfg['output']['smtp']['enabled'] :
                sendEvents(cfg['output']['smtp']['host'] , cfg['output']['smtp']['port'] , cfg['output']['smtp']['username'], alert['recipient'], cfg['output']['smtp']['password'] , alertOut)        


if __name__ == "__main__":
    while True:
        main()
        time.sleep(int(cfg['defaults']['alert_period']))
        
    