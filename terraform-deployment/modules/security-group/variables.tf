variable "ingress_rules" {
  type = list(object({
    from_port                    = number
    to_port                      = number
    ip_protocol                  = string
    cidr_ipv4                    = optional(string, null)
    referenced_security_group_id = optional(string, null)
  }))

  default = []
}


variable "egress_rules" {
  type = list(object({
    from_port                    = optional(number, null)
    to_port                      = optional(number, null)
    ip_protocol                  = string
    cidr_ipv4                    = optional(string, null)
    referenced_security_group_id = optional(string, null)
  }))

  default = []
}

variable "project_name"{
    default = "multimodal-rag"
}

variable "project_code"{
    default = "AAI-RAG-2026"
}

variable "environment"{}

variable "sg_name" {}

variable "vpc_id" {}