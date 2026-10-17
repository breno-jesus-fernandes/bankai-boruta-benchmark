"""Security boundaries for the image publisher's AWS access."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_publisher_trust_and_permissions_are_scoped():
    template = json.loads((ROOT/'deployment/publisher.json').read_text())
    role = template['Resources']['Publisher']['Properties']
    trust = role['AssumeRolePolicyDocument']['Statement']
    assert len(trust) == 1
    assert trust[0]['Action'] == 'sts:AssumeRoleWithWebIdentity'
    assert trust[0]['Principal'] == {'Federated': {'Ref': 'GitHubProvider'}}
    assert trust[0]['Condition'] == {'StringEquals': {
        'token.actions.githubusercontent.com:aud': 'sts.amazonaws.com',
        'token.actions.githubusercontent.com:sub': {'Fn::Sub': 'repo:${GitHubRepository}:ref:refs/heads/main'},
    }}
    statements = role['Policies'][0]['PolicyDocument']['Statement']
    for statement in statements:
        actions = statement['Action']
        actions = [actions] if isinstance(actions, str) else actions
        assert all(action.startswith('ecr:') and '*' not in action for action in actions)
        if statement['Resource'] == '*':
            assert actions == ['ecr:GetAuthorizationToken']
        else:
            assert statement['Resource'] == {'Fn::GetAtt': ['Repository', 'Arn']}
    assert 'ManagedPolicyArns' not in role


def test_publish_requires_main_and_image_acceptance_before_aws_auth():
    workflow = (ROOT/'.github/workflows/publish-image.yml').read_text()
    assert "if: github.ref == 'refs/heads/main'" in workflow
    assert workflow.index('scripts/verify_linux.py') < workflow.index('configure-aws-credentials@')
    assert workflow.index('scripts/verify_linux.py') < workflow.index('docker push')
    assert 'workflow_dispatch:' in workflow
    assert 'pull_request' not in workflow
