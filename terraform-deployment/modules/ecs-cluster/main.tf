resource "aws_ecs_cluster" "ecs_cluster" {
    name = var.ecs_cluster_name

    tags = {
        Name = "${var.project_name}-ecs"
        Project = var.project_code
    }  
  
}