import boto3
import json
from datetime import datetime
from io import BytesIO
from PIL import Image, ImageFilter
from botocore.client import Config

class S3Uploader:
    def __init__(self, bucket_name, aws_access_key_id=None, aws_secret_access_key=None, region_name='us-east-1'):
        # Configure the S3 client to use HTTPS and server-side encryption
        self.s3 = boto3.client('s3',
                               aws_access_key_id=aws_access_key_id,
                               aws_secret_access_key=aws_secret_access_key,
                               region_name=region_name,
                               config=Config(signature_version='s3v4'),
                               use_ssl=True)
        self.bucket_name = bucket_name

    def upload_logs(self, activity_log):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"activity_log_{timestamp}.json"
        
        json_data = json.dumps(activity_log, default=str)
        
        self.s3.put_object(Bucket=self.bucket_name,
                           Key=f"logs/{filename}",
                           Body=json_data,
                           ServerSideEncryption='AES256')  # Enable server-side encryption
        
        print(f"Uploaded encrypted activity log: {filename}")

    def upload_screenshot(self, screenshot, blur=False):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        
        img_byte_arr = BytesIO()

        if isinstance(screenshot, str):
            # If screenshot is a file path
            with Image.open(screenshot) as img:
                if blur:
                    img = img.filter(ImageFilter.GaussianBlur(radius=10))
                img.save(img_byte_arr, format='PNG')
        elif isinstance(screenshot, Image.Image):
            # If screenshot is already a PIL Image object
            if blur:
                screenshot = screenshot.filter(ImageFilter.GaussianBlur(radius=10))
            screenshot.save(img_byte_arr, format='PNG')
        else:
            raise ValueError("Screenshot must be either a file path or a PIL Image object")

        img_byte_arr.seek(0)
        
        self.s3.put_object(Bucket=self.bucket_name,
                           Key=f"screenshots/{filename}",
                           Body=img_byte_arr.getvalue(),
                           ServerSideEncryption='AES256')  # Enable server-side encryption
        
        print(f"Uploaded encrypted {'blurred ' if blur else ''}screenshot: {filename}")