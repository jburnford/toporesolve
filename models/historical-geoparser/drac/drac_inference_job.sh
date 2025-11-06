#!/bin/bash
#SBATCH --account=def-yourpi              # Replace with your PI's account
#SBATCH --gres=gpu:a100:1                 # Request 1 A100 GPU (or v100:1 for V100)
#SBATCH --cpus-per-task=8                 # Number of CPU cores
#SBATCH --mem=64G                         # Memory
#SBATCH --time=6:00:00                    # Max time (6 hours)
#SBATCH --job-name=hist-geo               # Job name
#SBATCH --output=%x-%j.out                # Output file (%x=job name, %j=job ID)
#SBATCH --error=%x-%j.err                 # Error file
#SBATCH --mail-type=BEGIN,END,FAIL        # Email notifications
#SBATCH --mail-user=your-email@domain.com # Your email

# ================================================
# Historical Geoparser Inference Job
# ================================================

echo "Job started at: $(date)"
echo "Running on node: $(hostname)"
echo "Job ID: $SLURM_JOB_ID"
echo "GPU(s): $CUDA_VISIBLE_DEVICES"

# Load modules
module load python/3.11 cuda/12.1

# Activate virtual environment
source ~/historic_geo_env/bin/activate

# Set working directory
cd ~/scratch/historical-geoparser

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Set HuggingFace cache to scratch (important!)
export HF_HOME=~/scratch/historical-geoparser/models
export TRANSFORMERS_CACHE=~/scratch/historical-geoparser/models

# Configuration
MODEL_NAME="meta-llama/Meta-Llama-3.1-70B-Instruct"  # Or qwen/Qwen2.5-72B-Instruct
INPUT_FILE="data/historical_toponyms.jsonl"
OUTPUT_FILE="results/disambiguated_$(date +%Y%m%d_%H%M%S).json"
BATCH_SIZE=32

# Run inference
echo ""
echo "Starting inference..."
echo "Model: $MODEL_NAME"
echo "Input: $INPUT_FILE"
echo "Output: $OUTPUT_FILE"
echo ""

python -u ../drac_batch_inference.py \
    --model "$MODEL_NAME" \
    --input "$INPUT_FILE" \
    --output "$OUTPUT_FILE" \
    --batch_size $BATCH_SIZE \
    --neo4j_uri "$NEO4J_URI" \
    --neo4j_user "$NEO4J_USER" \
    --neo4j_password "$NEO4J_PASSWORD"

echo ""
echo "Job completed at: $(date)"
echo "Results saved to: $OUTPUT_FILE"

# Optional: Copy results back to home or project directory
# cp "$OUTPUT_FILE" ~/projects/def-yourpi/results/
