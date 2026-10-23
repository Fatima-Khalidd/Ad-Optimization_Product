terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.60.0"
    }
  }

  # State stays in a local terraform.tfstate for the lab. To move it to S3, create a
  # versioned bucket and replace this block with a backend "s3" configuration.
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project           = var.project
      Course            = "CSC418 DevOps for Cloud Computing"
      Lab               = "Mid-Term Lab Exam"
      ManagedBy         = "terraform"
      Owner             = var.owner_tag
      DecommissionAfter = var.decommission_after
    }
  }
}
