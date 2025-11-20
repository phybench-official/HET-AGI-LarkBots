from library import *


def main():
    
    problem_solver = ProblemSolverBot(
        config_path = f"configs/problem_solver_config.yaml",
    )
    problem_solver.start()
    
    PKU_PHY_fermion_for_testing = PkuPhyFermionBot(
        config_path = f"configs/pku_phy_fermion_config_for_testing.yaml",
    )
    PKU_PHY_fermion_for_testing.start()
    
    PKU_PHY_fermion = PkuPhyFermionBot(
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