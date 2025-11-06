## DRAC Deployment Guide

Complete guide for deploying the historical geoparser on Digital Research Alliance of Canada (DRAC) clusters.

## Prerequisites

1. **DRAC Account**: Apply at [alliancecan.ca](https://alliancecan.ca)
2. **Resource Allocation**: Ensure you have GPU hours available
3. **SSH Access**: Configure SSH keys for cluster access

## Supported Clusters

- **Cedar** (Simon Fraser University) - Best for large jobs
- **Graham** (University of Waterloo) - Good availability
- **Béluga** (École de technologie supérieure) - Good for prototyping
- **Narval** (École de technologie supérieure) - Latest hardware

## Setup (One-Time)

### 1. Connect to DRAC

```bash
# Cedar
ssh username@cedar.computecanada.ca

# Graham
ssh username@graham.computecanada.ca

# Béluga
ssh username@beluga.computecanada.ca

# Narval
ssh username@narval.computecanada.ca
```

### 2. Run Setup Script

```bash
# Copy setup script to cluster
scp setup.sh username@cedar.computecanada.ca:~

# SSH to cluster and run
ssh username@cedar.computecanada.ca
chmod +x setup.sh
./setup.sh
```

### 3. Configure Environment

```bash
# Edit .env file
cd ~/scratch/historical-geoparser
nano .env

# Add your credentials:
# - Neo4j connection details
# - HuggingFace token (if using gated models)
```

### 4. Upload Data

```bash
# From your local machine
scp your_data.jsonl username@cedar.computecanada.ca:~/scratch/historical-geoparser/data/
```

## Running Jobs

### Quick Test (Interactive)

For testing and debugging:

```bash
# Submit interactive job
sbatch drac_interactive.sh

# Wait for allocation
squeue -u $USER

# Once running, connect to the node
# (Job output will show the node name)
```

### Production Batch Job

For processing large datasets:

```bash
# Edit job parameters
nano drac_inference_job.sh

# Update:
# - --account=def-yourpi
# - --mail-user=your-email@domain.com
# - MODEL_NAME (if different)
# - INPUT_FILE path
# - BATCH_SIZE (32 works well for A100)

# Submit job
sbatch drac_inference_job.sh

# Check status
squeue -u $USER

# View output
tail -f hist-geo-JOBID.out
```

### Check Job Status

```bash
# View all your jobs
squeue -u $USER

# View completed jobs
sacct -u $USER --format=JobID,JobName,State,Elapsed,MaxRSS

# Cancel a job
scancel JOBID

# View job details
seff JOBID
```

## Resource Guidelines

### GPU Selection

| GPU Type | Memory | Best For | Availability |
|----------|--------|----------|--------------|
| V100 | 16GB | Testing, 8B models | High |
| V100L | 32GB | 13B-70B models | Medium |
| A100 | 40GB | 70B+ models | Low (popular) |
| A100 | 80GB | Very large models | Very Low |

### Model Size Recommendations

| Model Size | GPU | Memory | Batch Size |
|------------|-----|--------|------------|
| 7-8B | V100 | 32GB | 64 |
| 13B | V100L | 32GB | 32 |
| 70B | A100 | 64GB | 16-32 |
| 72B | A100 | 64GB | 16-32 |

### Estimated Processing Times

Assuming V100L GPU + vLLM:

| Dataset Size | Model | Time | GPU Hours |
|--------------|-------|------|-----------|
| 100 toponyms | 70B | ~10 min | 0.17 |
| 1,000 toponyms | 70B | ~1.5 hrs | 1.5 |
| 10,000 toponyms | 70B | ~15 hrs | 15 |

## Optimization Tips

### 1. Use vLLM for Speed

vLLM provides 2-5x speedup:

```python
# Automatically used in drac_batch_inference.py
# To disable: --no-vllm flag
```

### 2. Increase Batch Size

Larger batches = better GPU utilization:

```bash
# In drac_inference_job.sh
BATCH_SIZE=64  # For 8B models on V100
BATCH_SIZE=32  # For 70B models on A100
```

### 3. Use Scratch Space

Never use home directory for data:

```bash
# ✓ Good - scratch has high performance
~/scratch/historical-geoparser/

# ✗ Bad - home has quotas and is slow
~/historical-geoparser/
```

### 4. Cache Models

Download model once, reuse:

```bash
# Set in job script
export HF_HOME=~/scratch/historical-geoparser/models

# Model downloads once, cached for future jobs
```

### 5. Job Arrays for Massive Datasets

Process multiple files in parallel:

```bash
#SBATCH --array=1-10  # 10 parallel jobs

# Each job processes a different file
INPUT_FILE="data/batch_${SLURM_ARRAY_TASK_ID}.jsonl"
```

## Monitoring

### GPU Usage

```bash
# While job is running, connect to node
ssh NODE_NAME

# Watch GPU utilization
nvidia-smi -l 1
```

### Resource Usage

```bash
# After job completes
seff JOBID

# Shows:
# - CPU usage
# - Memory usage
# - GPU usage
# - Time used
```

## Cost Management

### Allocation Tracking

```bash
# Check your allocation
sshare -U -u $USER

# View recent usage
sreport cluster UserUtilizationByAccount Start=2024-01-01 -t Hours
```

### Tips to Save GPU Hours

1. **Test on small subset** first (100 toponyms)
2. **Use interactive jobs** for debugging (don't waste GPU hours on crashes)
3. **Start with smaller models** (8B) before trying 70B
4. **Use CPU-only jobs** for non-LLM preprocessing

## Troubleshooting

### Job Fails Immediately

```bash
# Check error file
cat hist-geo-JOBID.err

# Common issues:
# - Wrong account: Update --account=def-yourpi
# - Out of allocation: Request more or wait for reset
# - Module not found: Check module load commands
```

### Out of Memory

```bash
# Solution 1: Request more memory
#SBATCH --mem=96G

# Solution 2: Reduce batch size
BATCH_SIZE=16

# Solution 3: Use quantization (in code)
# load_in_4bit=True
```

### Slow Start Time

Model loading can take 10-20 minutes for 70B models - this is normal!

### Neo4j Connection Issues

```bash
# Test connection from login node
python -c "from neo4j import GraphDatabase;
driver = GraphDatabase.driver('bolt://your-neo4j:7687',
auth=('neo4j', 'password'));
driver.verify_connectivity();
print('OK')"
```

## Example Workflows

### Workflow 1: Quick Test

```bash
# 1. Create small test file (10 toponyms)
head -n 10 data/full_dataset.jsonl > data/test.jsonl

# 2. Submit interactive job
sbatch drac_interactive.sh

# 3. When allocated, run inference
python drac_batch_inference.py \
    --model meta-llama/Meta-Llama-3.1-8B-Instruct \
    --input data/test.jsonl \
    --output results/test_result.json \
    --batch_size 10 \
    --neo4j_uri "$NEO4J_URI" \
    --neo4j_user "$NEO4J_USER" \
    --neo4j_password "$NEO4J_PASSWORD"
```

### Workflow 2: Full Production Run

```bash
# 1. Edit job script
nano drac_inference_job.sh

# 2. Submit
sbatch drac_inference_job.sh

# 3. Monitor
watch -n 60 squeue -u $USER

# 4. When complete, download results
scp username@cedar.computecanada.ca:~/scratch/historical-geoparser/results/*.json ./
```

### Workflow 3: Large Dataset (Job Array)

```bash
# 1. Split data into chunks
split -l 1000 -d data/large_dataset.jsonl data/chunk_

# 2. Create job array script
# (See drac_array_job.sh example)

# 3. Submit array
sbatch drac_array_job.sh

# 4. Wait for all to complete
watch -n 60 squeue -u $USER

# 5. Merge results
cat results/chunk_*.json > results/combined.json
```

## Getting Help

- **DRAC Documentation**: [docs.alliancecan.ca](https://docs.alliancecan.ca)
- **Support**: support@tech.alliancecan.ca
- **Status Page**: [status.alliancecan.ca](https://status.alliancecan.ca)

## Best Practices

1. **Always test small** before running on full dataset
2. **Use descriptive job names** for tracking
3. **Keep logs** for reproducibility
4. **Clean up scratch** regularly (60-day auto-deletion)
5. **Archive results** to project or home space
6. **Document your allocation usage** for annual reports

## Next Steps

After successful DRAC deployment:

1. Run evaluation against gold standard
2. Compare with baseline geoparsers
3. Iterate on prompts based on errors
4. Scale to full historical corpus
5. Publish results and share learned lessons!
