from aws_cdk import (
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_lambda,
    aws_cognito as cognito,
    aws_apigateway as apigateway,
    Stack,
    RemovalPolicy,
)
from constructs import Construct

class GuardianApiCognitoStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create VPC for secure resources deployment
        guardian_vpc = ec2.Vpc(
            self,
            "GuardianVPC",
            ip_addresses=ec2.IpAddresses.cidr("10.2.0.0/16"),
            max_azs=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="GuardianSubnetPublic",
                    cidr_mask=24,
                    subnet_type=ec2.SubnetType.PUBLIC
                ),
                ec2.SubnetConfiguration(
                    name="GuardianSubnetPrivate",
                    cidr_mask=24,
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                ),
            ]
        )

        # Cognito UserPool for the authentication application
        guardian_user_pool = cognito.UserPool(
            self, "GuardianPool", removal_policy=RemovalPolicy.DESTROY
        )

        # Cognito default authentication domain with cutom prefix "guardian"
        cognito.UserPoolDomain(
            self,
            "GuardianUserPoolDomain",
            user_pool=guardian_user_pool,
            cognito_domain=cognito.CognitoDomainOptions(domain_prefix="guardian"),
        )

        # Create a custom scope for the client_credentials grant. 
        # For instance to only read data
        guardian_readonly_scope = cognito.ResourceServerScope(
            scope_name="guardian.read",
            scope_description="Scope to read data only",
        )

        # Cognito resource server for custom authentication scopes for "client_credentilas"
        # authentication grant type
        guardian_cognito_resource_server = guardian_user_pool.add_resource_server(
            "GuardianCognitoResourceServer",
            user_pool_resource_server_name="GuardianCognitoResourceServer",
            identifier="guardian-cognito-resource-server",
            scopes=[guardian_readonly_scope],
        )

        # The cognito application client that provides cleint_credentials grant configuration
        guardian_user_pool.add_client(
            "GuardianAppClient",
            auth_flows=cognito.AuthFlow(user_srp=True),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(client_credentials=True),
                scopes=[
                    cognito.OAuthScope.resource_server(
                        guardian_cognito_resource_server,
                        guardian_readonly_scope
                    )
                ],
            ),
            generate_secret=True,
            user_pool_client_name="GuardianAppClient",
        )

        # Cognito autorizer for API resources
        guardian_autorizer = apigateway.CognitoUserPoolsAuthorizer(
            self,
            "GuardianAPIAuthorizer",
            cognito_user_pools=[guardian_user_pool],
            authorizer_name="GuardianAPIAuthorizer",
        )


        # Add a access/execution policy to a lambda function 
        guardian_lambda_role = iam.Role(
            self,
            "GuardianLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaVPCAccessExecutionRole"
                )
            ]
        )

        # Gateway API backend lambda that retrievs data for the response
        guardian_api_backend_lambda = aws_lambda.Function(
            self,
            "GuardianReadLambda",
            handler="api_read_lambda.handler",
            vpc=guardian_vpc,
            runtime=aws_lambda.Runtime.PYTHON_3_9,
            code=aws_lambda.Code.from_asset("./cdk_stacks/lambda"),
            role=guardian_lambda_role,
        )


        # Create Guardian API and access for client calls
        guardian_api = apigateway.RestApi(
            self,
            "GuardianApiGatewayWithCors",
            description="client_credentials grant authorization for Guardian API Gateway endpoint access",
            rest_api_name="GuardianAPI",
            deploy=False
        )

        # Gateway API resourse "galaxy" with GET method
        guardian_endpoint = guardian_api.root.add_resource(
            "galaxy",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_methods=["GET", "OPTIONS"], 
                allow_origins=apigateway.Cors.ALL_ORIGINS
            ),
        )

         # Create an integration between API endpoint and Lambda backend
        guardian_endpoint_lambda_integration = apigateway.LambdaIntegration(
            guardian_api_backend_lambda,
            proxy=True,
            integration_responses=[
                apigateway.IntegrationResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": "'*'"
                    },
                )
            ],
        )

         # Add the GET method for the DynamoDB database enpoint entry
        guardian_endpoint.add_method(
            "GET",
            guardian_endpoint_lambda_integration,
            authorizer=guardian_autorizer,
            authorization_scopes=[
                f"{guardian_cognito_resource_server.user_pool_resource_server_id}/{guardian_readonly_scope.scope_name}"
            ],
            authorization_type=apigateway.AuthorizationType.COGNITO,
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True
                    },
                )
            ],
        )

        # Deploy API Gateway stages
        guardian_api_deployment = apigateway.Deployment(self, "GuardianAPIGWDeployment", api=guardian_api)
        stages = ["dev", "prod"]
        for s in stages:
            apigateway.Stage(self, s + "_stage", deployment=guardian_api_deployment, stage_name=s)

