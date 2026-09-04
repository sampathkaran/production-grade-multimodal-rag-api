# define provider to interact with AWS

terraform {
  required_version = "~> 1.15.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.60.0"
    }
  }
}


provider "aws" {
  profile = "default" # use the default profile from my local
  region  = "us-east-1"
}



