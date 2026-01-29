# ECS Service for API
resource "aws_ecs_service" "api" {
  name            = "${var.app_name}-api-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.desired_count_api
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.main.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "${var.app_name}-api-container"
    container_port   = var.container_port_api
  }

  depends_on = [
    aws_lb_listener.api,
    aws_efs_mount_target.main
  ]

  tags = {
    Name        = "${var.app_name}-api-service"
    Environment = var.environment
  }
}

# ECS Service for Model
resource "aws_ecs_service" "model" {
  name            = "${var.app_name}-model-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.model.arn
  desired_count   = var.desired_count_model
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.main.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.model.arn
    container_name   = "${var.app_name}-model-container"
    container_port   = var.container_port_model
  }

  depends_on = [
    aws_lb_listener_rule.model,
    aws_efs_mount_target.main
  ]

  tags = {
    Name        = "${var.app_name}-model-service"
    Environment = var.environment
  }
}
