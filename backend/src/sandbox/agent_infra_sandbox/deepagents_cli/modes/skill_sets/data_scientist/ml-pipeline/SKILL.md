---
name: ml-pipeline
description: Machine learning pipeline development with scikit-learn. Use this skill for training models, cross-validation, hyperparameter tuning, and model evaluation.
---

# Machine Learning Pipeline

A structured approach to building and evaluating ML models.

## When to Use This Skill
- User asks to "train a model" or "build a classifier/regressor"
- Need to evaluate model performance
- Hyperparameter tuning tasks
- Model comparison and selection

## ML Pipeline Workflow

### 1. Data Preparation
```python
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder

# Load and prepare data
df = pd.read_csv("data.csv")

# Separate features and target
X = df.drop(columns=['target'])
y = df['target']

# Handle categorical variables
le = LabelEncoder()
for col in X.select_dtypes(include='object').columns:
    X[col] = le.fit_transform(X[col].astype(str))

# Train-test split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# Scale features
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)
```

### 2. Model Training with Cross-Validation
```python
from sklearn.model_selection import cross_val_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC

# Define models to compare
models = {
    'Logistic Regression': LogisticRegression(max_iter=1000),
    'Random Forest': RandomForestClassifier(n_estimators=100, random_state=42),
    'SVM': SVC(kernel='rbf', random_state=42),
}

# Cross-validation comparison
results = {}
for name, model in models.items():
    scores = cross_val_score(model, X_train_scaled, y_train, cv=5, scoring='accuracy')
    results[name] = {
        'mean': scores.mean(),
        'std': scores.std(),
    }
    print(f"{name}: {scores.mean():.4f} (+/- {scores.std()*2:.4f})")
```

### 3. Hyperparameter Tuning
```python
from sklearn.model_selection import GridSearchCV

# Example: Random Forest tuning
param_grid = {
    'n_estimators': [100, 200, 300],
    'max_depth': [5, 10, 15, None],
    'min_samples_split': [2, 5, 10],
}

grid_search = GridSearchCV(
    RandomForestClassifier(random_state=42),
    param_grid,
    cv=5,
    scoring='accuracy',
    n_jobs=-1,
    verbose=1
)

grid_search.fit(X_train_scaled, y_train)
print(f"Best params: {grid_search.best_params_}")
print(f"Best score: {grid_search.best_score_:.4f}")
```

### 4. Model Evaluation
```python
from sklearn.metrics import (
    classification_report, confusion_matrix, 
    accuracy_score, roc_auc_score, roc_curve
)
import matplotlib.pyplot as plt
import seaborn as sns

# Get best model
best_model = grid_search.best_estimator_

# Predictions
y_pred = best_model.predict(X_test_scaled)

# Classification report
print("\nClassification Report:")
print(classification_report(y_test, y_pred))

# Confusion matrix
plt.figure(figsize=(8, 6))
cm = confusion_matrix(y_test, y_pred)
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues')
plt.title('Confusion Matrix')
plt.xlabel('Predicted')
plt.ylabel('Actual')
plt.savefig('confusion_matrix.png', dpi=150)
```

### 5. Model Saving
```python
import joblib

# Save model and scaler
joblib.dump(best_model, 'model.joblib')
joblib.dump(scaler, 'scaler.joblib')

print("Model saved to model.joblib")
```

## Key Metrics to Report
- **Classification**: Accuracy, Precision, Recall, F1, ROC-AUC
- **Regression**: MSE, RMSE, MAE, R²

## Best Practices
1. Always use cross-validation for model selection
2. Scale features for distance-based algorithms
3. Handle class imbalance if present
4. Report confidence intervals, not just point estimates
5. Save models for reproducibility
