variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "app_name" {
  description = "Application name"
  type        = string
  default     = "fitcoach-ai"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "api_image" {
  description = "Docker image URI for API container"
  type        = string
}

variable "model_image" {
  description = "Docker image URI for model container"
  type        = string
}

variable "container_port_api" {
  description = "Container port for API"
  type        = number
  default     = 5000
}

variable "container_port_model" {
  description = "Container port for model service"
  type        = number
  default     = 8000
}

variable "api_cpu" {
  description = "CPU units for API service"
  type        = number
  default     = 256
}

variable "api_memory" {
  description = "Memory (MB) for API service"
  type        = number
  default     = 512
}

variable "model_cpu" {
  description = "CPU units for model service"
  type        = number
  default     = 512
}

variable "model_memory" {
  description = "Memory (MB) for model service"
  type        = number
  default     = 1024
}

variable "desired_count_api" {
  description = "Desired number of API tasks"
  type        = number
  default     = 1
}

variable "desired_count_model" {
  description = "Desired number of model tasks"
  type        = number
  default     = 1
}

variable "enable_nat_gateway" {
  description = "Enable NAT Gateway for outbound internet access from private subnets"
  type        = bool
  default     = false
}
