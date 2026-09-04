resource "aws_security_group" "sg" {
    name = "${var.project_name}-${var.environment}-${var.sg_name}"
    vpc_id = var.vpc_id

    tags ={
        Name = "${var.environment}-${var.project_name}-sg"
        Project = var.project_code 
    }
}


resource "aws_vpc_security_group_ingress_rule" "ingress" {
    for_each = {for idx, rule in var.ingress_rules: idx => rule}
    security_group_id = aws_security_group.sg.id
    from_port = each.value.from_port
    to_port = each.value.to_port
    ip_protocol = each.value.ip_protocol
    cidr_ipv4 = each.value.cidr_ipv4
    referenced_security_group_id=each.value.referenced_security_group_id 
    
}

resource "aws_vpc_security_group_egress_rule" "egress" {
    for_each = {for idx, rule in var.egress_rules: idx => rule}
    security_group_id = aws_security_group.sg.id
    from_port = each.value.from_port
    to_port = each.value.to_port
    ip_protocol = each.value.ip_protocol
    cidr_ipv4 = each.value.cidr_ipv4
    referenced_security_group_id = each.value.referenced_security_group_id
 
}
