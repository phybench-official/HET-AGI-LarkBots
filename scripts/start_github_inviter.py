# nohup uv run -m scripts.start_github_inviter 2>&1 >nohup_magnus_log.out &
# pkill -9 -f "HET-AGI-LarkBots"
from library import *


def main():
    
    github_inviter = GithubInviterBot(
        config_path = f"configs/github_inviter.yaml",
    )
    github_inviter.start(block=True)


if __name__ == "__main__":
    
    try:
        multiprocessing.set_start_method("spawn")
    except RuntimeError:
        pass
    
    main()