import json


# CloudFormation action → our internal action key
CFN_ACTION_MAP = {
    "Add": "create",
    "Modify": "update",
    "Remove": "delete",
    "Import": "create",
    "Dynamic": "update",
}

# CloudFormation ResourceType → AWS Terraform-equivalent type
# Used so cost.py and security.py can reuse existing logic
CFN_TYPE_MAP = {
    "AWS::EC2::Instance": "aws_instance",
    "AWS::EC2::SecurityGroup": "aws_security_group",
    "AWS::EC2::NatGateway": "aws_nat_gateway",
    "AWS::RDS::DBInstance": "aws_db_instance",
    "AWS::S3::Bucket": "aws_s3_bucket",
    "AWS::IAM::Role": "aws_iam_role",
    "AWS::IAM::Policy": "aws_iam_policy",
    "AWS::IAM::ManagedPolicy": "aws_iam_policy",
    "AWS::ElasticLoadBalancingV2::LoadBalancer": "aws_lb",
    "AWS::EKS::Cluster": "aws_eks_cluster",
    "AWS::Lambda::Function": "aws_lambda_function",
    "AWS::ElastiCache::CacheCluster": "aws_elasticache_cluster",
}


def parse_changeset(changeset_json_path: str) -> tuple:
    """
    Parse a CloudFormation changeset JSON file.
    Returns (summary, plan_raw) in the same format as parse_plan()
    so cost.py, security.py, and comment.py work unchanged.
    """
    with open(changeset_json_path, "r", encoding="utf-8-sig") as f:
        raw = json.load(f)

    # Support both direct changeset response and wrapped format
    changes_list = raw.get("Changes", raw.get("changes", []))

    changes = {
        "create": [],
        "update": [],
        "delete": [],
        "replace": [],
        "no-op": [],
        "read": [],
    }

    # Build a synthetic resource_changes list for security.py compatibility
    resource_changes_raw = []

    for change in changes_list:
        resource_change = change.get("ResourceChange", change)

        cfn_action = resource_change.get("Action", "Modify")
        cfn_type = resource_change.get("ResourceType", "")
        logical_id = resource_change.get("LogicalResourceId", "")
        physical_id = resource_change.get("PhysicalResourceId", logical_id)
        replacement = resource_change.get("Replacement", "False")

        # Map to internal action
        if cfn_action == "Modify" and replacement in ("True", "Conditional"):
            action_key = "replace"
        else:
            action_key = CFN_ACTION_MAP.get(cfn_action, "update")

        # Map CFN type to equivalent terraform type for cost/security reuse
        mapped_type = CFN_TYPE_MAP.get(cfn_type, cfn_type.lower().replace("::", "_").replace("aws_", "aws_"))

        address = f"{cfn_type}.{logical_id}"

        entry = {
            "name": logical_id,
            "type": mapped_type,
            "cfn_type": cfn_type,
            "address": address,
            "module": None,
            "config": _extract_cfn_config(resource_change),
        }

        changes[action_key].append(entry)

        # Build synthetic plan_raw entry for security scanner
        resource_changes_raw.append({
            "address": address,
            "type": mapped_type,
            "change": {
                "actions": [cfn_action.lower()],
                "after": _extract_cfn_config(resource_change),
                "before": None,
            }
        })

    total = sum(len(v) for v in changes.values())

    summary = {
        "total": total,
        "changes": changes,
        "counts": {k: len(v) for k, v in changes.items()},
        "source": "cloudformation",
    }

    plan_raw = {"resource_changes": resource_changes_raw}

    return summary, plan_raw


def _extract_cfn_config(resource_change: dict) -> dict:
    """
    Extract a best-effort config dict from a CFN resource change.
    CFN changesets don't include full resource properties,
    so we extract what we can from ResourceChange details.
    """
    config = {}
    details = resource_change.get("Details", [])

    for detail in details:
        target = detail.get("Target", {})
        attribute = target.get("Attribute", "")
        name = target.get("Name", "")

        # Try to pull property values if available
        if attribute == "Properties" and name:
            # CFN changeset doesn't give us the new values directly,
            # just which properties are changing. We note them.
            config[name.lower()] = detail.get("CausingEntity", None)

    return config


def load_changeset_from_aws(stack_name: str, changeset_name: str, region: str = "us-east-1") -> dict:
    """
    Fetch a changeset directly from AWS CloudFormation API.
    Returns the raw changeset dict.
    """
    try:
        import boto3
        client = boto3.client("cloudformation", region_name=region)
        response = client.describe_change_set(
            StackName=stack_name,
            ChangeSetName=changeset_name,
        )
        return response
    except Exception as e:
        raise RuntimeError(f"Failed to fetch changeset from AWS: {e}")