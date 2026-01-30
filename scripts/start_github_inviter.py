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