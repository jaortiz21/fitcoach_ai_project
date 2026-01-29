# EFS File System
resource "aws_efs_file_system" "main" {
  creation_token = "${var.app_name}-efs"
  encrypted      = true

  tags = {
    Name        = "${var.app_name}-efs"
    Environment = var.environment
  }
}

# EFS Mount Targets
resource "aws_efs_mount_target" "main" {
  count           = length(aws_subnet.private[*].id)
  file_system_id  = aws_efs_file_system.main.id
  subnet_id       = aws_subnet.private[count.index].id
  security_groups = [aws_security_group.main.id]
}

# EFS Access Point for API
resource "aws_efs_access_point" "api" {
  file_system_id = aws_efs_file_system.main.id
  root_directory {
    path = "/api"
  }

  posix_user {
    gid = 1000
    uid = 1000
  }

  tags = {
    Name        = "${var.app_name}-efs-api-ap"
    Environment = var.environment
  }
}

# EFS Access Point for Model
resource "aws_efs_access_point" "model" {
  file_system_id = aws_efs_file_system.main.id
  root_directory {
    path = "/model"
  }

  posix_user {
    gid = 1000
    uid = 1000
  }

  tags = {
    Name        = "${var.app_name}-efs-model-ap"
    Environment = var.environment
  }
}
