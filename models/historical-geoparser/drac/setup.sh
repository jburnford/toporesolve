#!/bin/bash
# DRAC Environment Setup Script
# Run this once to set up your environment on DRAC clusters

set -e  # Exit on error

echo "================================================"
echo "Setting up Historical Geoparser on DRAC"
echo "================================================"

# Load required modules
echo "Loading modules..."
module load python/3.11
module load cuda/12.1
module load apptainer  # For containerization if needed

# Create virtual environment
echo "Creating virtual environment..."
python -m venv ~/historic_geo_env

# Activate environment
source ~/historic_geo_env/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install PyTorch (CUDA-enabled)
echo "Installing PyTorch with CUDA support..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install core dependencies
echo "Installing core dependencies..."
pip install transformers accelerate bitsandbytes
pip install vllm  # Fast LLM inference
pip install sentencepiece protobuf

# Install geoprocessing libraries
echo "Installing geoprocessing libraries..."
pip install neo4j geopy shapely

# Install utilities
echo "Installing utilities..."
pip install python-dotenv tqdm jsonlines

# Create directories
echo "Creating project directories..."
mkdir -p ~/scratch/historical-geoparser/data
mkdir -p ~/scratch/historical-geoparser/models
mkdir -p ~/scratch/historical-geoparser/results
mkdir -p ~/scratch/historical-geoparser/logs

# Create .env template
echo "Creating .env template..."
cat > ~/scratch/historical-geoparser/.env << 'EOF'
# Neo4j Configuration
NEO4J_URI=bolt://your-neo4j-host:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password

# Model Configuration
HF_TOKEN=your-huggingface-token
EOF

echo ""
echo "================================================"
echo "Setup Complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo "1. Edit ~/scratch/historical-geoparser/.env with your credentials"
echo "2. Copy your data to ~/scratch/historical-geoparser/data/"
echo "3. Submit a job: sbatch drac_inference_job.sh"
echo ""
echo "To activate environment later:"
echo "  source ~/historic_geo_env/bin/activate"
echo ""
