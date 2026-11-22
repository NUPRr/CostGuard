import json
import os
import uuid
from datetime import datetime, timezone

import boto3

TABLE = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
SNS = boto3.client("sns")
TOPIC_ARN = os.environ["TOPIC_ARN"]

DEFAULT_SETTINGS = {
    "auto_stop": True,
    "allowed_types": ["t2.micro", "t3.micro", "t3.small"],
}


def get_settings():
    item = TABLE.get_item(Key={"pk": "SETTINGS", "ts": "config"}).get("Item") or {}
    return {**DEFAULT_SETTINGS, **item}


def stop_instance(instance_id, region):
    ec2 = boto3.client("ec2", region_name=region)
    ec2.get_waiter("instance_running").wait(
        InstanceIds=[instance_id], WaiterConfig={"Delay": 5, "MaxAttempts": 20}
    )
    ec2.stop_instances(InstanceIds=[instance_id])


def save_record(record):
    TABLE.put_item(Item=record)


def lambda_handler(event, context):
    detail = event.get("detail", {})
    region = event.get("region") or detail.get("awsRegion")
    who = detail.get("userIdentity", {}).get("arn", "unknown user")
    items = detail.get("responseElements", {}).get("instancesSet", {}).get("items", [])
    settings = get_settings()
    allowed = [t.strip().lower() for t in settings["allowed_types"]]

    for inst in items:
        instance_id = inst.get("instanceId", "unknown")
        instance_type = inst.get("instanceType", "unknown")
        now = datetime.now(timezone.utc).isoformat()

        if instance_type.lower() in allowed:
            status = "ALLOWED"
            message = f"{instance_type} is on the allowed list. No action needed."
        elif settings["auto_stop"]:
            try:
                stop_instance(instance_id, region)
                status = "STOPPED"
                message = f"{instance_type} is not allowed. It was stopped automatically."
            except Exception as err:
                status = "FAILED"
                message = f"{instance_type} is not allowed but could not be stopped: {err}"
        else:
            status = "FLAGGED"
            message = f"{instance_type} is not allowed. Auto-stop is OFF, so it was left running."

        save_record(
            {
                "pk": "EVENT",
                "ts": f"{now}#{uuid.uuid4().hex[:6]}",
                "time": now,
                "instance_id": instance_id,
                "instance_type": instance_type,
                "region": region,
                "launched_by": who,
                "status": status,
                "message": message,
            }
        )

        if status != "ALLOWED":
            SNS.publish(
                TopicArn=TOPIC_ARN,
                Subject=f"Cost Guard: {status} {instance_type}",
                Message=(
                    f"{message}\n\n"
                    f"Instance: {instance_id}\n"
                    f"Region: {region}\n"
                    f"Launched by: {who}\n"
                    f"Time (UTC): {now}"
                ),
            )

    return {"checked": len(items)}