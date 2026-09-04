# modules/ecs/main.tf
resource "aws_ecs_service" "service" {
  name            = "${var.project_name}-${var.environment}-${var.service_name}"
  cluster         = var.ecs_cluster_id
  task_definition = var.aws_ecs_task_definition_arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.ecs_sg_id]     # 👈 the link happens HERE
    assign_public_ip = false
  }

  dynamic "load_balancer" {
    for_each = var.attach_load_balancer ? [1] : []   # 👈 only creates this block if true
    content {
      target_group_arn = var.target_group_arn
      container_name    = var.container_name
      container_port    = var.container_port
    }
  }
}