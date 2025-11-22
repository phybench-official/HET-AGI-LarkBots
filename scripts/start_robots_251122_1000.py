from library import *


def main():
    
    PKU_PHY_fermion1 = PkuPhyFermionBot(
        config_path = f"configs/pku_phy_fermion_configs_251122_1200/fermion1.yaml",
    )
    PKU_PHY_fermion1.start()
    
    PKU_PHY_fermion2 = PkuPhyFermionBot(
        config_path = f"configs/pku_phy_fermion_configs_251122_1200/fermion2.yaml",
    )
    PKU_PHY_fermion2.start()
    
    PKU_PHY_fermion3 = PkuPhyFermionBot(
        config_path = f"configs/pku_phy_fermion_configs_251122_1200/fermion3.yaml",
    )
    PKU_PHY_fermion3.start()
    
    PKU_PHY_fermion4 = PkuPhyFermionBot(
        config_path = f"configs/pku_phy_fermion_configs_251122_1200/fermion4.yaml",
    )
    PKU_PHY_fermion4.start()
    
    PKU_PHY_fermion5 = PkuPhyFermionBot(
        config_path = f"configs/pku_phy_fermion_configs_251122_1200/fermion5.yaml",
    )
    PKU_PHY_fermion5.start(block=True)
    
    print("[Main] MainThread exiting.")


if __name__ == "__main__":
    
    main()