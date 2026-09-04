variable "project_name"{
    default = "multimodal-rag"
}

variable "project_code"{
    default = "AAI-RAG-2026"
}

variable "environment"{}

variable "private_subnet_ids" {
  
}

variable "ecs_sg_id" {
  
}

variable "ecs_cluster_id" {
  
}


variable "aws_ecs_task_definition_arn" {
  
}

variable "service_name" {
  
}

variable "attach_load_balancer" {
    default = true
}

variable "target_group_arn" {
    default = ""
}

variable "container_name" {
    default = ""
}

variable "container_port" {
    default = 8000
}