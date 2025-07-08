import os
from minio import Minio
from datetime import timedelta
 
class MinioClient:
    def __init__(self, endpoint, access_key, secret_key, secure=False):
        self.client = Minio(endpoint=endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
 
    def list_buckets(self):
        return self.client.list_buckets()
 
    def make_bucket(self, bucket_name):
        if not self.client.bucket_exists(bucket_name):
            return self.client.make_bucket(bucket_name=bucket_name)
        else:
            return f"Bucket {bucket_name} already exists"
    
    def upload_file(self, bucket_name, object_name, file_path):
        # object_name 是你想在 Minio 存储桶中为文件指定的名称,文件在存储桶中的标识符。
        return self.client.fput_object(bucket_name=bucket_name, object_name=object_name, file_path=file_path)
    
    def share_file(self, bucket_name, object_name, expires:float):
        return self.client.presigned_get_object(bucket_name, object_name, expires=timedelta(days=expires))
 
    