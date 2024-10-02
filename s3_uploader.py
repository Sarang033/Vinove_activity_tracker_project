import boto3
import json
from datetime import datetime
from io import BytesIO

class S3Uploader:
    def __init__(self, bucket_name, aws_access_key_id=None, aws_secret_access_key=None, region_name='us-east-1'):
        self.s3 = boto3.client('s3',
                               aws_access_key_id=aws_access_key_id,
                               aws_secret_access_key=aws_secret_access_key,
                               region_name=region_name)
        self.bucket_name = bucket_name

    def upload_logs(self, activity_log):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"activity_log_{timestamp}.json"
        
        json_data = json.dumps(activity_log, default=str)
        
        self.s3.put_object(Bucket=self.bucket_name,
                           Key=f"logs/{filename}",
                           Body=json_data)
        
        print(f"Uploaded activity log: {filename}")

    def upload_screenshot(self, screenshot):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        
        img_byte_arr = BytesIO()
        screenshot.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        
        self.s3.put_object(Bucket=self.bucket_name,
                           Key=f"screenshots/{filename}",
                           Body=img_byte_arr)
        
        print(f"Uploaded screenshot: {filename}")