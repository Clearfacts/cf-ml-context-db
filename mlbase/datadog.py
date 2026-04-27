
import requests
import json

from mlbase import config


def run_datadog_query(config_file, query, start_time, end_time):
    params = config.config(config_file, section="datadog" )
    
    result = []
    url = params['url']
    headers = {
        "Content-Type": "application/json",
        "Accept": "*/*",
        "DD-API-KEY": params["apikey"],
        "DD-APPLICATION-KEY": params["applicationkey"]
    }
    # Adding empty header as parameters are being sent in payload
    payload = {
        "filter": {
             "from": start_time,
             "to": end_time,
             "query": query
        }
    }
    r = requests.post(url, data=json.dumps(payload), headers=headers)
    data = r.json()
    if "data" not in data:
        print(data)
        return None
    result.extend(data["data"])
    
    # get all pages
    while "links" in data and "next" in data["links"]:
        r = requests.get(data["links"]['next'], headers=headers)
        data = r.json()
        result.extend(data["data"])
    
    return result