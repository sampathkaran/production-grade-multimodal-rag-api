resource "aws_vpc" "vpc" {
  cidr_block = var.vpc_cidr

tags = {
        Name = "${var.environment}-${var.project_name}-vpc"
        Project = var.project_code
    }
}





