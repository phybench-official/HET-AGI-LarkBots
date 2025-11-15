from library import *


def main():

    # problem_solver = ProblemSolverBot("做题家")
    # problem_solver.start()

    # PKU_PHY_fermion = ReflectorBot("北大物院-费米子")
    # PKU_PHY_fermion.start(block=True)

    # 使用新的 TestMCPBot 来测试 Mathematica MCP 集成
    test_mcp = TestMCPBot("测码者")
    test_mcp.start(block=True)

    print("[Main] MainThread exiting.")


if __name__ == "__main__":

    try:
        multiprocessing.set_start_method("spawn")
    except RuntimeError:
        pass
    
    main()