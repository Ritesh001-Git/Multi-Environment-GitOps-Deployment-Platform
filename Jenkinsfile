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

        choice(
            name: 'ENVIRONMENT',
            choices: ['local-k8s', 'staging', 'production'],
            description: 'Deployment environment'
        )

        string(
            name: 'APP_EC2_IP',
            defaultValue: '',
            description: 'SSH host or private IP of the K3s server'
        )
    }

    environment {

        APP_EC2_IP    = "${params.APP_EC2_IP}"

        IMAGE_TAG     = "${BUILD_NUMBER}"

        K8S_NAMESPACE = 'gitops'
        K8S_DEPLOY    = 'gitops-app'
        DEPLOY_ATTEMPTED = 'false'
    }

    stages {

        stage('Validate Parameters') {
            steps {
                script {
                    if (!(params.REPO_URL ==~ /^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+(?:\.git)?$/)) {
                        error('REPO_URL must be a GitHub HTTPS clone URL')
                    }
                    if (!(params.BRANCH ==~ /^[A-Za-z0-9._\/-]+$/) || params.BRANCH.contains('..')) {
                        error('BRANCH contains unsafe characters')
                    }
                    if (!(params.DOCKER_IMAGE ==~ /^[a-z0-9]+(?:[._-][a-z0-9]+)*(?:\/[a-z0-9]+(?:[._-][a-z0-9]+)*)+$/)) {
                        error('DOCKER_IMAGE is empty or invalid')
                    }
                    if (!(params.APP_EC2_IP ==~ /^[A-Za-z0-9.-]+$/)) {
                        error('APP_EC2_IP is empty or invalid')
                    }
                }
            }
        }

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
                    test -f k8s/deployment.yml
                    test -f k8s/service.yml
                    test -f k8s/ingress-traefik.yml
                    test -f k8s/rbac.yml
                    test -f k8s/namespace.yml
                    test -f k8s/pvc.yaml
                    test -f k8s/node-exporter.yml
                    test -f k8s/kube-state-metrics-nodeport.yml
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

                    retry(2) {
                        sh """
                            docker push ${params.DOCKER_IMAGE}:${IMAGE_TAG}
                            docker push ${params.DOCKER_IMAGE}:latest
                        """
                    }

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
                        set -eu
                        test -f k8s/deployment.yml
                        rm -rf .rendered-k8s
                        mkdir .rendered-k8s
                        cp k8s/namespace.yml k8s/pvc.yaml k8s/rbac.yml \
                           k8s/service.yml k8s/ingress-traefik.yml \
                           k8s/node-exporter.yml k8s/kube-state-metrics-nodeport.yml \
                           .rendered-k8s/
                        sed 's|IMAGE_PLACEHOLDER|${params.DOCKER_IMAGE}:${IMAGE_TAG}|g' \
                            k8s/deployment.yml > .rendered-k8s/deployment.yml

                        ssh -o StrictHostKeyChecking=accept-new ubuntu@${APP_EC2_IP} \
                            'rm -rf /tmp/gitops-k8s-${BUILD_NUMBER} && mkdir /tmp/gitops-k8s-${BUILD_NUMBER}'
                        scp -o StrictHostKeyChecking=accept-new .rendered-k8s/* \
                            ubuntu@${APP_EC2_IP}:/tmp/gitops-k8s-${BUILD_NUMBER}/
                        ssh -o StrictHostKeyChecking=accept-new ubuntu@${APP_EC2_IP} '
                            set -eu
                            kubectl apply -f /tmp/gitops-k8s-${BUILD_NUMBER}/namespace.yml
                            kubectl apply -f /tmp/gitops-k8s-${BUILD_NUMBER}/pvc.yaml
                            kubectl apply -f /tmp/gitops-k8s-${BUILD_NUMBER}/rbac.yml
                            kubectl get secret gitops-backend-env -n ${K8S_NAMESPACE} >/dev/null
                        '
                    """

                    script {
                        env.DEPLOY_ATTEMPTED = 'true'
                    }

                    sh """
                        ssh -o StrictHostKeyChecking=accept-new ubuntu@${APP_EC2_IP} '
                            set -eu
                            kubectl apply -f /tmp/gitops-k8s-${BUILD_NUMBER}/deployment.yml
                            kubectl apply -f /tmp/gitops-k8s-${BUILD_NUMBER}/service.yml
                            kubectl apply -f /tmp/gitops-k8s-${BUILD_NUMBER}/ingress-traefik.yml
                            kubectl apply -f /tmp/gitops-k8s-${BUILD_NUMBER}/node-exporter.yml
                            kubectl apply -f /tmp/gitops-k8s-${BUILD_NUMBER}/kube-state-metrics-nodeport.yml
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
                        ssh -o StrictHostKeyChecking=accept-new ubuntu@${APP_EC2_IP} '

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
            script {
                if (env.DEPLOY_ATTEMPTED == 'true') {
                    sshagent(credentials: ['app-ec2-ssh-key']) {
                        sh """
                            ssh -o StrictHostKeyChecking=accept-new ubuntu@${APP_EC2_IP} '
                                kubectl rollout undo deployment/${K8S_DEPLOY} \
                                  -n ${K8S_NAMESPACE} || true
                            '
                        """
                    }
                    echo 'Deployment failed — rollback attempted'
                } else {
                    echo 'Build failed before deployment; existing Kubernetes revision was not changed'
                }
            }
        }

        always {

            sh """
                docker logout || true
                docker image rm ${params.DOCKER_IMAGE}:${IMAGE_TAG} \
                    ${params.DOCKER_IMAGE}:latest || true
                rm -rf .rendered-k8s
            """
        }
    }
}
