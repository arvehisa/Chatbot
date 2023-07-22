import * as cdk from 'aws-cdk-lib'; 
import { ApplicationLoadBalancedFargateService } from 'aws-cdk-lib/aws-ecs-patterns';
import { Construct } from 'constructs';
import { Vpc } from 'aws-cdk-lib/aws-ec2';
import { Cluster, ContainerImage, FargateTaskDefinition, Protocol, Secret } from 'aws-cdk-lib/aws-ecs';
import { Table, AttributeType } from 'aws-cdk-lib/aws-dynamodb';
import { Role, ServicePrincipal, ManagedPolicy } from 'aws-cdk-lib/aws-iam';
import * as sm from 'aws-cdk-lib/aws-secretsmanager';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';

export class CdkStack extends cdk.Stack { 
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const vpc = new Vpc(this, 'VPC', { maxAzs: 1 }); 

    const cluster = new Cluster(this, 'ChatbotCluster', { vpc }); 

    const openAIAPIKeySecret = sm.Secret.fromSecretAttributes(this, 'OpenAIAPIKeySecret', {secretCompleteArn:'arn:aws:secretsmanager:ap-northeast-1:618044871166:secret:OPEN_AI_API-scjYEb'});

    const taskDef = new FargateTaskDefinition(this, 'ChatbotTaskDef', {
      cpu: 1024,
      memoryLimitMiB: 3072,
    });
=
    const container = taskDef.addContainer('chatbot', {
      image: ContainerImage.fromRegistry('${{ steps.build-image.outputs.image }}'),
      secrets: {
        OPENAI_API_KEY: Secret.fromSecretsManager(openAIAPIKeySecret),
      },
    });

    container.addPortMappings({ containerPort: 8501, protocol: Protocol.TCP }); 

    const table = new Table(this, 'ChatbotTable', {
      partitionKey: { name: 'session_id', type: AttributeType.STRING },
      sortKey: { name: 'timestamp', type: AttributeType.STRING },
      tableName: 'Chatbot-cdk',
    });

    const role = new Role(this, 'ChatbotTaskRole', {
      assumedBy: new ServicePrincipal('ecs-tasks.amazonaws.com'),
    });

    role.addManagedPolicy(ManagedPolicy.fromAwsManagedPolicyName('AmazonDynamoDBFullAccess'));

    const certificate = acm.Certificate.fromCertificateArn(this, 'Certificate', 'arn:aws:acm:ap-northeast-1:618044871166:certificate/0b5a0686-eeff-472e-ba66-93f90e9c2907');

    const fargateService = new ApplicationLoadBalancedFargateService(this, 'ChatbotFargate', {
      cluster,
      taskDefinition: taskDef,
      publicLoadBalancer: true,
      serviceName: 'ChatbotService',
      desiredCount: 1,
      certificate: certificate,
      protocol: elbv2.ApplicationProtocol.HTTPS,
      redirectHTTP: true
    });

    fargateService.targetGroup.configureHealthCheck({
      path: '/health-check-path',
    });

  }
}