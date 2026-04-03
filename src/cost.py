import json
import os

HOURS_PER_MONTH = 730

REGION_NAMES = {
    "us-east-1": "US East (N. Virginia)",
    "us-east-2": "US East (Ohio)",
    "us-west-1": "US West (N. California)",
    "us-west-2": "US West (Oregon)",
    "ap-south-1": "Asia Pacific (Mumbai)",
    "ap-southeast-1": "Asia Pacific (Singapore)",
    "ap-southeast-2": "Asia Pacific (Sydney)",
    "ap-northeast-1": "Asia Pacific (Tokyo)",
    "ap-northeast-2": "Asia Pacific (Seoul)",
    "eu-west-1": "Europe (Ireland)",
    "eu-west-2": "Europe (London)",
    "eu-central-1": "Europe (Frankfurt)",
    "ca-central-1": "Canada (Central)",
    "sa-east-1": "South America (Sao Paulo)",
}

RDS_ENGINE_MAP = {
    "mysql": "MySQL",
    "postgres": "PostgreSQL",
    "mariadb": "MariaDB",
    "oracle-se2": "Oracle",
    "sqlserver-se": "SQL Server",
    "aurora-mysql": "Aurora MySQL",
    "aurora-postgresql": "Aurora PostgreSQL",
}

_price_cache = {}

EC2_FALLBACK = {
    "t2.nano": 0.0058, "t2.micro": 0.0116, "t2.small": 0.023, "t2.medium": 0.0464,
    "t2.large": 0.0928, "t2.xlarge": 0.1856, "t2.2xlarge": 0.3712,
    "t3.nano": 0.0052, "t3.micro": 0.0104, "t3.small": 0.0208, "t3.medium": 0.0416,
    "t3.large": 0.0832, "t3.xlarge": 0.1664, "t3.2xlarge": 0.3328,
    "t3a.micro": 0.0094, "t3a.small": 0.0188, "t3a.medium": 0.0376,
    "m5.large": 0.096, "m5.xlarge": 0.192, "m5.2xlarge": 0.384, "m5.4xlarge": 0.768,
    "m6i.large": 0.096, "m6i.xlarge": 0.192, "m6i.2xlarge": 0.384,
    "c5.large": 0.085, "c5.xlarge": 0.17, "c5.2xlarge": 0.34,
    "r5.large": 0.126, "r5.xlarge": 0.252, "r5.2xlarge": 0.504,
}

RDS_FALLBACK = {
    "db.t3.micro": 0.017, "db.t3.small": 0.034, "db.t3.medium": 0.068,
    "db.t3.large": 0.136, "db.m5.large": 0.171, "db.m5.xlarge": 0.342,
    "db.r5.large": 0.24, "db.r5.xlarge": 0.48,
}


def _get_pricing_client():
    try:
        import boto3
        return boto3.client("pricing", region_name="us-east-1")
    except Exception:
        return None


def _extract_hourly_price(price_list_item):
    try:
        product = json.loads(price_list_item)
        on_demand = product.get("terms", {}).get("OnDemand", {})
        if not on_demand:
            return None
        term = list(on_demand.values())[0]
        for dim in term.get("priceDimensions", {}).values():
            unit = dim.get("unit", "")
            price = float(dim.get("pricePerUnit", {}).get("USD", "0"))
            if price > 0 and unit in ("Hrs", "hours"):
                return price
    except Exception:
        pass
    return None


def _fetch_ec2_price(instance_type, region="us-east-1"):
    cache_key = f"ec2:{instance_type}:{region}"
    if cache_key in _price_cache:
        return _price_cache[cache_key]
    client = _get_pricing_client()
    if not client:
        return None
    location = REGION_NAMES.get(region, "US East (N. Virginia)")
    try:
        response = client.get_products(
            ServiceCode="AmazonEC2",
            Filters=[
                {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_type},
                {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": "Linux"},
                {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"},
                {"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"},
                {"Type": "TERM_MATCH", "Field": "capacityStatus", "Value": "Used"},
                {"Type": "TERM_MATCH", "Field": "location", "Value": location},
            ],
            MaxResults=1,
        )
        if response["PriceList"]:
            price = _extract_hourly_price(response["PriceList"][0])
            _price_cache[cache_key] = price
            return price
    except Exception as e:
        print(f"  [pricing] EC2 API failed for {instance_type}: {e}")
    return None


def _fetch_rds_price(instance_class, engine="mysql", region="us-east-1"):
    cache_key = f"rds:{instance_class}:{engine}:{region}"
    if cache_key in _price_cache:
        return _price_cache[cache_key]
    client = _get_pricing_client()
    if not client:
        return None
    location = REGION_NAMES.get(region, "US East (N. Virginia)")
    db_engine = RDS_ENGINE_MAP.get(engine, "MySQL")
    try:
        response = client.get_products(
            ServiceCode="AmazonRDS",
            Filters=[
                {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_class},
                {"Type": "TERM_MATCH", "Field": "databaseEngine", "Value": db_engine},
                {"Type": "TERM_MATCH", "Field": "deploymentOption", "Value": "Single-AZ"},
                {"Type": "TERM_MATCH", "Field": "location", "Value": location},
            ],
            MaxResults=1,
        )
        if response["PriceList"]:
            price = _extract_hourly_price(response["PriceList"][0])
            _price_cache[cache_key] = price
            return price
    except Exception as e:
        print(f"  [pricing] RDS API failed for {instance_class}: {e}")
    return None


def _fetch_nat_price(region="us-east-1"):
    cache_key = f"nat:{region}"
    if cache_key in _price_cache:
        return _price_cache[cache_key]
    client = _get_pricing_client()
    if not client:
        return None
    location = REGION_NAMES.get(region, "US East (N. Virginia)")
    try:
        response = client.get_products(
            ServiceCode="AmazonEC2",
            Filters=[
                {"Type": "TERM_MATCH", "Field": "productFamily", "Value": "NAT Gateway"},
                {"Type": "TERM_MATCH", "Field": "location", "Value": location},
            ],
            MaxResults=5,
        )
        for item in response["PriceList"]:
            price = _extract_hourly_price(item)
            if price:
                _price_cache[cache_key] = price
                return price
    except Exception as e:
        print(f"  [pricing] NAT Gateway API failed: {e}")
    return None


def _fetch_alb_price(region="us-east-1"):
    cache_key = f"alb:{region}"
    if cache_key in _price_cache:
        return _price_cache[cache_key]
    client = _get_pricing_client()
    if not client:
        return None
    location = REGION_NAMES.get(region, "US East (N. Virginia)")
    try:
        response = client.get_products(
            ServiceCode="AWSElasticLoadBalancing",
            Filters=[
                {"Type": "TERM_MATCH", "Field": "productFamily", "Value": "Load Balancer-Application"},
                {"Type": "TERM_MATCH", "Field": "location", "Value": location},
            ],
            MaxResults=1,
        )
        if response["PriceList"]:
            price = _extract_hourly_price(response["PriceList"][0])
            _price_cache[cache_key] = price
            return price
    except Exception as e:
        print(f"  [pricing] ALB API failed: {e}")
    return None


def _fetch_elasticache_price(node_type, region="us-east-1"):
    cache_key = f"elasticache:{node_type}:{region}"
    if cache_key in _price_cache:
        return _price_cache[cache_key]
    client = _get_pricing_client()
    if not client:
        return None
    location = REGION_NAMES.get(region, "US East (N. Virginia)")
    try:
        response = client.get_products(
            ServiceCode="AmazonElastiCache",
            Filters=[
                {"Type": "TERM_MATCH", "Field": "instanceType", "Value": node_type},
                {"Type": "TERM_MATCH", "Field": "location", "Value": location},
            ],
            MaxResults=1,
        )
        if response["PriceList"]:
            price = _extract_hourly_price(response["PriceList"][0])
            _price_cache[cache_key] = price
            return price
    except Exception as e:
        print(f"  [pricing] ElastiCache API failed for {node_type}: {e}")
    return None


def estimate_resource_cost(resource):
    rtype = resource.get("type")
    config = resource.get("config", {})
    region = os.environ.get("AWS_DEFAULT_REGION", config.get("region", "us-east-1"))

    result = {
        "address": resource.get("address"),
        "type": rtype,
        "monthly_cost": None,
        "note": None,
        "source": None,
    }

    if rtype == "aws_instance":
        instance_type = config.get("instance_type") or "t3.micro"
        hourly = _fetch_ec2_price(instance_type, region)
        source = "AWS Pricing API"
        if hourly is None:
            hourly = EC2_FALLBACK.get(instance_type)
            source = "fallback"
        if hourly:
            result["monthly_cost"] = round(hourly * HOURS_PER_MONTH, 2)
            result["detail"] = instance_type
            result["source"] = source
        else:
            result["note"] = f"No price found for {instance_type}"

    elif rtype == "aws_db_instance":
        instance_class = config.get("instance_class") or "db.t3.micro"
        engine = config.get("engine") or "mysql"
        storage_gb = float(config.get("allocated_storage") or 20)
        hourly = _fetch_rds_price(instance_class, engine, region)
        source = "AWS Pricing API"
        if hourly is None:
            hourly = RDS_FALLBACK.get(instance_class)
            source = "fallback"
        if hourly:
            compute = round(hourly * HOURS_PER_MONTH, 2)
            storage = round(storage_gb * 0.115, 2)
            result["monthly_cost"] = round(compute + storage, 2)
            result["detail"] = f"{instance_class} ({engine}), {int(storage_gb)}GB"
            result["source"] = source
        else:
            result["note"] = f"No price found for {instance_class}"

    elif rtype == "aws_nat_gateway":
        hourly = _fetch_nat_price(region)
        result["monthly_cost"] = round((hourly or 0.045) * HOURS_PER_MONTH, 2)
        result["detail"] = "NAT Gateway (+ data processing charges)"
        result["source"] = "AWS Pricing API" if hourly else "fallback"

    elif rtype in ("aws_lb", "aws_alb", "aws_elb"):
        hourly = _fetch_alb_price(region)
        result["monthly_cost"] = round((hourly or 0.008) * HOURS_PER_MONTH, 2)
        result["detail"] = "Load Balancer (+ LCU charges)"
        result["source"] = "AWS Pricing API" if hourly else "fallback"

    elif rtype == "aws_elasticache_cluster":
        node_type = config.get("node_type") or "cache.t3.micro"
        hourly = _fetch_elasticache_price(node_type, region)
        if hourly:
            result["monthly_cost"] = round(hourly * HOURS_PER_MONTH, 2)
            result["detail"] = node_type
            result["source"] = "AWS Pricing API"
        else:
            result["note"] = f"No price found for {node_type}"

    elif rtype == "aws_eks_cluster":
        result["monthly_cost"] = round(0.10 * HOURS_PER_MONTH, 2)
        result["detail"] = "EKS control plane (worker nodes billed separately)"
        result["source"] = "fixed rate"

    elif rtype == "aws_lambda_function":
        result["note"] = "Depends on invocations and duration"

    elif rtype == "aws_s3_bucket":
        result["note"] = "Depends on storage volume and requests"

    elif rtype == "aws_ecs_service":
        result["note"] = "Depends on task CPU/memory"

    elif rtype == "aws_cloudfront_distribution":
        result["note"] = "Depends on data transfer and requests"

    else:
        result["note"] = f"Pricing not yet supported for {rtype}"

    return result


def estimate_costs(summary):
    cost_items = []
    total = 0.0
    has_unknown = False

    for action in ["create", "replace"]:
        for resource in summary["changes"][action]:
            item = estimate_resource_cost(resource)
            item["action"] = action
            cost_items.append(item)
            if item["monthly_cost"] is not None:
                total += item["monthly_cost"]
            else:
                has_unknown = True

    destroyed_items = []
    destroyed_total = 0.0
    for resource in summary["changes"]["delete"]:
        item = estimate_resource_cost(resource)
        item["action"] = "delete"
        destroyed_items.append(item)
        if item["monthly_cost"] is not None:
            destroyed_total += item["monthly_cost"]

    return {
        "added": cost_items,
        "destroyed": destroyed_items,
        "total_added": round(total, 2),
        "total_saved": round(destroyed_total, 2),
        "net": round(total - destroyed_total, 2),
        "has_unknown": has_unknown,
    }