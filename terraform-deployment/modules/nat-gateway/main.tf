# create a EIP for NAT Gatewat
resource "aws_eip" "nat" {
    domain = "vpc"

    tags = {
        Name = "${var.project_name}-${var.environment}-eip"
        Project = var.project_code
    }
}



resource "aws_nat_gateway" "nat"{
    allocation_id = aws_eip.nat.id
    subnet_id = var.public_subnet_id

    tags = {
        Name = "${var.project_name}-${var.environment}-nat"
        Project = var.project_code
    } 
}




# 
