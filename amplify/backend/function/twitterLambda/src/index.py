import tweepy
import boto3
import json
import tempfile
from botocore.exceptions import ClientError

region_name = "us-east-2"
session = boto3.session.Session()
client = session.client(service_name='secretsmanager', region_name=region_name)

def get_secret(secret_name):
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        secret = get_secret_value_response['SecretString']
        return json.loads(secret)
    except ClientError as e:
        print(f"Error retrieving secret {secret_name}: {str(e)}")
        raise e
    
def get_forbidden_words():
    secret_name = "ForbiddenWordsList"
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        secret = get_secret_value_response['SecretString']
        secret_dict = json.loads(secret)
        forbidden_words = secret_dict.get('forbiddenWords', [])
        return forbidden_words
    except ClientError as e:
        print(f"Error retrieving secret {secret_name}: {str(e)}")
        raise e

def handler(event, context):
    print('received event:')
    print(event)
    secrets = get_secret("TwitterAPICredentials")
    api_key = secrets.get('api_key')
    api_key_secret = secrets.get('api_key_secret')
    access_token = secrets.get('access_token')
    access_token_secret = secrets.get('access_token_secret')
    client_V2 = tweepy.Client(consumer_key=api_key, consumer_secret=api_key_secret, access_token=access_token, access_token_secret=access_token_secret)
    client_v1 = tweepy.API(tweepy.OAuth1UserHandler(consumer_key=api_key, consumer_secret=api_key_secret, access_token=access_token, access_token_secret=access_token_secret))
    
    if 'Records' in event and 's3' in event['Records'][0]:

        bucket_name = event['Records'][0]['s3']['bucket']['name']
        object_key = event['Records'][0]['s3']['object']['key']
        s3_client = boto3.client('s3')

        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            try:
                s3_client.download_file(bucket_name, object_key, tmp_file.name)
            except ClientError as e:
                print(f"Error downloading file from S3: {str(e)}")
                raise e

        try:
            response = s3_client.head_object(Bucket=bucket_name, Key=object_key)
            tweet_text = response['Metadata'].get('tweet-text', '')
        except ClientError as e:
            print(f"Error retrieving metadata: {str(e)}")
            tweet_text = ''
        
        try:
            s3_client.delete_object(Bucket=bucket_name, Key=object_key)
        except ClientError as e:
            print(f"Error occurred while deleting object from S3: {str(e)}")
            raise e

        mediaID = [client_v1.simple_upload(tmp_file.name).media_id]
        response = client_V2.create_tweet(media_ids = mediaID, text=tweet_text)

        return {
            'statusCode': 200,
            'body': json.dumps(response)
        }
    
    else:
        method = event['httpMethod']
        path_parameters = event['pathParameters']
        tweetID = path_parameters['tweetID']
        
        forbidden_content = get_forbidden_words()

        def is_content_allowed(content):
            content_lower = content.lower()
            return not any(forbidden in content_lower for forbidden in forbidden_content)

        if method == 'POST':
            body = json.loads(event['body'])
            tweet = body.get('message')

            if tweetID == 'text':
                try:
                    print(tweet)
                    if not is_content_allowed(tweet):
                        print("Tweet contains forbidden content.")
                        raise ValueError("Tweet contains forbidden content.")
                    
                    response = client_V2.create_tweet(text = tweet)
                    return {
                        'statusCode': 200,
                        'headers': {
                            'Access-Control-Allow-Headers': '*',
                            'Access-Control-Allow-Origin': '*',
                            'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
                        },
                        'body': json.dumps({'message': 'Tweet sent successfully!'})
                    }
                except ValueError as ve:
                    return {
                        'statusCode': 200,
                        'headers': {
                            'Access-Control-Allow-Headers': '*',
                            'Access-Control-Allow-Origin': '*',
                            'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
                        },
                        'body': json.dumps({'error': str(ve)})
                    }
                except tweepy.errors.Forbidden as e:
                    return {
                        'statusCode': 200,
                        'headers': {
                            'Access-Control-Allow-Headers': '*',
                            'Access-Control-Allow-Origin': '*',
                            'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
                        },
                        'body': json.dumps({'error': 'You are not allowed to create a Tweet with duplicate content.'})
                    }
                except Exception as e:
                    return {
                        'statusCode': 200,
                        'headers': {
                            'Access-Control-Allow-Headers': '*',
                            'Access-Control-Allow-Origin': '*',
                            'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
                        },
                        'body': json.dumps({'error': str(e)})
                    }
            
            elif tweetID == 'getUploadLink':
                s3 = boto3.client('s3')
                bucket_name = 'tweetimagebucket'
                object_name = event['queryStringParameters']['objectName']
                content_type = event['queryStringParameters']['contentType']
                
                try:
                    print(tweet)
                    if not is_content_allowed(tweet):
                        print("Tweet contains forbidden content.")
                        raise ValueError("Tweet contains forbidden content.")

                    presigned_url = s3.generate_presigned_url('put_object', Params={'Bucket': bucket_name, 'Key': object_name, 'ContentType': content_type, 'Metadata': {'tweet-text': tweet}}, ExpiresIn=3600)

                    return {
                        'statusCode': 200,
                        'headers': {
                            'Access-Control-Allow-Headers': '*',
                            'Access-Control-Allow-Origin': '*',
                            'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
                        },
                        'body': json.dumps({'url': presigned_url})
                    }
                except ValueError as ve:
                    return {
                        'statusCode': 200,
                        'headers': {
                            'Access-Control-Allow-Headers': '*',
                            'Access-Control-Allow-Origin': '*',
                            'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
                        },
                        'body': json.dumps({'error': str(ve)})
                    }