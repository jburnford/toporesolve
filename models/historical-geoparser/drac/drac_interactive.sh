#!/bin/bash
#SBATCH --account=def-yourpi              # Replace with your PI's account
#SBATCH --gres=gpu:v100:1                 # Request 1 V100 GPU (cheaper for testing)
#SBATCH --cpus-per-task=4                 # Number of CPU cores
#SBATCH --mem=32G                         # Memory
#SBATCH --time=3:00:00                    # Max time (3 hours)
#SBATCH --job-name=hist-geo-interactive   # Job name

# ================================================
# Interactive Job for Testing/Development
# ================================================

echo "Interactive job started at: $(date)"
echo "Running on node: $(hostname)"
echo "GPU(s): $CUDA_VISIBLE_DEVICES"
echo ""
echo "To use this interactive session:"
echo "  1. Load modules: module load python/3.11 cuda/12.1"
echo "  2. Activate env: source ~/historic_geo_env/bin/activate"
echo "  3. cd ~/scratch/historical-geoparser"
echo "  4. Run your code"
echo ""
echo "Session will end in 3 hours. Type 'exit' to end early."
echo ""

# Keep session alive
sleep infinity
