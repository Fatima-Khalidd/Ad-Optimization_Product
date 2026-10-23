output "alb_dns_name" {
  description = "Point the browser here. This is the URL the exam asks you to demonstrate."
  value       = aws_lb.app.dns_name
}

output "app_url" {
  value = "http://${aws_lb.app.dns_name}/"
}

output "health_url" {
  description = "Reports the serving instance id, so you can show the balancer distributing requests."
  value       = "http://${aws_lb.app.dns_name}${var.health_check_path}"
}

output "target_group_arn" {
  value = aws_lb_target_group.app.arn
}

output "autoscaling_group_name" {
  value = aws_autoscaling_group.app.name
}

output "launch_template_id" {
  value = aws_launch_template.app.id
}

output "instance_security_group_id" {
  description = "This group accepts 3000 and 8000 only from the ALB's group - worth showing in the viva."
  value       = aws_security_group.instance.id
}

output "session_manager_command" {
  description = "Shell onto a running instance without a key pair or an open port 22."
  value       = "aws ssm start-session --target <instance-id> --region ${var.region}"
}

output "verify_command" {
  value = "bash scripts/verify-load-balancing.sh ${aws_lb.app.dns_name}"
}

output "destroy_command" {
  description = "Run this the same day as the demo. Two t3.mediums plus an ALB bill roughly $0.20/hour."
  value       = "terraform -chdir=terraform destroy"
}
