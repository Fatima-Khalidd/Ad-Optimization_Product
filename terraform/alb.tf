resource "aws_lb" "app" {
  name               = "${var.project}-alb"
  load_balancer_type = "application"
  internal           = false
  subnets            = local.public_subnet_ids
  security_groups    = [aws_security_group.alb.id]

  # Reject malformed/ambiguous headers rather than forwarding them to the app.
  drop_invalid_header_fields = true
  enable_deletion_protection = false

  lifecycle {
    precondition {
      condition     = length(local.public_subnet_ids) >= 2
      error_message = "An ALB needs subnets in at least two availability zones. This default VPC has fewer than two public subnets - enable one more AZ, or import a VPC with two."
    }
  }
}

resource "aws_lb_target_group" "app" {
  name_prefix = "ado-"
  port        = var.app_port
  protocol    = "HTTP"
  target_type = "instance"
  vpc_id      = data.aws_vpc.selected.id

  # Give a terminating instance back to the balancer quickly during a scale-in, but not
  # so fast that an in-flight CSV upload is cut off.
  deregistration_delay = 30

  health_check {
    enabled             = true
    protocol            = "HTTP"
    path                = var.health_check_path
    interval            = 30
    timeout             = 6
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200-299"
  }

  # Deliberately off: the app is stateless (auth is a signed JWT in a cookie, sessions are
  # not held in the process), so round-robin across instances is what the demo needs to
  # show — sticky sessions would pin each client to one target and hide the distribution.
  stickiness {
    type    = "lb_cookie"
    enabled = false
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.app.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}
