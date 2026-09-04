# Create a route table with a route pointing to IGW

resource "aws_route_table" "rt"{
    vpc_id = var.vpc_id

    route{
        cidr_block = var.cidr_block
        gateway_id = var.aws_internet_gw_id
        nat_gateway_id = var.aws_nat_gw_id
    }

    tags = {
        Name = "${var.project_name}-${var.environment}-rt"
        Project = var.project_code
    }  
}
