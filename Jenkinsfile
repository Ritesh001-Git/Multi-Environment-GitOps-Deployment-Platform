pipeline {

    agent any

    options {
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timestamps()
        disableConcurrentBuilds()
    }

    parameters {

        string(
            name: 'REPO_URL',
            defaultValue: '',
            description: 'GitHub Repository URL'
        )

        string(
            name: 'BRANCH',
            defaultValue: 'main',
            description: 'Git branch'
        )

        string(
            name: 'DOCKER_IMAGE',
            defaultValue: '',
            description: 'Docker image name'
        )
    }

    environment {

        APP_EC2_IP    = '98.87.239.109'

        IMAGE_TAG     = "${BUILD_NUMBER}"

        K8S_NAMESPACE = 'gitops'
        K8S_DEPLOY    = 'gitops-app'
    }

    stages {

        // ─────────────────────────────────────────────────────────────
        // 1. Clean Workspace
        // ─────────────────────────────────────────────────────────────
        stage('Clean Workspace') {
            steps {
                deleteDir()
            }
        }

        // ─────────────────────────────────────────────────────────────
        // 2. Clone Repository
        // ─────────────────────────────────────────────────────────────
        stage('Clone Repository') {

            steps {

                git(
                    url: params.REPO_URL,
                    branch: params.BRANCH
                )

                script {

                    env.SHORT_COMMIT = sh(
                        script: 'git rev-parse --short HEAD',
                        returnStdout: true
                    ).trim()
                }

                echo "Building commit: ${env.SHORT_COMMIT}"
            }
        }

        // ─────────────────────────────────────────────────────────────
        // 3. Validate Repository
        // ─────────────────────────────────────────────────────────────
        stage('Validate Repository') {

            steps {

                sh '''
                    test -f Dockerfile
                '''
            }
        }

        // ─────────────────────────────────────────────────────────────
        // 4. Docker Build
        // ─────────────────────────────────────────────────────────────
        stage('Build Docker Image') {

            steps {

                sh """
                    docker buildx build \
                      --platform linux/amd64 \
                      --label git-commit=${env.SHORT_COMMIT} \
                      --label build-number=${IMAGE_TAG} \
                      -t ${params.DOCKER_IMAGE}:${IMAGE_TAG} \
                      -t ${params.DOCKER_IMAGE}:latest \
                      --load \
                      .
                """
            }
        }

        // ─────────────────────────────────────────────────────────────
        // 5. Push Docker Image
        // ─────────────────────────────────────────────────────────────
        stage('Push Docker Image') {

            steps {

                withCredentials([
                    usernamePassword(
                        credentialsId: 'dockerhub-creds',
                        usernameVariable: 'DOCKER_USER',
                        passwordVariable: 'DOCKER_PASS'
                    )
                ]) {

                    sh '''
                        set +x

                        echo "$DOCKER_PASS" | docker login \
                            -u "$DOCKER_USER" \
                            --password-stdin
                    '''

                    sh """
                        docker push ${params.DOCKER_IMAGE}:${IMAGE_TAG}

                        docker push ${params.DOCKER_IMAGE}:latest
                    """

                    sh '''
                        docker logout
                    '''
                }
            }
        }

        // ─────────────────────────────────────────────────────────────
        // 6. Deploy to Kubernetes
        // ─────────────────────────────────────────────────────────────
        stage('Deploy to Kubernetes') {

            steps {

                sshagent(credentials: ['app-ec2-ssh-key']) {

                    sh """
                        ssh -o StrictHostKeyChecking=no ubuntu@${APP_EC2_IP} '

                            set -e

                            cd ~/gitops-platform

                            git fetch origin

                            git reset --hard origin/${params.BRANCH}

                            kubectl create namespace ${K8S_NAMESPACE} \
                              --dry-run=client -o yaml | kubectl apply -f -

                            sed "s|IMAGE_PLACEHOLDER|${params.DOCKER_IMAGE}:${IMAGE_TAG}|g; \
                                 s|IMAGE_TAG_PLACEHOLDER|${IMAGE_TAG}|g" \
                                 k8s/deployment.yaml | kubectl apply -f -

                        '
                    """
                }
            }
        }

        // ─────────────────────────────────────────────────────────────
        // 7. Verify Rollout
        // ─────────────────────────────────────────────────────────────
        stage('Verify Rollout') {

            steps {

                sshagent(credentials: ['app-ec2-ssh-key']) {

                    sh """
                        ssh -o StrictHostKeyChecking=no ubuntu@${APP_EC2_IP} '

                            set -e

                            kubectl rollout status deployment/${K8S_DEPLOY} \
                              -n ${K8S_NAMESPACE} \
                              --timeout=180s

                            echo ""
                            echo "=== Running Pods ==="

                            kubectl get pods \
                              -n ${K8S_NAMESPACE} \
                              -l app=${K8S_DEPLOY}

                            echo ""
                            echo "=== Services ==="

                            kubectl get svc -n ${K8S_NAMESPACE}

                        '
                    """
                }
            }
        }
    }

    // ─────────────────────────────────────────────────────────────────
    // POST ACTIONS
    // ─────────────────────────────────────────────────────────────────
    post {

        success {

            echo """

==================================================

Deployment successful

Repository:
${params.REPO_URL}

Docker Image:
${params.DOCKER_IMAGE}:${IMAGE_TAG}

Kubernetes Deployment:
${K8S_DEPLOY}

Namespace:
${K8S_NAMESPACE}

==================================================

"""
        }

        failure {

            sshagent(credentials: ['app-ec2-ssh-key']) {

                sh """
                    ssh -o StrictHostKeyChecking=no ubuntu@${APP_EC2_IP} '

                        kubectl rollout undo deployment/${K8S_DEPLOY} \
                          -n ${K8S_NAMESPACE} || true
                    '
                """
            }

            echo 'Deployment failed — rollback attempted'
        }

        always {

            sh '''
                docker image prune -af || true
            '''
        }
    }
}