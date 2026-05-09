# ─────────────────────────────────────────────────────────────────────────────
#  Terraform · EC2 Instance for Frontend + Backend
#  Provider: AWS  |  Instance: t2.micro (Free Tier)
# ─────────────────────────────────────────────────────────────────────────────

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ── Variables ─────────────────────────────────────────────────────────────────
variable "aws_region"   { default = "us-east-1" }
variable "key_pair_name" {
  description = "Name of your existing EC2 key pair for SSH access"
}
variable "your_ip" {
  description = "Your public IP for SSH access (e.g. 1.2.3.4/32)"
}

# ── Security Group ────────────────────────────────────────────────────────────
resource "aws_security_group" "gitops_sg" {
  name        = "gitops-platform-sg"
  description = "GitOps Platform security group"

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.your_ip]
  }

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "React Frontend"
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "FastAPI Backend"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "gitops-platform-sg" }
}

# ── EC2 Instance ──────────────────────────────────────────────────────────────
resource "aws_instance" "gitops_server" {
  ami                    = "ami-0c7217cdde317cfec"  # Ubuntu 22.04 us-east-1
  instance_type          = "t3.micro"
  key_name               = var.key_pair_name
  vpc_security_group_ids = [aws_security_group.gitops_sg.id]

  # Bootstrap script: install Node.js + Python on launch
  user_data = <<-EOF
    #!/bin/bash
    apt-get update -y
    apt-get install -y nodejs npm python3 python3-pip git curl

    # Install Node 20
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs

    echo "Bootstrap complete" > /tmp/bootstrap.log
  EOF

  tags = { Name = "gitops-platform" }
}

# ── Elastic IP (static public IP) ─────────────────────────────────────────────
resource "aws_eip" "gitops_eip" {
  instance = aws_instance.gitops_server.id
  domain   = "vpc"
  tags     = { Name = "gitops-eip" }
}

# ── Outputs ───────────────────────────────────────────────────────────────────
output "ec2_public_ip" {
  description = "Public IP of EC2 instance"
  value       = aws_eip.gitops_eip.public_ip
}

output "ssh_command" {
  description = "SSH into your instance"
  value       = "ssh -i ~/.ssh/${var.key_pair_name}.pem ubuntu@${aws_eip.gitops_eip.public_ip}"
}

output "frontend_url" {
  description = "React frontend URL"
  value       = "http://${aws_eip.gitops_eip.public_ip}:3000"
}

output "backend_url" {
  description = "FastAPI backend URL"
  value       = "http://${aws_eip.gitops_eip.public_ip}:8000"
}
