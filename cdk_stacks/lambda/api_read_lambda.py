def handler(event, context):
    message = "Galaxy responded on a call from the lambda function 'api_read_lambda'"

    return {
        "statusCode": 200, 
        "body": message 
    }
