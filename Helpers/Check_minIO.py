import os
from minio import Minio
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "")
BUCKET_NAME = "terceirizados"


def get_client():
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False
    )


def list_buckets(client):
    print("\n📦 Buckets disponíveis:")
    for bucket in client.list_buckets():
        print(f" - {bucket.name}")


def inspect_bucket(client, bucket_name):
    if not client.bucket_exists(bucket_name):
        print(f"❌ Bucket '{bucket_name}' não existe.")
        return

    print(f"\n📂 Objetos no bucket '{bucket_name}':\n")

    total_size = 0
    count = 0

    for obj in client.list_objects(bucket_name, recursive=True):
        count += 1
        total_size += obj.size

        print(f"Objeto: {obj.object_name}")
        print(f"  Tamanho: {obj.size / 1024:.2f} KB")
        print(f"  Última modificação: {obj.last_modified}")
        print("-" * 40)

    print(f"\n📊 Total de objetos: {count}")
    print(f"📊 Tamanho total: {total_size / (1024**2):.2f} MB")


def main():
    client = get_client()
    list_buckets(client)
    inspect_bucket(client, BUCKET_NAME)


if __name__ == "__main__":
    main()