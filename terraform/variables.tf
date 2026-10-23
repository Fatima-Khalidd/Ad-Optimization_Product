variable "region" {
  description = "AWS region for the stack. ap-south-1 is closest to Lahore."
  type        = string
  default     = "ap-south-1"
}

variable "project" {
  description = "Name prefix for every resource."
  type        = string
  default     = "ad-optimizer"
}

variable "owner_tag" {
  description = "Your roll number, so the examiner can see whose lab this is."
  type        = string
  default     = "fa22-xxxxx"
}

variable "decommission_after" {
  description = "Reminder tag. Terraform will not act on it; delete the stack with `terraform destroy`."
  type        = string
  default     = "2026-11-01"
}

variable "repo_url" {
  description = "Clone URL the instances pull at boot."
  type        = string
  default     = "https://github.com/Fatima-Khalidd/Ad-Optimization_Product.git"
}

variable "branch" {
  description = "Branch the launch template checks out. Must contain docker-compose.yml — see terraform.tfvars.example."
  type        = string
  default     = "devops-lab"
}

variable "instance_type" {
  description = <<-EOT
    t3.medium, not t2.micro: the boot step builds the Next.js frontend and installs the
    pandas/numpy stack, which needs ~4 GB. t2.micro (1 GB) gets OOM-killed mid-build.
    Two t3.mediums for the mandatory minimum of two targets cost roughly $0.06-0.08 each.
  EOT
  type        = string
  default     = "t3.medium"
}

variable "root_volume_gb" {
  description = " gp3 so the images, build cache and Docker volumes fit."
  type        = number
  default     = 40
}

variable "min_size" {
  description = "The paper asks for two application instances, so the floor is 2."
  type        = number
  default     = 2
}

variable "max_size" {
  description = "Upper bound for the CPU target-tracking policy."
  type        = number
  default     = 4
}

variable "desired_capacity" {
  type    = number
  default = 2
}

variable "app_port" {
  description = "Container port the Compose stack publishes the Next.js frontend on."
  type        = number
  default     = 3000
}

variable "api_port" {
  description = "Container port the FastAPI service is published on, for direct diagnostics."
  type        = number
  default     = 8000
}

variable "health_check_path" {
  description = "Probed by the target group. /api/health is rewritten by Next to the API, so a 200 here means all three containers are healthy."
  type        = string
  default     = "/api/health"
}

variable "cpu_target_percentage" {
  description = "Scale out above this average CPU, scale in below it."
  type        = number
  default     = 60
}

variable "ssh_cidrs" {
  description = <<-EOT
    CIDRs allowed to reach port 22. Empty by default: shell access goes through Systems
    Manager Session Manager (the instance role has AmazonSSMManagedInstanceCore), which
    needs no key pair and opens no inbound port.
    EOT
  type        = list(string)
  default     = []
}

variable "rate_limit_storage_uri" {
  description = <<-EOT
    Optional shared store for the login rate limiter, e.g. redis://:pass@cache.xxx.cache.amazonaws.com:6379/0.
    Left empty, each instance keeps counters in its own process memory, which is correct
    for one node and approximate for an Auto Scaling Group.
  EOT
  type        = string
  default     = ""
}
