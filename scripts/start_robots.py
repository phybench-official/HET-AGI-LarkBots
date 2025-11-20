from library import *


def main():
    
    problem_solver = ProblemSolverBot(
        lark_bot_name = "做题家",
    )
    problem_solver.start()
    
    PKU_PHY_fermion_for_testing = PkuPhyFermionBot(
        lark_bot_name = "北大物院-费米子（内测版）",
        config_path = f"configs/pku_phy_fermion_config_for_testing.yaml",
    )
    PKU_PHY_fermion_for_testing.start()
    
    PKU_PHY_fermion = PkuPhyFermionBot(
        lark_bot_name = "北大物院-费米子",
        config_path = f"configs/pku_phy_fermion_config_251120_0900.yaml",
    )
    PKU_PHY_fermion.start(block=True)
    
    print("[Main] MainThread exiting.")


if __name__ == "__main__":

    try:
        multiprocessing.set_start_method("spawn")
    except RuntimeError:
        pass
    
    main()