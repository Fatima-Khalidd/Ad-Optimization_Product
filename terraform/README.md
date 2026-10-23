# Terraform — ALB + Auto Scaling (exam Task 1)

One ALB in front of an Auto Scaling Group of two EC2 instances; each instance runs the
whole Compose stack from the repo (`docs/devops-aws-deploy.md` explains the state
trade-off this implies).

| File | What it holds |
| --- | --- |
| `versions.tf` | Terraform >= 1.6, AWS provider ~> 6.0 |
| `variables.tf` | region, project, instance type, ports, `min`/`desired`/`max` size, `ssh_cidrs`, `rate_limit_storage_uri` |
| `data.tf` | Default VPC + its public subnets, Ubuntu 24.04 AMI, EC2 assume-role policy |
| `security.tf` | ALB group (80 from anywhere) and instance group (3000/8000 from the ALB group only) |
| `iam.tf` | Instance role, `AmazonSSMManagedInstanceCore`, instance profile |
| `launch-template.tf` | `t3.medium`, encrypted gp3 root, IMDSv2 required, user data |
| `alb.tf` | Load balancer, target group (`/api/health`), listener :80 |
| `asg.tf` | ASG (min 2 / desired 2 / max 4), CPU target-tracking policy, instance refresh, a `check` on the 2-instance minimum |
| `outputs.tf` | `app_url`, `health_url`, `verify_command`, `session_manager_command`, `destroy_command` |
| `templates/user_data.sh.tpl` | Boot script: swap, Docker, clone, `scripts/bootstrap-ec2.sh` |

## Before you apply

**Commit and push first.** Each instance clones `var.repo_url` / `var.branch` at boot and
runs `scripts/bootstrap-ec2.sh` from that checkout, so anything not pushed does not exist
on the instance. Verify with `git log --oneline -1 origin/main` before applying.

```bash
aws configure list                     # credentials + region must be set
terraform -chdir=terraform init        # downloads the AWS provider
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
```

Edit `terraform.tfvars`: `region`, `project` and `branch`. `branch` matters — the DevOps
work is on `devops-lab`, so leaving `main` there means the instances clone a tree with no
Dockerfiles in it. `ssh_cidrs` stays `[]` unless you specifically want port 22; the default
path is Session Manager, which opens no inbound port. `terraform.tfvars` is gitignored, so
nothing you put in it is published.

## Plan, then apply

```bash
terraform -chdir=terraform plan   # READ THIS. It says exactly what will be created.
terraform -chdir=terraform apply  # ~8-12 minutes: the ASG waits for both instances to pass ELB health checks
```

The first boot pulls the image layers and builds the frontend on the instance, so the
grace period is 900 seconds and `wait_for_capacity_timeout` is 25m. If instances never
go healthy, read the boot log instead of guessing:

```bash
aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names ad-optimizer-asg
aws ssm start-session --target <i-...>       # no key pair, no port 22
sudo cat /var/log/cloud-init-output.log
```

## Verify

```bash
terraform -chdir=terraform output app_url
terraform -chdir=terraform output verify_command | xargs -I{} bash -c {}
```

`scripts/verify-load-balancing.sh` tallies distinct `instance` values from `/api/health`
across repeated requests — that is the distribution evidence.

## Destroy

```bash
terraform -chdir=terraform destroy
```

Destroy runs the same day as the demo. It removes the ASG first (which terminates both
instances), then the ALB, listener, target group, launch template, IAM and security
groups. Confirm nothing is left:

```bash
aws ec2 describe-instances --filters Name=tag:Project,Values=<your-project> Name=instance-state-name,Values=running
aws elbv2 describe-load-balancers --query "LoadBalancers[?contains(LoadBalancerName,'<your-project>')].LoadBalancerName"
```

Both should come back empty. If `destroy` fails on a resource you created by hand,
`terraform state list` shows what Terraform owns; never delete an ASG in the console and
expect Terraform to cope with the rest.

## Notes

- State is local (`terraform.tfstate`, gitignored). For a shared team you would move it to
  an S3 backend with a DynamoDB lock; that is out of scope for a lab but is the viva
  answer to "what happens if two people apply at once".
- Subnets come from the account's default VPC. The ALB `precondition` fails early with a
  readable message if fewer than two public subnets exist — an ALB must span two AZs.
- The target group uses `name_prefix = "ado-"` because the full name plus suffix would
  otherwise risk colliding when Terraform recreates it (`create_before_destroy`).
