# Implementation Roadmap

## Project Status: Planning Phase Complete ✅

All design decisions made, architecture defined, code framework implemented.

## Phase-by-Phase Implementation Guide

---

## Phase 0: Prerequisites (Week 0)

### Completed ✅
- [x] Architecture design
- [x] Neo4j schema design
- [x] RAG pipeline implementation
- [x] Ambiguity detection system
- [x] OpenRouter testing framework
- [x] DRAC deployment scripts
- [x] Documentation

### To Do
- [ ] Obtain OpenRouter API key
- [ ] Obtain Gemini API key (for gold standard creation)
- [ ] Apply for DRAC account (if not already done)
- [ ] Access to Canada-focused Neo4j database

**Estimated Time**: 1-3 days

---

## Phase 1: Neo4j Setup and Data Ingestion (Week 1)

### Option A: Use Existing Canada Database ⭐ RECOMMENDED

**If you already have Canada-focused Neo4j**:

1. **Connect to existing database**
   ```bash
   # Test connection
   python models/historical-geoparser/neo4j/query_utils.py
   ```

2. **Verify schema compatibility**
   - Check if schema matches our design
   - Add temporal fields if missing (`valid_from`, `valid_to`)

3. **Validate data quality**
   ```python
   from neo4j.query_utils import HistoricalPlaceQuerier

   querier = HistoricalPlaceQuerier(uri, user, password)
   stats = querier.get_statistics()
   print(stats)  # Check coverage
   ```

4. **Add temporal data if needed**
   - Run queries to add `valid_from`/`valid_to` for known name changes
   - Priority: Major cities with name changes (York→Toronto, etc.)

**Estimated Time**: 2-3 days

### Option B: Build New Database from Scratch

**If starting fresh**:

1. **Set up Neo4j**
   ```bash
   docker run -d --name neo4j \
     -p 7474:7474 -p 7687:7687 \
     -e NEO4J_AUTH=neo4j/your-password \
     neo4j:latest
   ```

2. **Create schema**
   ```bash
   cat models/historical-geoparser/neo4j/schema.cypher | \
     cypher-shell -u neo4j -p password
   ```

3. **Ingest Wikidata** (Canada-focused)
   ```bash
   # Edit wikidata_ingest.py to filter for Canadian places
   python models/historical-geoparser/neo4j/wikidata_ingest.py
   ```
   **Time**: 4-8 hours (depends on how many places)

4. **Ingest GeoNames** (Canada only)
   ```bash
   # Download CA.txt from GeoNames
   python models/historical-geoparser/neo4j/geonames_ingest.py
   ```
   **Time**: 1-2 hours

**Estimated Time**: 1-2 weeks (if building from scratch)

### Success Criteria
- [ ] Neo4j running and accessible
- [ ] At least 1000 Canadian places in database
- [ ] Temporal data for major name changes (10+ examples)
- [ ] Can query: "Find 'Fort Garry' in 1869" → returns results

---

## Phase 2: OpenRouter Model Testing (Week 2)

### Steps

1. **Set up OpenRouter**
   ```bash
   export OPENROUTER_API_KEY=your-key
   ```

2. **Create Canadian test cases**

   Manually create 8-10 test cases covering:
   - Name changes (Fort Garry, York, Bytown)
   - Bilingual (Montreal, Quebec)
   - Ambiguous (Saint John vs St. Jean)
   - Different periods (1600s, 1800s, 1900s)

   Example:
   ```json
   {
     "toponym": "Fort Garry",
     "context": "The Red River Rebellion began near Fort Garry in 1869...",
     "entity_type": "GPE",
     "year": "1869",
     "expected_lat": 49.8951,
     "expected_lon": -97.1384
   }
   ```

3. **Run OpenRouter tests**
   ```bash
   python models/historical-geoparser/openrouter_test.py
   ```

4. **Analyze results**
   - Which model has best accuracy?
   - How are errors distributed?
   - Any Canadian-specific issues?

5. **Select production model**
   - Likely: Qwen 2.5 72B or Llama 3.1 70B
   - Balance: accuracy vs speed vs DRAC availability

### Success Criteria
- [ ] Tested 3-6 models on 8-10 Canadian examples
- [ ] Identified best-performing model
- [ ] Documented error patterns
- [ ] Cost: <$50

**Estimated Time**: 3-5 days

---

## Phase 3: Gold Standard Dataset Creation (Week 3-4)

### Using Gemini 2.5 Pro

See [04_creating_gold_standard.md](04_creating_gold_standard.md) for detailed workflow.

1. **Set up Gemini**
   ```bash
   pip install google-generativeai
   export GEMINI_API_KEY=your-key
   ```

2. **Gather source documents** (20-30 initially)
   - Library and Archives Canada
   - Early Canadiana Online
   - Provincial archives
   - Mix of English/French

3. **Extract toponyms with Gemini**
   ```python
   # Use provided script in 04_creating_gold_standard.md
   creator = CanadianGoldStandardCreator(api_key="YOUR_KEY")
   examples = creator.batch_create(source_documents)
   ```

4. **Manual verification**
   - Verify coordinates (GeoNames, historical maps)
   - Check temporal validity
   - Cross-reference sources

5. **Expand to target size**
   - Pilot: 20-30 examples
   - Refine workflow
   - Scale: 300-450 examples

### Distribution Targets
- **By Type**: 150 GPE, 100 LOC, 50-100 FAC
- **By Period**: 50-75 (1600-1763), 100-150 (1763-1867), 150-225 (1867-1950)
- **By Province**: Ontario 75-100, Quebec 75-100, others distributed
- **By Language**: 70% English, 25% French, 5% Indigenous

### Success Criteria
- [ ] 300-450 validated examples
- [ ] Covers all provinces/territories
- [ ] Covers all three historical periods
- [ ] Quality: >90% inter-annotator agreement
- [ ] Documented sources for each example

**Estimated Time**: 2-3 weeks

**Cost**: ~$0-5 (Gemini free tier should cover it)

---

## Phase 4: DRAC Deployment (Week 5-6)

### Steps

1. **Apply for DRAC account** (if needed)
   - Go to [alliancecan.ca](https://alliancecan.ca)
   - Request account
   - **Wait time**: 1-3 days for basic account

2. **Choose cluster**
   - Cedar (recommended for large jobs)
   - Graham (good availability)
   - Béluga (good for testing)

3. **Connect and setup**
   ```bash
   # SSH to cluster
   ssh username@cedar.computecanada.ca

   # Copy setup script
   scp models/historical-geoparser/drac/setup.sh username@cedar:~

   # Run setup
   bash setup.sh
   ```

4. **Upload data**
   ```bash
   # Upload code
   scp -r models/historical-geoparser username@cedar:~/scratch/

   # Upload gold standard
   scp data/canadian_gold_standard.jsonl \
     username@cedar:~/scratch/historical-geoparser/data/
   ```

5. **Configure environment**
   ```bash
   # Edit .env file on DRAC
   cd ~/scratch/historical-geoparser
   nano .env

   # Add:
   # - Neo4j connection (accessible from DRAC)
   # - HuggingFace token (if using gated models)
   ```

6. **Test with small job**
   ```bash
   # Create test file (10 examples)
   head -n 10 data/canadian_gold_standard.jsonl > data/test.jsonl

   # Edit job script
   nano drac/drac_inference_job.sh
   # Set INPUT_FILE=data/test.jsonl

   # Submit
   sbatch drac/drac_inference_job.sh

   # Monitor
   watch -n 60 squeue -u $USER
   ```

7. **Run full evaluation**
   ```bash
   # Edit for full dataset
   # Submit batch job
   sbatch drac/drac_inference_job.sh
   ```

### Success Criteria
- [ ] DRAC account active
- [ ] Environment set up successfully
- [ ] Model loads and runs
- [ ] Successfully processes test batch
- [ ] Full evaluation completes
- [ ] Results downloaded

**Estimated Time**: 1-2 weeks (including wait times)

**Compute**: 5-20 GPU hours depending on dataset size

---

## Phase 5: Evaluation and Analysis (Week 7)

### Steps

1. **Download results from DRAC**
   ```bash
   scp username@cedar:~/scratch/historical-geoparser/results/*.json ./
   ```

2. **Run evaluation**
   - Adapt `models/llms/evaluate_llm_disambiguation.py`
   - Calculate precision, recall, F1
   - Breakdown by:
     - Entity type (GPE, LOC, FAC)
     - Time period
     - Province
     - Language

3. **Error analysis**
   - Review false positives/negatives
   - Identify error patterns
   - Canadian-specific issues?

4. **Compare with baselines**
   - Cliff Clavin (modern baseline)
   - GPT-4o-mini (upper bound)
   - Traditional geoparsers (if tested)

5. **Statistical significance**
   - Calculate confidence intervals
   - Test significance of improvements

### Success Criteria
- [ ] F1-score ≥ 0.75 for GPE
- [ ] F1-score ≥ 0.70 for LOC
- [ ] F1-score ≥ 0.60 for FAC
- [ ] Handles temporal context correctly (80%+)
- [ ] Bilingual performance acceptable

**Estimated Time**: 1 week

---

## Phase 6: Iteration and Refinement (Week 8-10)

### Based on Evaluation Results

**If accuracy is good** (meets targets):
- Refine prompts for edge cases
- Add more test cases
- Focus on error analysis
- Document findings

**If accuracy is below target**:
- Analyze failure modes
- Try different models
- Improve prompt engineering
- Add more context to RAG
- Consider fine-tuning

### Potential Improvements

1. **Prompt Engineering**
   - Add more historical context
   - Improve bilingual handling
   - Better formatting for Indigenous names

2. **RAG Enhancements**
   - Add more candidates (top-15 instead of top-10)
   - Include administrative hierarchy
   - Add historical event context

3. **Knowledge Graph Expansion**
   - More temporal data
   - Indigenous name variants
   - Historical administrative boundaries

4. **Hybrid Approach** (if needed)
   - Integrate Edinburgh Geoparser
   - Implement ambiguity routing
   - Test on full dataset

**Estimated Time**: 2-3 weeks

---

## Phase 7: Publication and Dissemination (Week 11-14)

### Paper Writing

1. **Outline**
   - Abstract
   - Introduction (Canadian historical toponyms, challenges)
   - Related Work (geoparsing, historical NLP)
   - Methodology (RAG + Neo4j, gold standard creation)
   - Experiments (model comparison, evaluation)
   - Results (tables, error analysis)
   - Discussion (Canadian-specific findings, bilingual performance)
   - Conclusion (contributions, future work)

2. **Target Venues**
   - Primary: Canadian journals/conferences
   - Secondary: International geospatial venues

3. **Dataset Release**
   - Publish gold standard dataset
   - Open-source code (already on GitHub)
   - Create Zenodo DOI
   - Document usage examples

### Success Criteria
- [ ] Paper draft complete
- [ ] Dataset published with DOI
- [ ] Code documented and released
- [ ] Submitted to venue

**Estimated Time**: 3-4 weeks

---

## Optional Enhancements (Future Work)

### Enhancement 1: Fine-Tuning (If Needed)

**If base models underperform on Canadian toponyms**:

1. **Prepare training data**
   - 5,000-10,000 examples
   - Source from historical sources
   - Use Gemini to generate synthetic examples

2. **Fine-tune with LoRA**
   - Use DRAC for training
   - Base model: Best performer from Phase 2
   - ~24-48 hours training time

3. **Evaluate fine-tuned model**
   - Compare with base model
   - Test on held-out set

**Estimated Time**: 2-3 weeks

**GPU Hours**: 50-100 on DRAC

### Enhancement 2: Hybrid Pipeline

**If processing >5000 documents regularly**:

1. **Integrate Edinburgh Geoparser**
   - Set up Edinburgh with historical gazetteers
   - Test on Canadian examples
   - Create wrapper script

2. **Implement routing**
   - Use ambiguity detector
   - Route low-ambiguity → Edinburgh
   - Route high-ambiguity → LLM

3. **Evaluate savings**
   - Measure GPU hours saved
   - Check accuracy impact

**Estimated Time**: 1-2 weeks

### Enhancement 3: Multi-Language Support

**Expand beyond English/French**:

1. **Add Indigenous language support**
   - Inuktitut
   - Cree
   - Other indigenous languages

2. **Create multilingual examples**
   - 50-100 examples per language

3. **Test multilingual models**
   - Qwen (good multilingual)
   - m-BERT variants

**Estimated Time**: 3-4 weeks per language

---

## Total Timeline Summary

| Phase | Duration | Dependencies | Deliverables |
|-------|----------|--------------|--------------|
| 0: Prerequisites | 1-3 days | None | API keys, DRAC account |
| 1: Neo4j Setup | 2-14 days | Prerequisites | Working knowledge graph |
| 2: Model Testing | 3-5 days | Phase 1 | Best model selected |
| 3: Gold Standard | 2-3 weeks | Phase 2 | 300-450 validated examples |
| 4: DRAC Deploy | 1-2 weeks | Phase 3 | Results from full dataset |
| 5: Evaluation | 1 week | Phase 4 | Performance metrics |
| 6: Iteration | 2-3 weeks | Phase 5 | Improved system |
| 7: Publication | 3-4 weeks | Phase 6 | Paper, dataset, code |

**Total Core Timeline**: 10-14 weeks (~3 months)

**With Enhancements**: 14-20 weeks (~4-5 months)

---

## Resource Requirements

### Human Resources
- **Primary researcher**: 15-20 hours/week
- **Optional second annotator** (for gold standard): 10 hours total
- **Optional peer reviewer**: 5 hours

### Computational Resources
- **OpenRouter testing**: $20-50
- **Gemini gold standard creation**: $0-5 (free tier)
- **DRAC compute**: 0-30 GPU hours (free with allocation)
- **Neo4j hosting**: $0 (local) or $20/month (cloud)

**Total Budget**: $50-100 for core work

### Software Requirements
- Python 3.11+
- Neo4j 5.x
- Docker (for local Neo4j)
- HuggingFace account
- OpenRouter account
- Gemini AI Studio account
- DRAC account

---

## Risk Mitigation

### Risk 1: Neo4j Data Quality Issues
**Mitigation**: Start with pilot examples, validate carefully, add data incrementally

### Risk 2: Model Performance Below Target
**Mitigation**: Test multiple models early, iterate on prompts, consider fine-tuning

### Risk 3: DRAC Queue Times
**Mitigation**: Use multiple clusters, submit off-peak hours, test on smaller models first

### Risk 4: Gold Standard Creation Takes Too Long
**Mitigation**: Use Gemini automation, start with smaller dataset (200 examples), recruit help

### Risk 5: Historical Sources Inaccessible
**Mitigation**: Use multiple archives, Library and Archives Canada is well-digitized, contact archivists

---

## Success Metrics

### Technical Metrics
- ✅ F1-score ≥ 0.75 on Canadian GPE toponyms
- ✅ F1-score ≥ 0.70 on LOC toponyms
- ✅ F1-score ≥ 0.60 on FAC toponyms
- ✅ Temporal accuracy > 80%
- ✅ Bilingual handling functional
- ✅ Zero runtime cost (DRAC)

### Research Metrics
- ✅ Novel Canadian gold standard dataset (300-450 examples)
- ✅ Open-source system for Canadian historical geoparsing
- ✅ Publishable results
- ✅ Reproducible framework

### Impact Metrics
- ✅ Tools useful for Canadian digital humanities researchers
- ✅ Methods applicable to other regions/languages
- ✅ Contributes to Canadian digital infrastructure

---

## Next Immediate Steps (This Week)

1. [ ] **Connect to Canada Neo4j database**
   - Get connection details
   - Test queries
   - Validate data quality

2. [ ] **Set up OpenRouter**
   - Get API key
   - Test connection
   - Run sample query

3. [ ] **Create 5 pilot examples**
   - Manually from Canadian sources
   - Covering different challenges
   - Test end-to-end pipeline

4. [ ] **Run pilot test**
   - Test on pilot examples
   - Verify Neo4j integration works
   - Check results quality

5. [ ] **Adjust and plan**
   - Based on pilot results
   - Refine timeline
   - Identify blockers

**Goal**: Have working end-to-end system by end of week 1

---

## Questions to Answer Before Starting

1. **Do you have access to Canada-focused Neo4j database?**
   - If yes: What's the connection info?
   - If no: Start building from scratch (add 1-2 weeks)

2. **Do you have DRAC account?**
   - If yes: Which clusters do you have access to?
   - If no: Apply now (approval takes 1-3 days)

3. **What's your timeline for completion?**
   - 3 months (core work only)
   - 4-5 months (with enhancements)
   - Longer (part-time)

4. **Any specific Canadian regions of interest?**
   - All of Canada (general)
   - Specific provinces (focus dataset)
   - Specific time periods

5. **Publication goals?**
   - Academic paper (which venue?)
   - Tool/dataset release
   - Both

---

## Ready to Start?

**Checklist**:
- [ ] Read all documentation
- [ ] Have API keys ready (OpenRouter, Gemini)
- [ ] Have DRAC account or applied
- [ ] Know Neo4j connection details
- [ ] Have 2-3 hours to set up and test

**When ready**, start with Phase 1 and work through systematically!

Good luck! 🇨🇦🚀
