module "vpc" {
  source       = "../modules/vpc"
  vpc_cidr     = "10.0.0.0/16"
  project_name = "multimodal-rag"
  vpc_name     = "multimodal-rag-vpc"
  project_code = "AAI-RAG-2026"
  environment  = "dev"
}

module "subnet" {
  source = "../modules/subnet"
  vpc_id = module.vpc.vpc_id
  public_subnet_cidrs = {
    "us-east-1a" = "10.0.0.0/20"
    "us-east-1b" = "10.0.16.0/20"
  }
  private_subnet_cidrs = {
    "us-east-1a" = "10.0.32.0/20"
    "us-east-1b" = "10.0.48.0/20"
  }

  project_name = "multimodal-rag"
  project_code = "AAI-RAG-2026"
  environment  = "dev"

}


module "igw" {
  source = "../modules/internet-gateway"
  vpc_id = module.vpc.vpc_id
}

module "public_rt" {
  source             = "../modules/route-table"
  vpc_id             = module.vpc.vpc_id
  environment        = "dev"
  cidr_block         = "0.0.0.0/0"
  aws_internet_gw_id = module.igw.igw_id
}

module "public-rt-assoc" {
  source         = "../modules/route-table-assoc"
  subnet_ids     = module.subnet.public_subnet_ids
  route_table_id = module.public_rt.route_table_id
}

module "natgw"{
  source = "../modules/nat-gateway"
  environment = "dev"
  public_subnet_id = module.subnet.public_subnet_ids["us-east-1a"]
}

module "private_rt" {
  source             = "../modules/route-table"
  vpc_id             = module.vpc.vpc_id
  environment        = "dev"
  cidr_block         = "0.0.0.0/0"
  aws_nat_gw_id      = module.natgw.natgw_id 
}

module "private-rt-assoc" {
  source         = "../modules/route-table-assoc"
  subnet_ids     = module.subnet.private_subnet_ids
  route_table_id = module.private_rt.route_table_id
}

#Create an ECS cluster

module "redis_sg" {
  source =  "../modules/security-group"
  project_name = "multimodal-rag"
  environment  = "dev"
  vpc_id       = module.vpc.vpc_id
  sg_name      = "redis-sg"
  
  ingress_rules = [
    {
      from_port = 6379
      to_port = 6379
      ip_protocol = "tcp"
      referenced_security_group_id = module.ecs_sg.aws_security_group_id
    
  }]
}


module "redis_cluster" {
  source = "../modules/elasticache"
  cluster_id = "redis"
  private_subnet_ids = [module.subnet.private_subnet_ids["us-east-1a"], module.subnet.private_subnet_ids["us-east-1b"]]
  environment = "dev"
  node_type = "cache.t3.micro"
  engine= "redis"
  port = 6379
  num_cache_nodes= 1
  parameter_group_name="default.redis7"
  security_group_ids = [module.redis_sg.aws_security_group_id]
}


# Create ECS

module "cw" {
  source = "../modules/aws-cloudwatch"
}

module "ecs_cluster" {
  source = "../modules/ecs-cluster"
  ecs_cluster_name = "multimodal-rag-ecs"
  
}

module "ecs_sg" {
  source =  "../modules/security-group"
  project_name = "multimodal-rag"
  environment  = "dev"
  vpc_id       = module.vpc.vpc_id
  sg_name      = "ecs-sg"
  
  ingress_rules = [
    {
      from_port = 8000
      to_port = 8000
      ip_protocol = "tcp"
      referenced_security_group_id = module.alb_sg.aws_security_group_id 
  }]
  egress_rules = [{
      ip_protocol = "-1"
      cidr_ipv4   = "0.0.0.0/0"

  }]
}

module "ecs_task_definition_api"{
  source = "../modules/ecs-task-definition"
  name = "api"
  environment = "dev"
  log_group_name = module.cw.log_group_name
  container_definitions_file = "ecs-task-definitions/multimodal-rag-api.json"
}


module "ecs_task_definition_celery"{
  source = "../modules/ecs-task-definition"
  name = "celery"
  environment = "dev"
  log_group_name = module.cw.log_group_name
  container_definitions_file = "ecs-task-definitions/multimodal-rag-celery.json"
}


module "ecs_service_api"{
  source = "../modules/ecs-service"
  service_name = "api"
  ecs_cluster_id         = module.ecs_cluster.ecs_cluster_id
  aws_ecs_task_definition_arn = module.ecs_task_definition_api.task_definition_arn
  private_subnet_ids =values(module.subnet.private_subnet_ids)
  ecs_sg_id = module.ecs_sg.aws_security_group_id
  environment = "dev"

  attach_load_balancer = true                              # 👈 API gets ALB
  target_group_arn     = module.alb.target_group_arn
  container_name        = "multimodal-rag-api"
  container_port         = 8000

  depends_on = [module.alb]
}

module "ecs_service_celery"{
  source = "../modules/ecs-service"
  service_name = "celery"
  ecs_cluster_id         = module.ecs_cluster.ecs_cluster_id
  aws_ecs_task_definition_arn = module.ecs_task_definition_celery.task_definition_arn
  private_subnet_ids =values(module.subnet.private_subnet_ids)
  ecs_sg_id = module.ecs_sg.aws_security_group_id
  environment = "dev"

  attach_load_balancer = false
}
 
# Create ALB

module "alb_sg" {
  source = "../modules/security-group"
  project_name = "multimodal-rag"
  environment  = "dev"
  vpc_id       = module.vpc.vpc_id
  sg_name      = "alb-sg"
  
  ingress_rules = [
    {
      from_port = 80
      to_port = 80
      ip_protocol = "tcp"
      cidr_ipv4 = "0.0.0.0/0"
      referenced_security_group_id = null
    
  }]
  egress_rules = [
    {
      ip_protocol = "-1"
      cidr_ipv4   = "0.0.0.0/0"
    }
  ]
  
}

module "alb" {
  source = "../modules/aws-alb"
  alb_name = "multimodal-rag-alb"
  alb_security_groups = [module.alb_sg.aws_security_group_id]
  alb_subnets = values(module.subnet.public_subnet_ids)
  environment = "dev"
  container_port     = 8000
  health_check_path  = "/"
  vpc_id = module.vpc.vpc_id
}

# create cloudfront distribution

module "cloudfront" {
  source       = "../modules/aws-cloudfront"
  project_name = "multimodal-rag"
  environment  = "dev"
  alb_dns_name = module.alb.alb_dns_name
  depends_on = [module.alb]
}