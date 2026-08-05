import boto3
from src.config.index import app_config

s3_client = boto3.client("s3",
          aws_access_key_id = app_config['aws_access_key_id'],
          aws_secret_access_key = app_config['aws_secret_access_key'],
          region_name = app_config['aws_region'],
          endpoint_url="https://t3.storage.dev")

BUCKET_NAME = app_config['s3_bucket_name']