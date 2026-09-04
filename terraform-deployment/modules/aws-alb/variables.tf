variable "alb_name" {}
variable "alb_security_groups" {}
variable "alb_subnets" {}
variable "project_name"{
    default = "multimodal-rag"
}

variable "project_code"{
    default = "AAI-RAG-2026"
}

variable "environment"{
    default = "dev"
}

variable "container_port" {
    default = 8000
}

variable "health_check_path" {
    default = "/health"
}

variable "vpc_id" {
    
}