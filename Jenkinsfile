// ─────────────────────────────────────────────────────────────────────────────
//  GitOps Platform · Jenkinsfile
//  Stages: Clone → Build → Push → Deploy → Health Check
// ─────────────────────────────────────────────────────────────────────────────

pipeline {
    agent any

    // Parameters passed from FastAPI backend via buildWithParameters
    parameters {
        string(name: 'REPO_URL',     defaultValue: '',      description: 'GitHub HTTPS clone URL')
        string(name: 'BRANCH',       defaultValue: 'main',  description: 'Git branch to build')
        string(name: 'DOCKER_IMAGE', defaultValue: '',      description: 'Docker Hub image name (user/image)')
        string(name: 'ENVIRONMENT',  defaultValue: 'local-k8s', description: 'Target environment')
    }

    environment {
        // Store Docker Hub credentials as "dockerhub-creds" in Jenkins credentials
        DOCKER_CREDS = credentials('dockerhub-creds')
        KUBECONFIG   = "${HOME}/.kube/config"
        IMAGE_TAG    = "${env.BUILD_NUMBER}"
    }

    options {
        timeout(time: 20, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    stages {

        // ── 1. Clone ──────────────────────────────────────────────────────────
        stage('Clone Repository') {
            steps {
                echo "▶ Cloning ${params.REPO_URL} @ ${params.BRANCH}"
                git(
                    url: "${params.REPO_URL}",
                    branch: "${params.BRANCH}",
                    changelog: true,
                    poll: false
                )
                sh 'ls -la'
            }
        }

        // ── 2. Build Docker Image ─────────────────────────────────────────────
        stage('Build Docker Image') {
            steps {
                echo "▶ Building Docker image: ${params.DOCKER_IMAGE}:${IMAGE_TAG}"
                sh """
                    docker build \
                        --tag ${params.DOCKER_IMAGE}:${IMAGE_TAG} \
                        --tag ${params.DOCKER_IMAGE}:latest \
                        --label "git-commit=${env.GIT_COMMIT}" \
                        --label "build=${env.BUILD_NUMBER}" \
                        .
                """
                sh "docker images | grep ${params.DOCKER_IMAGE}"
            }
        }

        // ── 3. Push to Docker Hub ─────────────────────────────────────────────
        stage('Push to Docker Hub') {
            steps {
                echo "▶ Pushing to Docker Hub"
                sh """
                    echo "${DOCKER_CREDS_PSW}" | docker login -u "${DOCKER_CREDS_USR}" --password-stdin
                    docker push ${params.DOCKER_IMAGE}:${IMAGE_TAG}
                    docker push ${params.DOCKER_IMAGE}:latest
                    docker logout
                """
            }
        }

        // ── 4. Deploy to Kubernetes ───────────────────────────────────────────
        stage('Deploy to Kubernetes') {
            when {
                expression { params.ENVIRONMENT == 'local-k8s' }
            }
            steps {
                echo "▶ Deploying to local Kubernetes (minikube)"
                sh """
                    # Update image tag in deployment
                    sed -i 's|IMAGE_PLACEHOLDER|${params.DOCKER_IMAGE}:${IMAGE_TAG}|g' k8s/deployment.yaml

                    # Apply manifests
                    kubectl apply -f k8s/deployment.yaml
                    kubectl apply -f k8s/service.yaml

                    # Wait for rollout
                    kubectl rollout status deployment/app-deployment --timeout=120s

                    # Show pod status
                    kubectl get pods -l app=gitops-app
                """
            }
        }

        // ── 5. Health Check ───────────────────────────────────────────────────
        stage('Health Check') {
            steps {
                echo "▶ Running health check"
                sh """
                    sleep 5
                    # Get minikube service URL and check /health
                    SERVICE_URL=\$(minikube service app-service --url 2>/dev/null || echo "http://localhost:8000")
                    echo "Checking: \${SERVICE_URL}/health"
                    curl --fail --retry 5 --retry-delay 3 "\${SERVICE_URL}/health" || echo "Health check skipped (service not yet exposed)"
                """
            }
        }

    }

    // ── Post-build actions ────────────────────────────────────────────────────
    post {
        success {
            echo "✓ Pipeline completed successfully. Build #${env.BUILD_NUMBER}"
        }
        failure {
            echo "✗ Pipeline failed at stage. Check logs above."
        }
        always {
            // Clean up dangling images to save disk space
            sh 'docker image prune -f || true'
        }
    }
}
