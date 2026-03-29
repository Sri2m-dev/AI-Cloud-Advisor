import boto3
import pandas as pd
from io import BytesIO

def load_cur_from_s3(bucket, key):
    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=bucket, Key=key)
    data = obj["Body"].read()
    df = pd.read_csv(BytesIO(data))
    return df
