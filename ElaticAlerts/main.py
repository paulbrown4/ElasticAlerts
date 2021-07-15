#!/usr/bin/python

import smtplib, time, logging, os, argparse, copy
import yaml, json, requests, urllib3
from requests.auth import HTTPBasicAuth
from jsonpath_rw import parse
from datetime import datetime

if not os.path.exists('/var/log/ElasticAlerts'):
    os.makedirs('/var/log/ElasticAlerts')

# Setup the logger
logging.basicConfig(filename="/var/log/ElasticAlerts/ElaticAlerts.log", 
                format='%(asctime)s %(message)s', 
                filemode='a') 
logger=logging.getLogger() 
logger.setLevel(logging.DEBUG) 

# Disable SSL certificate warnings in case self-signed certificates are being used
# It is recommended to use a valid certificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def alertQuery(index_pattern, time_period, must="", must_not="") :
    
    if must :
        must_array = ""
        for key in must :
            must_array += '{ "match": { "' + key.split(':')[0] + '": "' + key.split(':')[1] + '" }},'

        must_array = must_array[:-1]
        
    if must_not : 
        mustnot_array = ""
        for key in must_not :
            mustnot_array += '{ "match": { "' + key.split(':')[0] + '": "' + must_not.split(':')[1] + '" }},'

        mustnot_array = mustnot_array[:-1]
    
    if must_array in locals() and mustnot_array in locals() :
        jquery = json.loads('{  "query": { "bool": {"must": [' + must_array + '],"must_not": [' + mustnot_array + '] ,"filter":[{ "range": { "@timestamp":{ "gte": "now-' + time_period + '" }}}]}}}')
    elif must_array :
        jquery = json.loads('{  "query": { "bool": {"must": [' + must_array + '],"filter":[{ "range": { "@timestamp":{ "gte": "now-' + time_period + '" }}}]}}}')
    elif mustnot_array :
        jquery = json.loads('{  "query": { "bool": {"must_not": [' + mustnot_array + '],"filter":[{ "range": { "@timestamp":{ "gte": "now-' + time_period + '" }}}]}}}')
    
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
    
# Disescts the field names. Will be used later on to print specific values.    
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
    
    sent_from = username
    to = recipient
    subject = 'Elastic Alert Message'
    body = message
    
    email_text = """\
From: %s
To: %s
Subject: %s

%s
""" % (sent_from, to, subject, body)
    
    try:
        smtpObj = smtplib.SMTP(host, port)
        smtpObj.ehlo()
        smtpObj.starttls()
        smtpObj.login(username, password)
        smtpObj.sendmail(sent_from, to, email_text)    
        smtpObj.close()     
        
        logger.info("Successfully sent email to " + str(recipient))
        
        if cfg['output']['console']['enabled'] : 
            print("Successfully sent email to " + str(recipient))

    except smtplib.SMTPException :
        logger.warning("Error: unable to send email to " + str(recipient))
        
        if cfg['output']['console']['enabled'] : 
            print("Error: unable to send email to "+ str(recipient))

def main():
    logger.debug("Starting search")
    timestamp = datetime.now()
    
    # This is where we check all configured alerts.
    for alert in cfg['alerts'] :
        
        if 'must' in alert and 'must_not' in alert :
            json_response = alertQuery(alert['index_pattern'],alert['time_period'],alert['must'],alert['must_not'])
        if 'must' in alert :
            json_response = alertQuery(alert['index_pattern'],alert['time_period'],alert['must'],None)    
        if 'must_not' in alert :
            json_response = alertQuery(alert['index_pattern'],alert['time_period'],None,alert['must_not'])    
              
        docids = []
        if json_response['hits']['total']['value'] != 0 :
            for hit in json_response['hits']['hits'] :
                
                
                if hit['_id'] not in docids :
                    alertValue = str(alert['must'])
                    
                    alertOut = "Alert matched: " + str(alertValue) + "\n" + "Time: " + hit['_source']['@timestamp'] + "\n\n" + "Full message: \n\n" + json.dumps(hit['_source'], indent=2)
                    
                    if cfg['output']['log']['enabled'] :
                        logger.debug("Writing to log...")
                        logger.debug(alertOut)
                        
                    if cfg['output']['console']['enabled'] :
                        print(alertOut)
                    
                    if cfg['output']['smtp']['enabled'] :
                        sendEvents(cfg['output']['smtp']['host'] , cfg['output']['smtp']['port'] , cfg['output']['smtp']['username'], alert['recipient'], cfg['output']['smtp']['password'] , alertOut)        
    
                    docids.append(hit['_id'])

        else:
            logger.debug(timestamp.strftime("%m/%d/%y %H:%M:%S") + ": No results returned for " + alert['name'])
             
            if cfg['output']['console']['enabled'] :
                print(timestamp.strftime("%m/%d/%y %H:%M:%S") + ": No results returned for " + alert['name'])
    logger.debug("Run finished")
            
if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description='Export Elastic query results to CSV or JSON via email or local file')
    parser.add_argument('--config', dest='configfile', default='config/test2.yml')
    parser.add_argument('-E', dest='E', help="YAML configuration overrides", nargs='*', action='append')
    
    args = parser.parse_args()
        
    # Import the alerts configuration
    file = open(args.configfile,'r')
    cfg = yaml.load(file, Loader=yaml.FullLoader)
    
    if args.E :
        for override in args.E:
            ############################################################
            # Split by the delimiter, making sure to split once only
            # to prevent splitting when the delimiter appears in the value
            key, value = override[0].split("=", 1)
            
            # Break the dot-joined key into parts that form a path
            key_parts = key.split(".")
            parent_key = key_parts[0]
            
            # The last part is required to update the dictionary
            last_part = key_parts.pop()
            
            # Traverse the dictionary using the parts
            current = copy.deepcopy(cfg)
            while key_parts:
                current = current[key_parts.pop(0)]
        
            # Update the value
            current[last_part] = value
            
            cfg[parent_key] = current 
            ############################################################
        
    
    
    main()

