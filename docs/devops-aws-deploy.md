# AWS deployment: load balancer + Auto Scaling Group

Section A, task 1. Roughly 30 minutes start to finish, of which most is waiting for the
instances to build their images. **Destroy the stack the same day** — two `t3.medium`s plus
an ALB run about $0.25/hour.

## 0. Prerequisites

* An AWS account with billing enabled (a student account works; the free tier does not
  cover `t3.medium` x2 plus an ALB).
* AWS CLI v2 and Terraform >= 1.5 on the machine you apply from.
* Credentials that can create EC2, Elastic Load Balancing, Auto Scaling and IAM resources:

  ```bash
  aws configure                      # or export AWS_ACCESS_KEY_ID / SECRET / REGION
  aws sts get-caller-identity        # prove which account you are about to change
  export AWS_DEFAULT_REGION=ap-south-1
  ```

* The pushed version of this repository — the instances `git clone` the repo at boot, so
  anything uncommitted never reaches AWS. Push your branch and pass `branch = "..."` in
  `terraform.tfvars`.

> IAM note for the viva: the instances get exactly one managed policy,
> `AmazonSSMManagedInstanceCore`. They have no S3 or EC2 write permissions, so even a
> compromised container cannot create resources. That is why `aws_iam_instance_profile`
> exists rather than embedding keys in the user data.

## 1. Plan

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars   # set owner_tag, branch, instance_type
terraform init
terraform plan        # read it: every resource is new, nothing is "destroy"
```

Expect the plan to list: 2 security groups + 6 rules, 1 IAM role + profile + attachment,
1 launch template, 1 ALB, 1 target group, 1 listener, 1 Auto Scaling group, 1 scaling
policy.

## 2. Apply

```bash
terraform apply
```

The group comes up with `min_size = desired = 2`. Provisioning is slow on purpose: user
data installs Docker, clones the repo, builds the frontend image, runs the migration and
seeds the demo client. Give it 10-15 minutes; `wait_for_capacity_timeout = "25m"` stops the
group from deciding the instances failed too early.

## 3. Confirm the balancer sees both targets

```bash
terraform output app_url
terraform output health_url

aws elbv2 describe-target-health \
  --target-group-arn $(terraform output -raw target_group_arn) \
  --query 'TargetHealthDescriptions[].{id:Target.Id,state:TargetHealth.State}' --output table
```

Both must read `healthy`. If one is `initial`, keep waiting; if it is `unhealthy`, read
`scripts/bootstrap-ec2.sh` output on that instance:

```bash
aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names $(terraform output -raw autoscaling_group_name) \
  --query 'AutoScalingGroups[0].Instances[].InstanceId' --output text

aws ssm start-session --target i-xxxxxxxx          # no SSH key, no port 22
sudo tail -n 100 /var/log/user-data.log
sudo docker compose -f /opt/ad-optimizer/docker-compose.yml ps
```

## 4. Prove the distribution and the resilience

```bash
bash scripts/verify-load-balancing.sh "$(terraform output -raw alb_dns_name)"
```

That prints the HTTP code, the distinct `instance` values returned by `/api/health` with
how many requests each served, the target health table, the group's min/desired/max and
the scaling policies. Then, live:

1. Loop a request: `while true; do curl -s $(terraform output -raw health_url); echo; sleep 1; done`
2. Terminate one instance:
   `aws autoscaling terminate-instance-in-auto-scaling-group --instance-id i-xxx --no-hide-in-auto-scaling-group`
3. The loop keeps returning 200 while the group launches a replacement.

That single sequence covers load balancing, health checking **and** auto scaling.

## 5. Prove it scales out

CPU target tracking needs real load. From one instance, generate work through the
balancer:

```bash
aws ssm start-session --target i-xxx
sudo -i
cd /opt/ad-optimizer
for i in $(seq 1 4000); do curl -s -o /dev/null http://localhost:3000/api/health; done
```

Then watch CloudWatch pick it up:

```bash
aws autoscaling describe-scaling-activities \
  --auto-scaling-group-names $(terraform output -raw autoscaling_group_name) \
  --max-items 3 --query 'Activities[].{status:StatusCode,cause:Cause}' --output table
```

A faster, fully honest alternative for the demo is to move the ceiling directly — same
lifecycle, no waiting on a metric:

```bash
aws autoscaling update-auto-scaling-group \
  --auto-scaling-group-name $(terraform output -raw autoscaling_group_name) --desired-capacity 3
```

Show both: the policy is the *configuration*, the activity log is the *evidence*.

## 6. Selenium against the deployed URL

```bash
APP_BASE_URL="$(terraform output -raw app_url)" DEMO_PASSWORD="$(ssh-free: see below)" \
  pytest tests/selenium -v
```

The demo password is generated on each instance at boot:
`aws ssm start-session` then `sudo cat /opt/ad-optimizer/.demo-password`. It is never in
Terraform state and never in Git, which is a point worth making in the viva.

## 7. Teardown

```bash
terraform destroy     # answers "yes" once; deletes ASG, instances, ALB, target group, SGs, IAM
docker compose down   # on your laptop
```

Confirm nothing is left billing:

```bash
aws ec2 describe-instances --filters Name=instance-state-name,Values=running \
  --query 'Reservations[].Instances[?Tags[?Value==`ad-optimizer`]].InstanceId' --output table
aws elbv2 describe-load-balancers --query 'LoadBalancers[?contains(LoadBalancerName,`ad-optimizer`)].LoadBalancerName'
```

## What the Terraform choices are for

| Choice | Where | Why it matters here |
| --- | --- | --- |
| `min_size = 2`, `desired = 2` | `variables.tf` | The paper requires two application instances behind the balancer |
| Target group on :3000, health `/api/health` | `alb.tf` | The path is proxied by Next to the API, so 200 means web **and** api **and** db are up |
| `stickiness.enabled = false` | `alb.tf` | Round-robin is what you need to *show* distribution; the app is stateless (cookies + shared DB) |
| Target-group-only ingress on the instance SG | `security.tf` | Port 3000/8000 are not open to the internet; only the ALB can reach them |
| `AmazonSSMManagedInstanceCore`, `ssh_cidrs = []` | `iam.tf`, `security.tf` | Shell access with no key pair and no inbound 22 |
| `http_tokens = "required"`, hop limit 2 | `launch-template.tf` | IMDSv2 only, and still reachable from containers |
| 2 GB swap in user data | `templates/user_data.sh.tpl` | The Next.js build is OOM-killed on a 4 GB instance without it |
| `health_check_grace_period = 900` | `asg.tf` | Otherwise the group kills instances that are still building images |
| `instance_refresh` at 50% healthy | `asg.tf` | A new template version rolls the fleet without dropping below the floor |
| gp3 40 GB encrypted root | `launch-template.tf` | Images, build cache and the Docker volumes need the space |

## Faster scaling (optional, impresses examiners)

Cold boot is minutes because every instance builds images. The production answer is a
pre-baked AMI: build once (HashiCorp Packer, or launch one instance, `docker compose
build`, then create an AMI from it) and point the launch template at
`data.aws_ami` → an `aws_ami` lookup by tag. Boot time drops to about a minute, and
`health_check_grace_period` can come down with it. Say this in the viva rather than
implementing it — scale-up latency is a known cost of the design as it stands.
