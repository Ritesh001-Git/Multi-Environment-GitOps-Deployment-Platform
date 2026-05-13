pipeline {
  agent any

  parameters {
    string(name: 'REPO_URL', defaultValue: '', description: 'GitHub HTTPS clone URL')
    string(name: 'BRANCH', defaultValue: 'main')
    string(name: 'DOCKER_IMAGE', defaultValue: '')
  }

  environment {
    APP_EC2_IP = '44.214.81.126'
    IMAGE_TAG = "${env.BUILD_NUMBER}"
  }

  stages {

    stage('Clone') {
      steps {
        git url: params.REPO_URL, branch: params.BRANCH
      }
    }

    stage('Build Docker Image') {
      steps {
        sh """
          docker build \
            -t ${params.DOCKER_IMAGE}:${IMAGE_TAG} \
            -t ${params.DOCKER_IMAGE}:latest .
        """
      }
    }

    stage('Push to Docker Hub') {
      steps {
        withCredentials([usernamePassword(
          credentialsId: 'dockerhub-creds',
          usernameVariable: 'DOCKER_USER',
          passwordVariable: 'DOCKER_PASS'
        )]) {

          sh '''
            set +x
            echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin
          '''

          sh """
            docker push ${params.DOCKER_IMAGE}:${IMAGE_TAG}
            docker push ${params.DOCKER_IMAGE}:latest
            docker logout
          """
        }
      }
    }

    stage('Deploy to EC2') {
      steps {
        sshagent(credentials: ['app-ec2-ssh-key']) {
          sh """
            ssh -o StrictHostKeyChecking=no ubuntu@${APP_EC2_IP} \
            'bash /home/ubuntu/gitops-platform/deploy.sh'
          """
        }
      }
    }

    stage('Health Check') {
      steps {
        sh """
          for i in {1..10}; do
            curl --fail http://${APP_EC2_IP}:8000/health && exit 0
            sleep 10
          done
          exit 1
        """
      }
    }
  }

  post {
    success {
      echo 'Deployment successful'
    }

    failure {
      echo 'Pipeline failed'
    }

    always {
      sh 'docker image prune -f || true'
    }
  }
}