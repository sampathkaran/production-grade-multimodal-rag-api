variable "vpc_id" {
  type        = string
  description = "VPC ID to create subnets in"
}

variable "project_name"{
    default = "multimodal-rag"
}

variable "project_code"{
    default = "AAI-RAG-2026"
}