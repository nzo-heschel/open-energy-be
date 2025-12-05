import json
import urllib.request
POST_URL = "https://apim-api.noga-iso.co.il/"
def noga_post(path, from_date, to_date, token):
    hdr = {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'Ocp-Apim-Subscription-Key': token
    }
    data = json.dumps({"fromDate": from_date, "toDate": to_date})
    req = urllib.request.Request(POST_URL + path, headers=hdr, data=bytes(data.encode("utf-8")))
    req.get_method = lambda: 'POST'
    response = urllib.request.urlopen(req)
    return json.loads(response.read().decode("utf-8"))
jsons = noga_post("PRODUCTIONMIX/PRODMIXAPI/v1", "01-04-2025", "31-12-2025", "7b397cafa75b4a00848542829a588dac")
energy = jsons["energy"]
values = []
for day_item in energy:
    date = day_item['date']
    time_items = day_item[list(day_item.keys())[1]]
    for time_item in time_items:
        value = {'date': date}
        for k, v in time_item.items():
            value[k] = v
        values.append(value)
for value in values:
    print(value)
print("Extracted {} values".format(len(values)))
import json
import urllib.request
POST_URL = "https://apim-api.noga-iso.co.il/"
def noga_post(path, from_date, to_date, token):
    hdr = {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'Ocp-Apim-Subscription-Key': token
    }
    data = json.dumps({"fromDate": from_date, "toDate": to_date})
    req = urllib.request.Request(POST_URL + path, headers=hdr, data=bytes(data.encode("utf-8")))
    req.get_method = lambda: 'POST'
    response = urllib.request.urlopen(req)
    return json.loads(response.read().decode("utf-8"))
jsons = noga_post("PRODUCTIONMIX/PRODMIXAPI/v1", "01-04-2025", "31-12-2025", "7b397cafa75b4a00848542829a588dac")
energy = jsons["energy"]
values = []
for day_item in energy:
    date = day_item['date']
    time_items = day_item[list(day_item.keys())[1]]
    for time_item in time_items:
        value = {'date': date}
        for k, v in time_item.items():
            value[k] = v
        values.append(value)
for value in values:
    print(value)
print("Extracted {} values".format(len(values)))
