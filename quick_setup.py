import argparse
import logging
import os
from pathlib import Path

import boto3
import botocore
import tomli  # for reading toml files
from dotenv import find_dotenv, load_dotenv

# Force reload of environment variables
load_dotenv(find_dotenv(), override=True)

# Set up argument parser
parser = argparse.ArgumentParser(description="Setup S3 bucket")
parser.add_argument("--debug", action="store_true", help="Enable debug logging")
parser.add_argument("--quiet", action="store_true", help="Only show warning and error logs")
args = parser.parse_args()

# Configure logging based on command line arguments
LOGGER = logging.getLogger(__name__)
match (args.debug, args.quiet):
    case (True, _):
        LOGGER.setLevel(logging.DEBUG)
    case (_, True):
        LOGGER.setLevel(logging.WARNING)
    case _:
        LOGGER.setLevel(logging.INFO)

# Add console handler with formatting
console_handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)
LOGGER.addHandler(console_handler)

# Load configuration from morphik.toml
config_path = Path("morphik.toml")
with open(config_path, "rb") as f:
    CONFIG = tomli.load(f)
    LOGGER.info("Loaded configuration from morphik.toml")

# Extract configuration values
STORAGE_PROVIDER = CONFIG["storage"]["provider"]
DATABASE_PROVIDER = CONFIG["database"]["provider"]

# Extract storage-specific configuration
if STORAGE_PROVIDER == "aws-s3":
    DEFAULT_REGION = CONFIG["storage"]["region"]
    DEFAULT_BUCKET_NAME = CONFIG["storage"]["bucket_name"]
else:
    DEFAULT_REGION = None
    DEFAULT_BUCKET_NAME = None


def create_s3_bucket(bucket_name, region=DEFAULT_REGION):
    """Set up S3 bucket."""
    # Clear any existing AWS credentials from environment
    boto3.Session().resource("s3").meta.client.close()

    aws_access_key = os.getenv("AWS_ACCESS_KEY")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    region = os.getenv("AWS_REGION") or region

    if not aws_access_key or not aws_secret_key:
        LOGGER.error("AWS credentials not found in environment variables.")
        return

    LOGGER.debug("Successfully retrieved AWS credentials and region.")
    # Create new session with explicit credentials
    session = boto3.Session(
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=region,
    )

    s3_client = session.client("s3")
    LOGGER.debug("Successfully created S3 client.")

    if bucket_exists(s3_client, bucket_name):
        LOGGER.info(f"Bucket with name {bucket_name} already exists")
        return

    if region == "us-east-1":
        s3_client.create_bucket(Bucket=bucket_name)
    else:
        s3_client.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={"LocationConstraint": region})

    LOGGER.debug(f"Bucket {bucket_name} created successfully in {region} region.")


def bucket_exists(s3_client, bucket_name):
    """Check if an S3 bucket exists."""
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        return True
    except botocore.exceptions.ClientError as e:
        error_code = int(e.response["Error"]["Code"])
        if error_code in [404, 403]:
            return False
        # raise e


def setup():
    # Setup S3 if configured
    if STORAGE_PROVIDER == "aws-s3":
        LOGGER.info("Setting up S3 bucket...")
        create_s3_bucket(DEFAULT_BUCKET_NAME, DEFAULT_REGION)
        LOGGER.info("S3 bucket setup completed.")

    # Setup database based on provider
    if DATABASE_PROVIDER != "postgres":
        LOGGER.error(f"Unsupported database provider: {DATABASE_PROVIDER}")
        raise ValueError(f"Unsupported database provider: {DATABASE_PROVIDER}")

    LOGGER.info("Postgres is setup on database initialization - nothing to do here!")

    LOGGER.info("Setup completed successfully. Feel free to start the server now!")


if __name__ == "__main__":
    setup()
