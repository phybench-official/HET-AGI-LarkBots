#!/bin/bash

# 项目路径
PROJECT_DIR="/data/hetbench/dock/stacks/lark-bot"
LOG_FILE="$PROJECT_DIR/deploy.log"

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "========== Deployment triggered =========="
log "Triggered by: ${1:-manual}"

# 镜像优先级列表
IMAGES=(
    "ghcr.io/phybench-official/het-lark-bot:latest"
    "ghcr.nju.edu.cn/phybench-official/het-lark-bot:latest"
    "wjsoj/het-lark-bot:latest"
)

# 等待镜像同步
log "Waiting 10 seconds for image sync..."
sleep 10

# 进入项目目录
cd "$PROJECT_DIR" || {
    log "ERROR: Failed to change directory to $PROJECT_DIR"
    exit 1
}

# 尝试拉取镜像（按优先级）
IMAGE_TO_USE=""
for IMAGE in "${IMAGES[@]}"; do
    log "Trying to pull: $IMAGE"
    if DOCKER_IMAGE="$IMAGE" docker compose pull 2>&1 | tee -a "$LOG_FILE"; then
        log "✓ Successfully pulled: $IMAGE"
        IMAGE_TO_USE="$IMAGE"
        break
    else
        log "✗ Failed to pull: $IMAGE"
    fi
done

# 如果所有镜像都拉取失败，尝试使用本地镜像
if [ -z "$IMAGE_TO_USE" ]; then
    log "WARNING: All image sources failed, checking local images..."
    for IMAGE in "${IMAGES[@]}"; do
        if docker image inspect "$IMAGE" &>/dev/null; then
            log "✓ Found local image: $IMAGE"
            IMAGE_TO_USE="$IMAGE"
            break
        fi
    done

    if [ -z "$IMAGE_TO_USE" ]; then
        log "ERROR: No available images (remote or local)"
        exit 1
    fi
fi

log "Using image: $IMAGE_TO_USE"

# 重新启动容器
log "Restarting containers with docker compose up -d..."
if DOCKER_IMAGE="$IMAGE_TO_USE" docker compose up -d 2>&1 | tee -a "$LOG_FILE"; then
    log "Containers restarted successfully"
else
    log "ERROR: Failed to restart containers"
    exit 1
fi

# 显示容器状态
log "Current container status:"
docker compose ps >> "$LOG_FILE" 2>&1

# 清理旧镜像(可选,节省空间)
log "Cleaning up old images..."
docker image prune -f >> "$LOG_FILE" 2>&1

log "========== Deployment completed successfully =========="
log ""

exit 0
