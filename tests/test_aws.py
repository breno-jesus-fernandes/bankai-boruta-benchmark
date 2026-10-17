import json
import pytest
from bankai_benchmark.aws_ecs import infrastructure,task_definition,commands,verify_hosts,launch,AMI_PARAMETER


def test_resource_geometry_and_scoped_policies():
    template=infrastructure('example','results-bucket',['subnet-a'],['sg-a']);resources=template['Resources']
    fleet=resources['Fleet']['Properties']
    assert [fleet[k] for k in ['MinSize','MaxSize','DesiredCapacity']] == ['5']*3
    assert resources['LaunchTemplate']['Properties']['LaunchTemplateData']['InstanceType'] == 'c7i.4xlarge'
    assert template['Parameters']['EcsAmi']['Default'] == AMI_PARAMETER
    statements=resources['TaskRole']['Properties']['Policies'][0]['PolicyDocument']['Statement']
    assert statements[0]['Resource'] == ['arn:aws:s3:::results-bucket/example/*','arn:aws:s3:::results-bucket/example-quality/*','arn:aws:s3:::results-bucket/example-scaling/*']
    assert not any(r['Type'] == 'AWS::S3::Bucket' for r in resources.values())
    assert 'Spot' not in json.dumps(template)


def test_digest_and_cpu_reservations():
    outputs=dict(ExecutionRole='execution',TaskRole='task',Logs='/bankai/example')
    with pytest.raises(ValueError):task_definition('example','repo:latest','us-east-1',outputs)
    definition=task_definition('example','repo@sha256:'+'a'*64,'us-east-1',outputs)
    assert definition['cpu'] == '16384' and definition['memory'] == '28672'
    assert definition['runtimePlatform']['cpuArchitecture'] == 'X86_64'
    assert definition['containerDefinitions'][0]['cpu'] == 16384
    assert len(commands('example','bucket','us-east-1')) == 5


def test_mocked_five_host_launch():
    class ECS:
        requests=[]
        def run_task(self,**kwargs):
            self.requests.append(kwargs)
            return dict(tasks=[dict(taskArn=f'task{len(self.requests)}')])
        def describe_tasks(self,**kwargs):
            return dict(tasks=[dict(taskArn=t,lastStatus='RUNNING',containerInstanceArn='host'+t) for t in kwargs['tasks']])
        def describe_container_instances(self,**kwargs):
            return dict(containerInstances=[dict(containerInstanceArn=h,ec2InstanceId='ec2-'+h) for h in kwargs['containerInstances']])
    class S3:
        def put_object(self,**kwargs):self.request=kwargs
    ecs,s3=ECS(),S3();outputs=dict(Cluster='cluster',CapacityProvider='capacity',Logs='logs')
    result=launch(ecs,s3,outputs,dict(task_definition='definition'),'example','bucket','us-east-1')
    assert len(set(result['instances'])) == 5 and len(result['tasks']) == 5
    for request in ecs.requests:
        assert request['placementConstraints'] == [dict(type='distinctInstance'),dict(type='memberOf',expression='attribute:ecs.instance-type == c7i.4xlarge')]
    assert json.loads(s3.request['Body'])['tasks'] == result['tasks']
    with pytest.raises(RuntimeError):verify_hosts([dict(lastStatus='RUNNING',containerInstanceArn='same')]*5)
