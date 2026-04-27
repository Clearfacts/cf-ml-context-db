import gzip

import os
import re
import boto3
import botocore
import shutil
import json


import base64

class JupyterPdf(object):
    def __init__(self, storage_key):
        self.pdf = load_s3_document(storage_key)
        self.pdf = base64.b64encode(self.pdf).decode('utf-8')

    def _repr_html_(self):        
        pdf_display = f'<embed src="data:application/pdf;base64,{self.pdf}" width="800" height="1200" type="application/pdf">'
        return pdf_display


def ifnull(*args):
    for arg in args:
        if arg is not None:
            return arg
    return None

def convert_to_snake_case(name):
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()


def http_closer(http_response, **kwargs):
    print("http_closer")
    if http_response:
        http_response.close()



def does_s3_key_exists(bucket, key):
    s3 = boto3.resource('s3')
    try:
        s3.Object(bucket, key).load()
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == "404":
            # The object does not exist.
            return False
        else:
            # Something else has gone wrong.
            raise
    else:
        return True


def load_s3_object(object_key, bucket_name='cf-queue-prod'):
    s3 = boto3.resource('s3')
    if does_s3_key_exists(bucket_name, object_key):
        obj = s3.Object(bucket_name, object_key)
        return obj.get()['Body'].read()
    else:
        return None


def upload_file(file_name, bucket, object_key):
    # Upload the file
    s3_client = boto3.client('s3')
    s3_client.upload_file(file_name, bucket, object_key)


def load_s3_document(storage_key, bucket_name='cf-nodes-prod'):
    s3 = boto3.resource('s3')
    item_name = f"{storage_key}"
    if does_s3_key_exists(bucket_name, item_name):
        obj = s3.Object(bucket_name, item_name)
        return obj.get()['Body'].read()
    else:
        return None


def save_s3_document(filename, storage_key, doc_type="pdfa", bucket_name='cf-queue-prod'):
    data = load_s3_document(storage_key, doc_type, bucket_name)
    if data:
        with open(filename, 'wb') as file:
            file.write(data)
            return True
    return False


def load_s3_txt_document(storage_key, doc_type="txt-layout", bucket_name='cf-queue-prod'):
    return load_s3_document(storage_key, doc_type, bucket_name).decode('windows-1252')


def load_json_file(filename):
    with open(filename) as f:
        data = json.loads(f.read())
    return data


def write_json_file(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f)


def create_folder_if_not_exists(folder):
    if not os.path.exists(folder):
        os.makedirs(folder)


def remove_folder(folder):
    shutil.rmtree(folder)


class Struct:
    def __init__(self, **entries):
        """
            Class used to convert dictionaries to objects.
            e.g.:
            ```
                s = Struct(**{"a":1,"b":"test"})
                print(s.a, s.b)
            ```
        """
        self.__dict__.update(entries)


def to_objects(list_of_dictionaries):
    """ creates a list of Struct given a list of dictionaries.  """
    return [Struct(**d) for d in list_of_dictionaries]


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

        
def coalesce(*values):
    """Return the first non-None value or None if all values are None"""
    return next((v for v in values if v is not None), None)        
        

def load_gz_file(filename, is_json=True):
    with gzip.open(filename, 'rb') as file:
        data = file.read()
        if is_json:
            data = json.loads(data)
    return data

