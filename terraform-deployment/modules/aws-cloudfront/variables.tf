variable "alb_dns_name" {
  type        = string
  description = "DNS name of the ALB to use as CloudFront origin"
}

variable "environment" {
    default = "dev"
}

variable "project_name"{
    default = "multimodal-rag"
}

variable "project_code"{
    default = "AAI-RAG-2026"
}