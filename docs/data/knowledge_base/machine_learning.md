# Machine Learning Knowledge

## Supervised and unsupervised learning
Supervised learning trains on labelled examples to predict a target: classification predicts categories and regression predicts numbers. Unsupervised learning finds structure in unlabelled data, for example clustering with k-means or dimensionality reduction with PCA. Reinforcement learning learns from rewards by interacting with an environment.

## Overfitting and underfitting
Overfitting means the model memorises noise in the training data and performs poorly on unseen data. Underfitting means the model is too simple to capture the pattern. To reduce overfitting use more data, simpler models, regularization, dropout, early stopping, cross-validation and feature selection.

## Bias-variance tradeoff
Bias is error from wrong or overly simple assumptions and leads to underfitting. Variance is error from sensitivity to the specific training sample and leads to overfitting. Increasing model complexity usually lowers bias and raises variance. The aim is a balance that minimises the error on unseen data.

## Evaluation metrics
Accuracy is misleading on imbalanced data. Precision is the fraction of predicted positives that are correct. Recall is the fraction of actual positives that are found. F1 is the harmonic mean of precision and recall. Prioritise precision when false positives are costly, for example spam filters, and recall when false negatives are costly, for example disease screening. ROC-AUC and PR-AUC summarise performance across thresholds.

## Data splitting and cross-validation
Use a training set to fit the model, a validation set to tune hyperparameters and a test set held out for the final unbiased estimate. In k-fold cross-validation the data is split into k folds; the model trains k times, each time validating on a different fold, and the scores are averaged. Data leakage happens when information from validation or test data influences training, for example fitting a scaler on the full dataset.

## Handling imbalanced data
Use metrics such as precision, recall, F1 or PR-AUC. Rebalance with oversampling such as SMOTE, undersampling, class weights or threshold tuning. Use stratified splits so every fold keeps the class ratio.

## Random forests and ensembles
A random forest builds many decision trees on bootstrap samples and uses a random subset of features at each split. Predictions are averaged for regression or majority-voted for classification. This bagging approach lowers variance compared with a single deep tree. Gradient boosting builds trees sequentially, each correcting the errors of the previous ones.

## Regularization
Regularization adds a penalty on the weights to discourage complexity. L1 or Lasso penalises absolute values and can shrink weights to exactly zero, which performs feature selection. L2 or Ridge penalises squared values and shrinks weights smoothly without zeroing them. Elastic net combines both.

## Feature engineering and preprocessing
Handle missing values by dropping or imputing them. Scale numeric features for distance-based and gradient-based models. Encode categorical variables with one-hot or ordinal encoding. Fit all preprocessing on the training set only and apply it to validation and test data.

## Model deployment basics
Package the trained model with its preprocessing, expose it through an API, monitor prediction quality and data drift, and retrain when performance degrades.
