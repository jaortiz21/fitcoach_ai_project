terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  backend "s3" {
    bucket              = "tf-state-zitro"
    key                 = "fitcoach/statefile.tf"
    region              = "us-east-2"
    profile             = "personal-admin"

    encrypt             = true
  }
}

provider "aws" {
  region  = var.aws_region
  profile = "personal-admin"
}

