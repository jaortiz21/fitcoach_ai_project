# Application Load Balancer
resource "aws_lb" "main" {
  name               = "${var.app_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.main.id]
  subnets            = aws_subnet.public[*].id

  tags = {
    Name        = "${var.app_name}-alb"
    Environment = var.environment
  }
}

# ALB Target Group for API
resource "aws_lb_target_group" "api" {
  name        = "${var.app_name}-api-tg"
  port        = var.container_port_api
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 3
    interval            = 30
    path                = "/"
    matcher             = "200"
  }

  tags = {
    Name        = "${var.app_name}-api-tg"
    Environment = var.environment
  }
}

# ALB Target Group for Model Service
resource "aws_lb_target_group" "model" {
  name        = "${var.app_name}-model-tg"
  port        = var.container_port_model
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 3
    interval            = 30
    path                = "/health"
    matcher             = "200"
  }

  tags = {
    Name        = "${var.app_name}-model-tg"
    Environment = var.environment
  }
}

# ALB Listener for API
resource "aws_lb_listener" "api" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# ALB Listener Rule for Model Service
resource "aws_lb_listener_rule" "model" {
  listener_arn = aws_lb_listener.api.arn
  priority     = 1

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.model.arn
  }

  condition {
    path_pattern {
      values = ["/model/*"]
    }
  }
}
