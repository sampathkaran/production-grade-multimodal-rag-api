resource "aws_lb" "alb" {
    name = "${var.project_name}-${var.environment}-alb"
    internal = false # to make this accessible from the internet
    load_balancer_type = "application"
    security_groups = var.alb_security_groups 
    subnets = var.alb_subnets

    tags = {
    Name = "${var.project_name}-${var.environment}-alb"
  }

}

# Create a target group for the alb
resource "aws_lb_target_group" "alb_target_group" {
    name ="${var.project_name}-${var.environment}-tg-api"
    port = var.container_port 
    protocol = "HTTP"
    vpc_id = var.vpc_id
    target_type = "ip"

    health_check {
        path = var.health_check_path
        protocol = "HTTP"
        matcher = "200"
        interval = 30  # check every 30 seconds 
        timeout = 5  # give up after 5 seconds 
        healthy_threshold = 2  # 2 successful checks required
        unhealthy_threshold = 2  # 2 failed checks required
    
    }

    deregistration_delay = 30  # give time for the container to drain the requests
    tags = {
        Name = "${var.project_name}-${var.environment}-tg-api"
    }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.alb.arn
  port = 80
  protocol = "HTTP"

  default_action {
    type = "forward"
    target_group_arn = aws_lb_target_group.alb_target_group.arn
}
}

