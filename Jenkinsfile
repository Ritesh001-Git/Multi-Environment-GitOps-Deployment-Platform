pipeline {
    agent any

    options {
        timeout(time: 20, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    parameters {
        string(name: 'REPO_URL', defaultValue: '', description: 'GitHub Repo URL')
        string(name: 'BRANCH', defaultValue: 'main')
        string(name: 'DOCKER_IMAGE', defaultValue: '')
    }

    environment {
        APP_EC2_IP = 'YOUR_APP_EC2_IP'
        IMAGE_TAG = "${env.BUILD_NUMBER}"
    }

    stages {

        stage('Clean Workspace') {
            steps {
                deleteDir()
            }
        }

        stage('Clone Repository') {
            steps {
                git url: params.REPO_URL,
                    branch: params.BRANCH
            }
        }

        stage('Validate Repository') {
            steps {
                sh 'test -f Dockerfile'
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

        stage('Push Docker Image') {
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

        stage('Deploy') {
            steps {

                sshagent(credentials: ['app-ec2-ssh-key']) {

                    sh """
                    ssh -o StrictHostKeyChecking=no ubuntu@${APP_EC2_IP} '
                    docker pull ${params.DOCKER_IMAGE}:latest

                    docker stop app || true
                    docker rm app || true

                    docker run -d \
                      --name app \
                      -p 8000:8000 \
                      ${params.DOCKER_IMAGE}:latest
                    '
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