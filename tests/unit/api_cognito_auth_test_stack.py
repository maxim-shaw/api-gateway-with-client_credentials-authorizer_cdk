import aws_cdk as core
import aws_cdk.assertions as assertions

from cdk_stacks.api_cognito_auth_stack import GuardianApiCognitoStack

# example tests. To run these tests, uncomment this file along with the example
# resource in cdk_test/cdk_test_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = GuardianApiCognitoStack(app, "cdk-test")
    template = assertions.Template.from_stack(stack)
