"""Read-only resource/billing audit and S3 integrity check for the completed campaign."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',default='bankai');parser.add_argument('--archive',required=True)
    parser.add_argument('--bucket',default='bankai-benchmark-bootstrap-results-ku2wdx1kzzqb')
    parser.add_argument('--refresh-billing',action='store_true',help='Refresh the billable Cost Explorer query instead of using a matching cached period')
    args=parser.parse_args();root=Path(args.archive);output=root/'aws';output.mkdir(parents=True,exist_ok=True)
    now=datetime.now(timezone.utc)
    print('Audit UTC date:',now.isoformat(),flush=True)
    session=boto3.Session(profile_name=args.profile,region_name='us-east-1')
    config=Config(retries={'total_max_attempts':3,'mode':'standard'},connect_timeout=5,read_timeout=20)
    s3=session.client('s3',config=config)
    integrity=[]
    for suite in ('quality','scaling'):
        prefix=f'pilot-20261017-{suite}/'
        for page in s3.get_paginator('list_objects_v2').paginate(Bucket=args.bucket,Prefix=prefix):
            for obj in page.get('Contents',[]):
                key=obj['Key']
                if not key.endswith('.json'):continue
                target=root/suite/'input'/key
                if '..' in Path(key).parts or Path(key).is_absolute():raise ValueError('Unsafe S3 key')
                if not target.exists():
                    target.parent.mkdir(parents=True,exist_ok=True)
                    s3.download_file(args.bucket,key,str(target))
                raw=target.read_bytes();etag=obj['ETag'].strip('"')
                if '-' not in etag and hashlib.md5(raw).hexdigest()!=etag:
                    raise ValueError(f'Archive bytes differ from S3: {key}')
                integrity.append(dict(path=str(target.relative_to(root)),s3_key=key,
                    s3_etag=etag,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)))
    report=dict(verified_at=now.isoformat(),resource_scope=['us-east-1','sa-east-1'],regions={},
                archive_objects=len(integrity),s3_integrity='All downloaded single-part objects match S3 ETags')
    for region in report['resource_scope']:
        ec2=session.client('ec2',region_name=region,config=config)
        instances=[dict(id=i['InstanceId'],type=i['InstanceType'],state=i['State']['Name'])
            for page in ec2.get_paginator('describe_instances').paginate(Filters=[
                {'Name':'instance-state-name','Values':['pending','running','stopping','stopped']}])
            for r in page['Reservations'] for i in r['Instances']]
        volumes=[dict(id=v['VolumeId'],gib=v['Size']) for page in ec2.get_paginator('describe_volumes').paginate(
            Filters=[{'Name':'status','Values':['available']}]) for v in page['Volumes']]
        addresses=ec2.describe_addresses()['Addresses']
        nats=[n['NatGatewayId'] for page in ec2.get_paginator('describe_nat_gateways').paginate(
            Filter=[{'Name':'state','Values':['available','pending']}]) for n in page['NatGateways']]
        report['regions'][region]=dict(nonterminated_instances=instances,unattached_volumes=volumes,
            elastic_ip_count=len(addresses),active_nat_gateways=nats)
    asg=session.client('autoscaling',config=config)
    groups=[g for page in asg.get_paginator('describe_auto_scaling_groups').paginate()
            for g in page['AutoScalingGroups'] if 'pilot-20261017' in g['AutoScalingGroupName']]
    report['fleets']=[dict(name=g['AutoScalingGroupName'],desired=g['DesiredCapacity'],max=g['MaxSize'],
        instance_ids=[i['InstanceId'] for i in g['Instances']]) for g in groups]
    activities=[];episodes={}
    for group in groups:
        for page in asg.get_paginator('describe_scaling_activities').paginate(AutoScalingGroupName=group['AutoScalingGroupName']):
            for activity in page['Activities']:
                activities.append(activity)
                match=re.search(r'i-[0-9a-f]+',activity['Description'])
                if not match or activity['StatusCode']!='Successful':continue
                episode=episodes.setdefault(match.group(),{})
                if activity['Description'].startswith('Launching'):episode['launch']=activity['StartTime']
                if activity['Description'].startswith('Terminating'):episode['termination']=activity.get('EndTime')
    price=session.client('pricing',config=config).get_products(ServiceCode='AmazonEC2',Filters=[
        {'Type':'TERM_MATCH','Field':k,'Value':v} for k,v in dict(instanceType='c7i.4xlarge',regionCode='us-east-1',
            operatingSystem='Linux',tenancy='Shared',preInstalledSw='NA',capacitystatus='Used').items()])
    rates={Decimal(d['pricePerUnit']['USD']) for p in price['PriceList']
        for term in json.loads(p)['terms'].get('OnDemand',{}).values()
        for d in term['priceDimensions'].values() if d['unit']=='Hrs'}
    if len(rates)!=1:raise ValueError('Ambiguous on-demand EC2 rate')
    rate=rates.pop();seconds=Decimal(0);episode_rows=[]
    for identity,episode in episodes.items():
        if episode.get('launch') and episode.get('termination'):
            span=Decimal(str((episode['termination']-episode['launch']).total_seconds()))
            if span<0:raise ValueError('Invalid ASG activity interval')
            seconds+=span
            episode_rows.append(dict(instance_id=identity,seconds=str(span),**episode))
    report['compute_estimate']=dict(method='ASG launch-start to successful termination-end; operational interval, not billing meter',
        episodes=len(episode_rows),operational_instance_hours=str(seconds/Decimal(3600)),
        on_demand_usd_per_hour=str(rate),compute_only_estimated_usd=str(seconds/Decimal(3600)*rate),
        fx_assumption_brl_per_usd='6.50',planning_margin='30%',
        compute_only_planning_brl=str(seconds/Decimal(3600)*rate*Decimal('6.5')*Decimal('1.3')),
        excludes='EBS, IPv4, S3, ECR, CloudWatch, requests, taxes and final exchange rate')
    end=now.date().isoformat()
    try:
        cache=output/'cost-explorer.json'
        billing=json.loads(cache.read_text()) if cache.exists() and not args.refresh_billing else None
        cached=bool(billing and billing.get('ResultsByTime') and billing['ResultsByTime'][-1]['TimePeriod']['End']==end)
        if not cached:
            billing=session.client('ce',config=config).get_cost_and_usage(
                TimePeriod={'Start':'2026-10-17','End':end},Granularity='DAILY',Metrics=['UnblendedCost'],
                Filter={'Not':{'Dimensions':{'Key':'RECORD_TYPE','Values':['Credit','Refund']}}},
                GroupBy=[{'Type':'DIMENSION','Key':'SERVICE'}])
        amount=sum((Decimal(g['Metrics']['UnblendedCost']['Amount'])
            for day in billing['ResultsByTime'] for g in day['Groups']),Decimal(0))
        report['billing']=dict(status='available_partial',gross_reported_usd=str(amount),
            start='2026-10-17',end_exclusive=end,current_utc_day_excluded=True,
            delayed=True,cached_response=cached,note='Account-wide posted data; excludes credits/refunds. Not a final campaign bill.')
        if not cached:cache.write_text(json.dumps(billing,indent=2,default=str)+'\n')
    except ClientError as exc:
        report['billing']=dict(status='unavailable',error=exc.response['Error'],
            note='No final billing total available; reservations and estimates must not be presented as actual charges.')
    logs=session.client('logs',config=config)
    report['retained_log_groups']=[dict(name=g['logGroupName'],stored_bytes=g.get('storedBytes'),retention_days=g.get('retentionInDays'))
        for page in logs.get_paginator('describe_log_groups').paginate(logGroupNamePrefix='/bankai/') for g in page['logGroups']]
    ecr=session.client('ecr',config=config)
    repository='bankai-image-publisher-images'
    report['retained_ecr_images']=[dict(digest=i['imageDigest'],bytes=i.get('imageSizeInBytes'),pushed_at=i.get('imagePushedAt'))
        for page in ecr.get_paginator('describe_images').paginate(repositoryName=repository) for i in page.get('imageDetails',[])]
    report['retained_bucket']=dict(name=args.bucket,versioning=s3.get_bucket_versioning(Bucket=args.bucket).get('Status'))
    report['retained_resources_note']='Results bucket, ECR image and log objects retained; storage/requests can continue to cost. Zero-capacity ASGs/IAM/task definitions retained for audit.'
    for name,data in [('audit.json',report),('archive-integrity.json',integrity),('scaling-activities.json',activities),
                      ('instance-intervals.json',episode_rows),('compute-price.json',price)]:
        (output/name).write_text(json.dumps(data,indent=2,default=str)+'\n')
    print(json.dumps(report,indent=2,default=str))


if __name__=='__main__':main()
