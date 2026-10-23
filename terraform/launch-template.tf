# A launch template (not a raw configuration) because an Auto Scaling Group requires one,
# and because it is what makes replacement instances reproducible.

locals {
  user_data = base64encode(templatefile("${path.module}/templates/user_data.sh.tpl", {
    repo_url               = var.repo_url
    branch                 = var.branch
    app_port               = var.app_port
    api_port               = var.api_port
    rate_limit_storage_uri = var.rate_limit_storage_uri
    owner_tag              = var.owner_tag
  }))
}

resource "aws_launch_template" "app" {
  name_prefix   = "${var.project}-lt-"
  description   = "Runs the Compose stack on Ubuntu 24.04; see scripts/bootstrap-ec2.sh"
  image_id      = data.aws_ami.ubuntu.id
  instance_type = var.instance_type

  user_data = local.user_data

  iam_instance_profile {
    arn = aws_iam_instance_profile.instance.arn
  }

  vpc_security_group_ids = [aws_security_group.instance.id]

  block_device_mappings {
    device_name = "/dev/sda1"

    ebs {
      volume_size           = var.root_volume_gb
      volume_type           = "gp3"
      encrypted             = true
      delete_on_termination = true
    }
  }

  # IMDSv2 only (http_tokens = required): the bootstrap script exchanges a token before
  # reading the instance id, and forcing it closes off the SSRF-to-credentials path.
  # Hop limit 2 lets the containers reach the metadata service through the docker bridge.
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "${var.project}-app"
      Role = "web-and-api"
    }
  }

  tag_specifications {
    resource_type = "volume"
    tags = {
      Name = "${var.project}-root"
    }
  }

  lifecycle {
    # The template itself is immutable in the ASG's eyes; a change means an instance
    # refresh, which is the point of using a template at all.
    ignore_changes = [description]
  }
}
