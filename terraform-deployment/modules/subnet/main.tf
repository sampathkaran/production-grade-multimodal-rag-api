resource "aws_subnet" "public_subnet" {
    for_each = var.public_subnet_cidrs
    vpc_id = var.vpc_id
    cidr_block = each.value
    availability_zone = each.key
    map_public_ip_on_launch = true

    tags = {
        Name = "${var.environment}-${var.project_name}-${each.key}-public-subnet"
        Project = var.project_code
    }
}

resource "aws_subnet" "private_subnet" {
    for_each = var.private_subnet_cidrs
    vpc_id = var.vpc_id
    cidr_block = each.value
    availability_zone = each.key
    map_public_ip_on_launch = true

    tags = {
        Name = "${var.environment}-${var.project_name}-${each.key}-private-subnet"
        Project = var.project_code
    }
}