resource "aws_elasticache_subnet_group" "redis" {
  name       = "${var.project_name}-${var.environment}-redis-subnet-group"
  subnet_ids = var.private_subnet_ids
}


resource "aws_elasticache_cluster" "redis" {
    cluster_id = "${var.project_name}-${var.environment}-${var.cluster_id}"
    engine     = var.engine
    node_type  = var.node_type
    num_cache_nodes = var.num_cache_nodes
    parameter_group_name =  var.parameter_group_name
    port = var.port
    subnet_group_name = aws_elasticache_subnet_group.redis.id
    security_group_ids = var.security_group_ids


    tags = {
        Name = "${var.project_name}-${var.environment}-rt"
        Project = var.project_code
    }
}