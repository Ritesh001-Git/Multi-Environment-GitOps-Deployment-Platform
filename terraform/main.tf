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
  instance_type          = "t3.micro"
  key_name               = var.key_pair_name
  vpc_security_group_ids = [aws_security_group.jenkins_sg.id]

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

output "jenkins_ssh" {
  value = "ssh -i ~/.ssh/gitops-key.pem ubuntu@${aws_eip.jenkins_eip.public_ip}"
}

output "app_ssh" {
  value = "ssh -i ~/.ssh/gitops-key.pem ubuntu@${aws_eip.app_eip.public_ip}"
}