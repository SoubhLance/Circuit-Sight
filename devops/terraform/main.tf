terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

variable "instance_id" {
  description = "Existing CircuitSight EC2 instance ID"
  type        = string
}

data "aws_instance" "circuitsight" {
  instance_id = var.instance_id
}

output "instance_id" {
  value = data.aws_instance.circuitsight.id
}

output "instance_type" {
  value = data.aws_instance.circuitsight.instance_type
}

output "public_ip" {
  value = data.aws_instance.circuitsight.public_ip
}

output "instance_state" {
  value = data.aws_instance.circuitsight.instance_state
}
