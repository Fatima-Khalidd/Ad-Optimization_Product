resource "aws_autoscaling_group" "app" {
  name             = "${var.project}-asg"
  min_size         = var.min_size
  max_size         = var.max_size
  desired_capacity = var.desired_capacity

  vpc_zone_identifier = local.public_subnet_ids
  target_group_arns   = [aws_lb_target_group.app.arn]

  launch_template {
    id      = aws_launch_template.app.id
    version = "$LATEST"
  }

  # "ELB" means the target group's health check decides whether an instance is kept, so a
  # container that crashes on boot gets the instance replaced.
  health_check_type = "ELB"

  # The grace period has to cover the whole cold boot: apt, git clone, the Docker builds
  # and the first migration. Under ~15 minutes an instance would be judged and killed
  # before it ever registers healthy. (docs/DEVOPS.md lists pre-baking an AMI as the fix
  # for scaling latency.)
  health_check_grace_period = 900
  wait_for_capacity_timeout = "25m"

  # Pushing a new launch template version rolls the fleet instead of leaving the old
  # nodes running. 50% healthy keeps the group above its two-instance floor.
  instance_refresh {
    strategy = "Rolling"

    preferences {
      min_healthy_percentage = 50
    }
  }

  tag {
    key                 = "Name"
    value               = "${var.project}-app"
    propagate_at_launch = true
  }

  tag {
    key                 = "Role"
    value               = "web-and-api"
    propagate_at_launch = true
  }

  tag {
    key                 = "Lab"
    value               = "csc418-midterm"
    propagate_at_launch = true
  }
}

# Non-fatal guard: the paper asks for two application instances behind the balancer, so a
# single-node group is a mistake worth flagging at plan time rather than at the viva.
check "two_instance_minimum" {
  assert {
    condition     = var.min_size >= 2
    error_message = "min_size is below 2: the load balancer will have one target, so the distribution demo and the failover demo cannot be shown."
  }
}

# Target tracking on average CPU: scale out over the threshold, scale back in under it.
resource "aws_autoscaling_policy" "cpu_target_tracking" {
  name                   = "${var.project}-cpu-${var.cpu_target_percentage}"
  policy_type            = "TargetTrackingScaling"
  autoscaling_group_name = aws_autoscaling_group.app.name

  target_tracking_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ASGAverageCPUUtilization"
    }

    target_value = var.cpu_target_percentage
  }
}
