pipeline {
  agent any

  options {
    timestamps()
    buildDiscarder(logRotator(numToKeepStr: '20'))
    timeout(time: 30, unit: 'MINUTES')
  }

  environment {
    IMAGE = 'gsst3ja/openproject-mcp'
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
        script {
          env.GIT_SHORT = sh(returnStdout: true, script: 'git rev-parse --short HEAD').trim()
          env.VERSION = sh(returnStdout: true, script: 'cat apps/mcp-server/VERSION').trim()
        }
        echo "building ${env.IMAGE}:${env.VERSION} (${env.GIT_SHORT})"
      }
    }

    stage('Lint & test') {
      steps {
        dir('apps/mcp-server') {
          sh '''
            python3 -m venv .venv
            . .venv/bin/activate
            pip install -e .[dev]
            ruff check .
            mypy src/
            pytest -q --cov=src --cov-fail-under=85
          '''
        }
      }
    }

    stage('Setup buildx') {
      steps {
        sh '''
          docker run --privileged --rm tonistiigi/binfmt --install all
          # fresh dind volumes lose the builder. inspect first, create if missing.
          if ! docker buildx inspect mcp-builder >/dev/null 2>&1; then
            docker buildx create --name mcp-builder --driver docker-container --use
          else
            docker buildx use mcp-builder
          fi
          docker buildx inspect --bootstrap
        '''
      }
    }

    stage('Multi-arch build & push') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'dockerhub-token', usernameVariable: 'DH_USER', passwordVariable: 'DH_TOKEN')]) {
          sh '''
            echo "$DH_TOKEN" | docker login -u "$DH_USER" --password-stdin
            docker buildx build \
              --platform linux/amd64,linux/arm64 \
              --build-arg VERSION=${VERSION} \
              --build-arg REVISION=${GIT_SHORT} \
              -t ${IMAGE}:${VERSION} \
              -t ${IMAGE}:latest \
              --push \
              apps/mcp-server/
          '''
        }
      }
    }

    stage('Trivy scan') {
      steps {
        sh '''
          # scan the just-pushed image. fail on HIGH/CRITICAL.
          docker run --rm \
            -v /var/run/docker.sock:/var/run/docker.sock \
            aquasec/trivy:0.53.0 image \
            --severity HIGH,CRITICAL \
            --exit-code 1 \
            --ignore-unfixed \
            ${IMAGE}:${VERSION}
        '''
      }
    }

    stage('Helm lint & package') {
      steps {
        sh '''
          helm lint helm/openproject-mcp/
          helm package helm/openproject-mcp/ \
            --app-version "${VERSION}" \
            --version "${VERSION}" \
            -d /tmp/charts/
        '''
      }
    }

    stage('Deploy dev') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig-dev', variable: 'KUBECONFIG')]) {
          sh '''
            helm upgrade --install openproject-mcp helm/openproject-mcp/ \
              -n openproject-mcp --create-namespace \
              -f helm/openproject-mcp/values-dev.yaml \
              --set image.tag=${VERSION} \
              --atomic --timeout 5m --wait
          '''
        }
      }
    }

    stage('Smoke dev') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig-dev', variable: 'KUBECONFIG')]) {
          sh '''
            kubectl -n openproject-mcp rollout status deploy/openproject-mcp --timeout=2m
            POD=$(kubectl -n openproject-mcp get pod -l app.kubernetes.io/name=openproject-mcp -o jsonpath='{.items[0].metadata.name}')
            kubectl -n openproject-mcp exec "$POD" -- curl -fsS http://localhost:8000/healthz
            kubectl -n openproject-mcp exec "$POD" -- curl -fsS http://localhost:8000/readyz
          '''
        }
      }
    }

    stage('Promote staging') {
      input { message 'Promote to staging?' }
      steps {
        withCredentials([file(credentialsId: 'kubeconfig-staging', variable: 'KUBECONFIG')]) {
          sh '''
            helm upgrade --install openproject-mcp helm/openproject-mcp/ \
              -n openproject-mcp --create-namespace \
              -f helm/openproject-mcp/values-staging.yaml \
              --set image.tag=${VERSION} \
              --atomic --timeout 5m --wait
          '''
        }
      }
    }

    stage('Promote prod') {
      input { message 'Promote to prod?' }
      steps {
        withCredentials([file(credentialsId: 'kubeconfig-prod', variable: 'KUBECONFIG')]) {
          sh '''
            helm upgrade --install openproject-mcp helm/openproject-mcp/ \
              -n openproject-mcp --create-namespace \
              -f helm/openproject-mcp/values-prod.yaml \
              --set image.tag=${VERSION} \
              --atomic --timeout 5m --wait
          '''
        }
      }
    }
  }

  post {
    failure {
      // --atomic above will already revert a failed upgrade; this is the
      // safety net for failures outside the helm stage (lint, scan, smoke).
      echo "pipeline failed at stage ${env.STAGE_NAME}; --atomic handled helm rollback if applicable"
    }
  }
}
