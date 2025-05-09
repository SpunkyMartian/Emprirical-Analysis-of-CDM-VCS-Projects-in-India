# Carbon Credit Project Success Analysis in India

## Project Overview

This repository contains a comprehensive analysis of carbon credit projects in India, examining both Clean Development Mechanism (CDM) and Verified Carbon Standard (VCS) projects. The goal is to identify factors that determine the success of carbon offset projects in achieving their projected emission reductions.

**Author:** Anvith  
**Date:** May 2025

---

## Research Question

**What factors determine the success of carbon credit projects in India, and do these factors differ between mandatory (CDM) and voluntary (VCS) carbon market regimes?**

---

## Project Structure

```
project/
├── data/                            
│   ├── vcs_projects_for_analysis.csv      # VCS project data
│   └── results_cdm.xlsx                   # CDM project data
├── notebooks/                       
│   ├── 1_data_preparation.ipynb           # Data cleaning and preparation
│   ├── 2_descriptive_analysis.ipynb       # Descriptive statistics and visualization
│   └── 3_regression_analysis.ipynb        # Statistical modeling and inference
├── output/                          
│   ├── figures/                           # Visualizations
│   ├── tables/                            # Statistical tables
│   ├── vcs_processed.csv                  # Processed VCS data
│   ├── cdm_processed.csv                  # Processed CDM data
│   ├── combined_projects_categorized.csv  # Combined dataset
│   └── descriptive_analysis_report.txt    # Comprehensive findings
└── README.md
```

---

## Methodology

This research follows established frameworks from literature on carbon project performance.

### Success Metric

- **Indicator**: Logarithm of actual vs. estimated emission reductions  
- **Formula**: `log(q) = log(Total Actual Emission Reductions Issued / Total Estimated Emission Reductions)`
- **Interpretation**:
  - `log(q) ≈ 0`: Project performed as expected  
  - `log(q) > 0`: Project over-performed  
  - `log(q) < 0`: Project under-performed  

### Explanatory Variables

- **Technology Type**: Wind, Solar, Hydro, Biomass & Waste, Industrial Gases, etc.  
- **Project Scale**: Small vs. Large  
- **Duration**: Logarithm of actual crediting time (log(t))  
- **Participation**: International vs. Domestic  
- **Regime**: CDM (Mandatory) vs. VCS (Voluntary)  

---

## Analysis Workflow

### 1. Data Preparation (Notebook 1)
- Data cleaning, categorization
- Calculating success metrics
- Merging CDM and VCS datasets

### 2. Descriptive Analysis (Notebook 2)
- Distribution of success indicators
- Group-wise comparisons (e.g. technology, scale)
- Statistical significance testing

### 3. Regression Analysis (Notebook 3)
- Pooled and regime-specific regression models
- Technology-specific insights
- Interaction effect evaluations

---

## Key Findings

### Success Distribution
- High variability in project performance  
- Many projects underperform relative to estimates

### Regime Differences
- CDM vs. VCS projects vary in scale, technology choice, and outcomes  
- [Insert key regime-specific insights]

### Success Determinants
- **Duration**: Shows a [positive/negative] correlation with success  
- **Scale**: [Large/small]-scale projects tend to perform better  
- **Participation**: International collaborations yield [better/worse] results  
- **Technology**: [e.g., Wind/Solar] projects have the highest success rates  

---

## How to Use This Repository

1. Start with `1_data_preparation.ipynb` to understand the raw dataset and preprocessing
2. Move to `2_descriptive_analysis.ipynb` for visual patterns and summaries
3. Review `3_regression_analysis.ipynb` for formal testing of hypotheses
4. Refer to `output/` for all saved results, figures, and processed datasets

---

## Dependencies

This project uses the following Python libraries:

- `pandas`
- `numpy`
- `matplotlib`
- `seaborn`
- `statsmodels`
- `scipy`

---

## Citation

If you use this analysis, please cite:

> Anvith. (2025). *Carbon Credit Project Success Analysis in India: Comparing CDM and VCS Regimes.*

---

## License

MIT License

Copyright (c) 2025 Anvith

Permission is hereby granted, free of charge, to any person obtaining a copy  
of this software and associated documentation files (the "Software"), to deal  
in the Software without restriction, including without limitation the rights  
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell  
copies of the Software, and to permit persons to whom the Software is  
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all  
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR  
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,  
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE  
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER  
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,  
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE  
SOFTWARE.