# terraform/main.tf

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ─────────────────────────────────────────────────────────────
# AWS Provider
# ─────────────────────────────────────────────────────────────

provider "aws" {
  region = "us-east-1"
}

# ─────────────────────────────────────────────────────────────
# Variables
# ─────────────────────────────────────────────────────────────

variable "key_pair_name" {
  default = "gitops-key"
}

variable "admin_cidr" {
  description = "Trusted administrator public IP in CIDR form (for example 203.0.113.10/32)"
  type        = string
}

variable "app_client_cidr" {
  description = "CIDR allowed to reach the HTTP ingress; keep restricted until TLS and API authentication are enabled"
  type        = string
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# ─────────────────────────────────────────────────────────────
# Security Group: Jenkins
# ─────────────────────────────────────────────────────────────

resource "aws_security_group" "jenkins_sg" {
  name        = "jenkins-sg"
  description = "Security group for Jenkins server"

  ingress {
    description = "SSH from your Mac"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }

  ingress {
    description = "Jenkins UI"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }
  ingress {
    description = "Grafana"
    from_port   = 3001
    to_port     = 3001
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }
  ingress {
    description = "Prometheus"
    from_port   = 9090
    to_port     = 9090
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }
  ingress {
    description = "Alertmanager"
    from_port   = 9093
    to_port     = 9093
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }

  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "jenkins-sg"
  }
}

# ─────────────────────────────────────────────────────────────
# Security Group: App Server
# ─────────────────────────────────────────────────────────────

resource "aws_security_group" "app_sg" {
  name        = "app-sg"
  description = "Security group for application server"

  ingress {
    description = "SSH from your Mac"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }

  ingress {
    description     = "Allow Jenkins to SSH into app server"
    from_port       = 22
    to_port         = 22
    protocol        = "tcp"
    security_groups = [aws_security_group.jenkins_sg.id]
  }

  ingress {
    description = "Traefik HTTP ingress"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = [var.app_client_cidr]
  }

  ingress {
    description     = "FastAPI metrics through Traefik from Jenkins/Prometheus"
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [aws_security_group.jenkins_sg.id]
  }

  ingress {
    description     = "K3s monitoring NodePorts from Jenkins/Prometheus"
    from_port       = 30090
    to_port         = 30091
    protocol        = "tcp"
    security_groups = [aws_security_group.jenkins_sg.id]
  }

  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "app-sg"
  }
}

resource "aws_security_group_rule" "jenkins_api_from_app" {
  description              = "FastAPI backend can trigger and poll Jenkins"
  type                     = "ingress"
  from_port                = 8080
  to_port                  = 8080
  protocol                 = "tcp"
  security_group_id        = aws_security_group.jenkins_sg.id
  source_security_group_id = aws_security_group.app_sg.id
}

# ─────────────────────────────────────────────────────────────
# Jenkins EC2 Instance
# ─────────────────────────────────────────────────────────────

resource "aws_instance" "jenkins_ec2" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = "t3.small"
  key_name               = var.key_pair_name
  vpc_security_group_ids = [aws_security_group.jenkins_sg.id]
  root_block_device {
    volume_size = 20
    volume_type = "gp3"
    encrypted   = true
  }
  metadata_options {
    http_tokens = "required"
  }
  tags = {
    Name = "jenkins-master"
  }
}

# ─────────────────────────────────────────────────────────────
# App EC2 Instance
# ─────────────────────────────────────────────────────────────

resource "aws_instance" "app_ec2" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = "t3.small"
  key_name               = var.key_pair_name
  vpc_security_group_ids = [aws_security_group.app_sg.id]

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
    encrypted   = true
  }

  metadata_options {
    http_tokens = "required"
  }

  tags = {
    Name = "app-server"
  }
}

# ─────────────────────────────────────────────────────────────
# Elastic IPs
# ─────────────────────────────────────────────────────────────

resource "aws_eip" "jenkins_eip" {
  instance = aws_instance.jenkins_ec2.id
  domain   = "vpc"

  depends_on = [aws_instance.jenkins_ec2]
}

resource "aws_eip" "app_eip" {
  instance = aws_instance.app_ec2.id
  domain   = "vpc"

  depends_on = [aws_instance.app_ec2]
}

# ─────────────────────────────────────────────────────────────
# Outputs
# ─────────────────────────────────────────────────────────────

output "jenkins_ip" {
  value = aws_eip.jenkins_eip.public_ip
}

output "app_ip" {
  value = aws_eip.app_eip.public_ip
}

output "jenkins_private_ip" {
  value = aws_instance.jenkins_ec2.private_ip
}

output "app_private_ip" {
  value = aws_instance.app_ec2.private_ip
}

output "jenkins_ssh" {
  value = "ssh -i ~/.ssh/gitops-key.pem ubuntu@${aws_eip.jenkins_eip.public_ip}"
}

output "app_ssh" {
  value = "ssh -i ~/.ssh/gitops-key.pem ubuntu@${aws_eip.app_eip.public_ip}"
}
