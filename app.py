#!/usr/bin/env python3
import os

import aws_cdk as cdk

from cdk_stacks.api_cognito_auth_stack import GuardianApiCognitoStack

app = cdk.App()
GuardianApiCognitoStack(app, "GuardianApiCognitoAuthStack")

app.synth()
