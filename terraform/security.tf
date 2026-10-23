# Two security groups: one on the balancer, one on the instances.
#
# Rules live in their own aws_security_group_rule resources instead of inline blocks
# because the ALB group and the instance group must reference each other. Inline blocks
# make Terraform resolve "alb depends on instance depends on alb" and fail with a cycle.

resource "aws_security_group" "alb" {
  name        = "${var.project}-alb"
  description = "Internet-facing load balancer for the lab"
  vpc_id      = data.aws_vpc.selected.id

  tags = { Name = "${var.project}-alb" }
}

resource "aws_security_group" "instance" {
  name        = "${var.project}-instance"
  description = "Docker hosts behind the load balancer"
  vpc_id      = data.aws_vpc.selected.id

  tags = { Name = "${var.project}-instance" }
}

# ------------------------------------------------------------------ inbound ----

# Plain HTTP: the lab has no domain or ACM certificate. That is also why the stack runs
# with ENV=dev - ENV=prod turns on the Secure cookie flag, and no login cookie would ever
# come back on an HTTP response.
resource "aws_security_group_rule" "alb_http_in" {
  type              = "ingress"
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.alb.id
  description       = "HTTP from anywhere"
}

resource "aws_security_group_rule" "instance_app_in" {
  type              = "ingress"
  from_port         = var.app_port
  to_port           = var.app_port
  protocol          = "tcp"
  security_group_id = aws_security_group.instance.id

  # Named source group rather than 0.0.0.0/0: only the balancer may reach the app port,
  # so a public scan of an instance's own address finds nothing listening.
  source_security_group_id = aws_security_group.alb.id
  description              = "Frontend, from the ALB security group only"
}

resource "aws_security_group_rule" "instance_api_in" {
  type                     = "ingress"
  from_port                = var.api_port
  to_port                  = var.api_port
  protocol                 = "tcp"
  security_group_id        = aws_security_group.instance.id
  source_security_group_id = aws_security_group.alb.id
  description              = "API health check, from the ALB security group only"
}

# Port 22 stays closed unless ssh_cidrs names the sources; the default shell path is
# Session Manager, which needs no inbound rule at all.
resource "aws_security_group_rule" "instance_ssh_in" {
  for_each = toset(var.ssh_cidrs)

  type              = "ingress"
  from_port         = 22
  to_port           = 22
  protocol          = "tcp"
  cidr_blocks       = [each.value]
  security_group_id = aws_security_group.instance.id
  description       = "SSH from ${each.value} (only because ssh_cidrs is set)"
}

# ------------------------------------------------------------------ outbound ----

resource "aws_security_group_rule" "alb_app_out" {
  type              = "egress"
  from_port         = var.app_port
  to_port           = var.app_port
  protocol          = "tcp"
  security_group_id = aws_security_group.alb.id

  # On an egress rule this names the destination group.
  source_security_group_id = aws_security_group.instance.id
  description              = "Forward to the Auto Scaling instances"
}

resource "aws_security_group_rule" "alb_api_out" {
  type                     = "egress"
  from_port                = var.api_port
  to_port                  = var.api_port
  protocol                 = "tcp"
  security_group_id        = aws_security_group.alb.id
  source_security_group_id = aws_security_group.instance.id
  description              = "Target group health checks against the API port"
}

resource "aws_security_group_rule" "instance_all_out" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.instance.id
  description       = "Docker Hub, GitHub, apt and PyPI during boot"
}
