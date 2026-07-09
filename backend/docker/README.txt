Folder: backend/docker/

Description:
This folder contains all Docker and container orchestration configuration
files for building, running, and deploying the backend system in
containerized environments.

Responsibilities:
- Define Dockerfiles for the API server, worker, and any sidecar services
- Provide docker-compose files for local development and testing stacks
- Configure multi-stage builds for lean production images
- Include environment variable templates and container networking setup

Integration:
References the backend application code and exposes it as a containerized
service. Works alongside backend/scripts/ for container entrypoint commands.
In production, these configurations are consumed by orchestration platforms
such as Kubernetes, AWS ECS, or Railway for deployment and scaling.
