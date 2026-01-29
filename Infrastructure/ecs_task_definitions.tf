# CloudWatch Log Group for API
resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.app_name}-api"
  retention_in_days = 7

  tags = {
    Name        = "${var.app_name}-api-logs"
    Environment = var.environment
  }
}

# CloudWatch Log Group for Model Service
resource "aws_cloudwatch_log_group" "model" {
  name              = "/ecs/${var.app_name}-model"
  retention_in_days = 7

  tags = {
    Name        = "${var.app_name}-model-logs"
    Environment = var.environment
  }
}

# ECS Task Definition for API
resource "aws_ecs_task_definition" "api" {
  family                   = "${var.app_name}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "${var.app_name}-api-container"
      image     = var.api_image
      essential = true
      portMappings = [
        {
          containerPort = var.container_port_api
          hostPort      = var.container_port_api
          protocol      = "tcp"
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.api.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
      mountPoints = [
        {
          sourceVolume  = "efs-storage"
          containerPath = "/app/storage"
          readOnly      = false
        }
      ]
    }
  ])

  volume {
    name = "efs-storage"
    efs_volume_configuration {
      file_system_id = aws_efs_file_system.main.id
      root_directory = "/api"
    }
  }

  tags = {
    Name        = "${var.app_name}-api-task"
    Environment = var.environment
  }
}

# ECS Task Definition for Model Service
resource "aws_ecs_task_definition" "model" {
  family                   = "${var.app_name}-model"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.model_cpu
  memory                   = var.model_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "${var.app_name}-model-container"
      image     = var.model_image
      essential = true
      portMappings = [
        {
          containerPort = var.container_port_model
          hostPort      = var.container_port_model
          protocol      = "tcp"
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.model.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
      mountPoints = [
        {
          sourceVolume  = "efs-storage"
          containerPath = "/app/models"
          readOnly      = false
        }
      ]
    }
  ])

  volume {
    name = "efs-storage"
    efs_volume_configuration {
      file_system_id = aws_efs_file_system.main.id
      root_directory = "/model"
    }
  }

  tags = {
    Name        = "${var.app_name}-model-task"
    Environment = var.environment
  }
}
