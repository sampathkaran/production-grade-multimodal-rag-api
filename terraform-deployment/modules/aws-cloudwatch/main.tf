resource "aws_cloudwatch_log_group" "cw" {
  name              = "/ecs/${var.project_name}-${var.environment}-cw"
  retention_in_days = 3   # keeps cost low while you're actively debugging
}