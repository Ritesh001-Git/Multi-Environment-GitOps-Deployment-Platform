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

# variable "your_ip" {
#   description = "Your public IP in CIDR format (example: 1.2.3.4/32)"
# }

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
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Jenkins UI"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "Grafana"
    from_port   = 3001
    to_port     = 3001
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "Prometheus"
    from_port   = 9090
    to_port     = 9090
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "Alertmanager"
    from_port   = 9093
    to_port     = 9093
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "cAdvisor"
    from_port   = 8081
    to_port     = 8081
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "Node Exporter"
    from_port   = 9100
    to_port     = 9100
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
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
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Allow Jenkins to SSH into app server"
    from_port       = 22
    to_port         = 22
    protocol        = "tcp"
    security_groups = [aws_security_group.jenkins_sg.id]
  }

  ingress {
    description = "Frontend application"
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Backend application"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "For app run"
    from_port   = 8001
    to_port     = 8010
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "Node Exporter"
    from_port   = 9100
    to_port     = 9100
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
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

# ─────────────────────────────────────────────────────────────
# Jenkins EC2 Instance
# ─────────────────────────────────────────────────────────────

resource "aws_instance" "jenkins_ec2" {
  ami                    = "ami-0c7217cdde317cfec"
  instance_type          = "t3.small"
  key_name               = var.key_pair_name
  vpc_security_group_ids = [aws_security_group.jenkins_sg.id]
  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }
  tags = {
    Name = "jenkins-master"
  }
}

# ─────────────────────────────────────────────────────────────
# App EC2 Instance
# ─────────────────────────────────────────────────────────────

resource "aws_instance" "app_ec2" {
  ami                    = "ami-0c7217cdde317cfec"
  instance_type          = "t3.micro"
  key_name               = var.key_pair_name
  vpc_security_group_ids = [aws_security_group.app_sg.id]

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