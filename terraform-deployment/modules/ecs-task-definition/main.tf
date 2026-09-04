# projects/ragapp/main.tf

data "aws_iam_role" "ecs_execution" {
  name = "ecsTaskExecutionRole"
}


resource "aws_ecs_task_definition" "api" {
  family                   = "${var.project_name}-${var.environment}-${var.name}"
  requires_compatibilities  = ["FARGATE"]
  network_mode              = "awsvpc"
  cpu                       = "1024"
  memory                    = "3072"
  execution_role_arn        = data.aws_iam_role.ecs_execution.arn
  task_role_arn             = data.aws_iam_role.ecs_execution.arn
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture         = "X86_64"
  }

  container_definitions = templatefile("${path.root}/${var.container_definitions_file}", {
    region          = "us-east-1"
    log_group                 = var.log_group_name
  })
}