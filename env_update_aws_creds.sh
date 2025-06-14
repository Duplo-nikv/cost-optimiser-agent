#!/bin/bash

# Default values
TENANT="agents"
HOST="https://duplo.hackathon.duploworkshop.com/"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --tenant=*)
      TENANT="${1#*=}"
      shift
      ;;
    --host=*)
      HOST="${1#*=}"
      shift
      ;;
    --tenant)
      TENANT="$2"
      shift 2
      ;;
    --host)
      HOST="$2"
      shift 2
      ;;
    *)
      echo "Unknown parameter: $1"
      echo "Usage: $0 [--tenant=TENANT_NAME] [--host=HOST_URL]"
      echo "   or: $0 [--tenant TENANT_NAME] [--host HOST_URL]"
      exit 1
      ;;
  esac
done

echo "Using tenant: $TENANT"
echo "Using host: $HOST"

# Run duplo-jit command and capture output
output=$(duplo-jit aws --no-cache --tenant="$TENANT" --host "$HOST" --interactive)

# Extract credentials using jq
access_key=$(echo "$output" | jq -r '.AccessKeyId')
secret_key=$(echo "$output" | jq -r '.SecretAccessKey')
session_token=$(echo "$output" | jq -r '.SessionToken')

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "Creating new .env file..."
    touch .env
    # Add AWS credentials to the new file
    echo "AWS_ACCESS_KEY_ID=\"$access_key\"" >> .env
    echo "AWS_SECRET_ACCESS_KEY=\"$secret_key\"" >> .env
    echo "AWS_SESSION_TOKEN=\"$session_token\"" >> .env
    echo "New .env file created with AWS credentials"
    exit 0
fi

# Create a temporary file
temp_file=$(mktemp)

# Variables to track if we've found the AWS credentials
found_access_key=false
found_secret_key=false
found_session_token=false

# Read the current .env line by line and update existing AWS credentials
while IFS= read -r line || [ -n "$line" ]; do
    if [[ $line == AWS_ACCESS_KEY_ID=* ]]; then
        echo "AWS_ACCESS_KEY_ID=\"$access_key\"" >> "$temp_file"
        found_access_key=true
    elif [[ $line == AWS_SECRET_ACCESS_KEY=* ]]; then
        echo "AWS_SECRET_ACCESS_KEY=\"$secret_key\"" >> "$temp_file"
        found_secret_key=true
    elif [[ $line == AWS_SESSION_TOKEN=* ]]; then
        echo "AWS_SESSION_TOKEN=\"$session_token\"" >> "$temp_file"
        found_session_token=true
    else
        echo "$line" >> "$temp_file"
    fi
done < .env

# Add any missing AWS credentials
if [ "$found_access_key" = false ]; then
    echo "AWS_ACCESS_KEY_ID=\"$access_key\"" >> "$temp_file"
fi
if [ "$found_secret_key" = false ]; then
    echo "AWS_SECRET_ACCESS_KEY=\"$secret_key\"" >> "$temp_file"
fi
if [ "$found_session_token" = false ]; then
    echo "AWS_SESSION_TOKEN=\"$session_token\"" >> "$temp_file"
fi

# Replace the original file with our updated version
mv "$temp_file" .env

echo "AWS credentials updated in .env while preserving other variables"