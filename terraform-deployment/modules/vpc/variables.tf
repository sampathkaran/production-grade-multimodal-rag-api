variable "vpc_cidr" {
  description = "Specify CIDR range of VPC"
  type = string
  default = "10.0.0.0/16"
}

variable "vpc_name" {
    description = "Name of the VPC"
    type = string
    default = "multimodal-rag-vpc"
}

variable "project_name"{
    default = "multimodal-rag"
}

variable "project_code"{
    default = "AAI-RAG-2026"
}

variable "environment"{}

