# modules/alb/outputs.tf
output "alb_dns_name" {
  value = aws_lb.alb.dns_name    # this is the actual URL you'll visit, e.g. multimodal-rag-alb-123.us-east-1.elb.amazonaws.com
}
output "target_group_arn" {
  value = aws_lb_target_group.alb_target_group.arn   # needed by the ECS service, so it knows where to register itself
}