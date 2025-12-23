---
name: exploratory-data-analysis
description: Structured approach to exploratory data analysis with pandas, matplotlib, and seaborn. Use this skill when analyzing new datasets, understanding distributions, or preparing data for modeling.
---

# Exploratory Data Analysis (EDA)

A systematic approach to understanding datasets before modeling.

## When to Use This Skill
- User asks to "analyze a dataset" or "explore data"
- Need to understand data distributions and relationships
- Preparing data for machine learning
- Creating initial data quality reports

## EDA Workflow

### 1. Data Loading and Initial Inspection
```python
import pandas as pd
import numpy as np

# Load data
df = pd.read_csv("data.csv")

# Initial inspection
print(f"Shape: {df.shape}")
print(f"\nColumn types:\n{df.dtypes}")
print(f"\nFirst 5 rows:\n{df.head()}")
```

### 2. Missing Value Analysis
```python
# Missing values summary
missing = df.isnull().sum()
missing_pct = (missing / len(df)) * 100
missing_df = pd.DataFrame({
    'Missing Count': missing,
    'Percentage': missing_pct
}).sort_values('Percentage', ascending=False)
print(missing_df[missing_df['Missing Count'] > 0])
```

### 3. Descriptive Statistics
```python
# Numerical columns
print(df.describe())

# Categorical columns
for col in df.select_dtypes(include='object').columns:
    print(f"\n{col}:\n{df[col].value_counts()}")
```

### 4. Visualization
```python
import matplotlib.pyplot as plt
import seaborn as sns

# Set style
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("husl")

# Distribution plots for numerical columns
num_cols = df.select_dtypes(include=[np.number]).columns
fig, axes = plt.subplots(len(num_cols), 2, figsize=(12, 4*len(num_cols)))

for i, col in enumerate(num_cols):
    # Histogram
    axes[i, 0].hist(df[col].dropna(), bins=30, edgecolor='black')
    axes[i, 0].set_title(f'{col} - Distribution')
    
    # Box plot
    axes[i, 1].boxplot(df[col].dropna())
    axes[i, 1].set_title(f'{col} - Box Plot')

plt.tight_layout()
plt.savefig("distributions.png", dpi=150)
```

### 5. Correlation Analysis
```python
# Correlation heatmap
plt.figure(figsize=(10, 8))
corr = df.select_dtypes(include=[np.number]).corr()
sns.heatmap(corr, annot=True, cmap='coolwarm', center=0, 
            square=True, linewidths=0.5)
plt.title('Correlation Heatmap')
plt.tight_layout()
plt.savefig("correlation.png", dpi=150)
```

## Key Questions to Answer
1. What is the size and shape of the data?
2. What are the data types?
3. How much missing data exists?
4. What are the distributions of key variables?
5. Are there outliers?
6. What correlations exist between variables?

## Common Pitfalls
- Don't assume data is clean - always check for anomalies
- Handle missing data appropriately (don't just drop)
- Consider the context when interpreting statistics
- Save visualizations for the user to review
