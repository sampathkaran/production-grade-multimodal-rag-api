variable "public_subnet_cidrs"{
    description = "Specify the public subnet cidr as dict key value pair"
    type = map(string)
}

variable "private_subnet_cidrs"{
    description = "Specify the private sbunet cidr as dict key value pair"
    type = map(string)
}

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