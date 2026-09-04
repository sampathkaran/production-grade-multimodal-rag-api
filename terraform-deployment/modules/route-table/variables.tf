
variable "project_name"{
    default = "multimodal-rag"
}

variable "project_code"{
    default = "AAI-RAG-2026"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID to create subnets in"
}

variable "environment"{}

variable "cidr_block" {}

variable "aws_internet_gw_id"{
  type    = string
  default = null
}

variable "aws_nat_gw_id" {
  type    = string
  default = null
}
