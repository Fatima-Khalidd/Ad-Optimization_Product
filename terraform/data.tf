# The lab uses the account's default VPC: it already has one subnet per availability
# zone, which is what an ALB and an Auto Scaling Group need (ALBs require >=2 zones).
data "aws_vpc" "selected" {
  default = true
}

data "aws_subnets" "selected" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.selected.id]
  }
}

data "aws_subnet" "selected" {
  for_each = toset(data.aws_subnets.selected.ids)
  id       = each.value
}

# Only public subnets (map_public_ip_on_tile), because the ALB is internet-facing and the
# instances have to reach Docker Hub and GitHub at boot without a NAT gateway.
locals {
  public_subnet_ids = [
    for s in data.aws_subnet.selected : s.id if s.map_public_ip_on_launch
  ]
  availability_zones = distinct([
    for s in data.aws_subnet.selected : s.availability_zone if s.map_public_ip_on_launch
  ])
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical's publisher account id

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-noble-24.04-amd64-server-*"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}
