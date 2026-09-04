resource "aws_route_table_association" "rt_assoc" {
  for_each = var.subnet_ids

  subnet_id = each.value
  route_table_id = var.route_table_id
}


