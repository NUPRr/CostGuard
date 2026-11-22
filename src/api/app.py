import hmac
import json
import os

import boto3

TABLE = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
API_KEY = os.environ["API_KEY"]

DEFAULT_SETTINGS = {
    "auto_stop": True,
    "allowed_types": ["t2.micro", "t3.micro", "t3.small"],
}


def reply(code, body):
    return {
        "statusCode": code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def get_settings():
    item = TABLE.get_item(Key={"pk": "SETTINGS", "ts": "config"}).get("Item") or {}
    return {
        "auto_stop": bool(item.get("auto_stop", DEFAULT_SETTINGS["auto_stop"])),
        "allowed_types": list(item.get("allowed_types", DEFAULT_SETTINGS["allowed_types"])),
    }


def lambda_handler(event, context):
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    if not hmac.compare_digest(headers.get("x-api-key", ""), API_KEY):
        return reply(401, {"error": "Wrong access key"})

    method = event["requestContext"]["http"]["method"]
    path = event.get("rawPath", "")

    if method == "GET" and path.endswith("/events"):
        result = TABLE.query(
            KeyConditionExpression="pk = :p",
            ExpressionAttributeValues={":p": "EVENT"},
            ScanIndexForward=False,
            Limit=50,
        )
        return reply(200, {"events": result.get("Items", [])})

    if method == "GET" and path.endswith("/settings"):
        return reply(200, get_settings())

    if method == "POST" and path.endswith("/settings"):
        try:
            data = json.loads(event.get("body") or "{}")
            types = [str(t).strip().lower() for t in data.get("allowed_types", []) if str(t).strip()]
            settings = {"auto_stop": bool(data.get("auto_stop", True)), "allowed_types": types}
        except (ValueError, TypeError):
            return reply(400, {"error": "Could not read the settings"})
        TABLE.put_item(Item={"pk": "SETTINGS", "ts": "config", **settings})
        return reply(200, settings)

    return reply(404, {"error": "Not found"})