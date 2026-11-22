# Cost Guard

Cost Guard is a safety guard for cloud servers. When someone starts an AWS server that is too expensive, it stops the server automatically and shows the estimated money saved on a simple dashboard that works on phone and laptop.


## The problem

On AWS you pay for servers by the hour. A large server (for example a GPU machine) can cost many times more than a small one, and a forgotten one can cause a surprise bill at the end of the month.

## How it works

1. Someone launches an EC2 server.
2. The launch is checked against an allowed list of sizes (for example t3.micro, t3.small).
3. If the size is not allowed and auto-stop is on, the server is stopped and an alert is sent.
4. The dashboard shows what happened, estimated spending prevented and a 7-day chart.

## Two parts

**1. Local prototype (works without an AWS account)**
`local_server.py` is a small Python server that imitates AWS. A "Simulate a launch" bar lets you test the rules, and "Load sample week" fills the dashboard with example data.

**2. AWS serverless version (written, not deployed)**
Defined in `template.yaml` and `src/`, using AWS SAM:
- Amazon EventBridge detects EC2 launches
- AWS Lambda (Python) checks the rules and stops disallowed servers
- Amazon SNS sends the email alert
- Amazon DynamoDB stores history and settings
- API Gateway plus a second Lambda serve the dashboard
- The engine has least-privilege access: it can look at and stop instances, never delete them

I did not deploy this version because my AWS account is on the Free plan, which blocks CloudFormation. The code is written to be deployed with `sam build` and `sam deploy --guided`.

## Run it on your laptop

You need Python 3.12. No other installs.

```
python local_server.py
```

Open http://localhost:8000 and enter the access key `demo1234`. To open it on a phone, connect to the same Wi-Fi and visit `http://<your-laptop-ip>:8000`.

## Project structure

```
template.yaml          AWS SAM template (all AWS resources)
src/engine/app.py      Lambda that checks launches and stops servers
src/api/app.py         Lambda that serves the dashboard data
dashboard/index.html   Responsive dashboard (plain HTML, CSS, JavaScript)
local_server.py        Local demo server (no AWS needed)
```

## Notes

- The "spending prevented" figures are estimates. They use rough illustrative hourly prices and assume each stopped server would have run for 24 hours.
- The demo access key is for local use only.

## Built with

Python, AWS Lambda, EventBridge, SNS, DynamoDB, API Gateway, AWS SAM, HTML, CSS, JavaScript