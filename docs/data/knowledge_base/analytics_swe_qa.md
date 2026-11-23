# Data Analysis, Software Engineering and QA Knowledge

## Mean versus median
The mean is the arithmetic average and is pulled by outliers. The median is the middle value and is robust to outliers and skew, so it is preferred for data such as income or house prices.

## P-values and hypothesis testing
A p-value is the probability of observing results at least as extreme as those seen, assuming the null hypothesis is true. A p-value below a chosen threshold such as 0.05 is evidence against the null hypothesis. It is not the probability that the hypothesis is true and it does not measure effect size.

## Correlation and causation
Correlation means two variables move together. Causation means a change in one produces a change in the other. Confounding variables and coincidence can create correlation without causation; randomised experiments such as A/B tests help establish causal effects.

## Missing values
First investigate why the data is missing. Options are dropping rows or columns, imputing with the mean, median, mode or a model, forward filling for time series and adding a missing-value indicator. Fit imputers on training data only and document the decision.

## Choosing charts
Use line charts for trends over time, bar charts to compare categories, scatter plots for relationships between two numeric variables, histograms for distributions and pie charts only for a small number of parts of a whole. Label axes, keep the design simple and avoid misleading scales.

## Object oriented programming
The four pillars are encapsulation, abstraction, inheritance and polymorphism. Encapsulation hides internal state behind methods, abstraction exposes only what is needed, inheritance reuses behaviour from a parent class and polymorphism lets different classes be used through a common interface.

## REST APIs
REST is a stateless client-server style where resources are identified by URLs. GET reads, POST creates, PUT replaces or updates, PATCH partially updates and DELETE removes a resource. Status codes communicate results: 200 OK, 201 Created, 400 Bad Request, 401 Unauthorized, 404 Not Found and 500 Server Error.

## Git merge and rebase
Merge joins two branches and keeps the full history with a merge commit. Rebase replays commits onto a new base to give a linear history but rewrites commits, so it should not be used on shared public branches.

## Caching
Caching keeps frequently requested results in fast storage such as memory or Redis to reduce latency and database load. The hard part is invalidation: cached data becomes stale when the source changes. Strategies include time-to-live expiry, write-through updates and explicit invalidation.

## Testing levels
Unit tests check a single function or class in isolation. Integration tests check that components work together. System and end-to-end tests check complete user flows. The test pyramid advises many unit tests, fewer integration tests and a few UI end-to-end tests.

## Verification and validation
Verification asks whether we are building the product right, by checking it against the specification through reviews and inspections. Validation asks whether we are building the right product, by checking that it meets user needs through testing.

## Smoke, sanity and regression testing
Smoke testing is a quick check that the critical functions of a new build work. Sanity testing is a narrow check that a specific fix works. Regression testing re-runs existing tests to confirm that recent changes did not break working features.

## Test design techniques
Equivalence partitioning groups inputs into classes expected to behave the same and tests one value per class. Boundary value analysis tests the edges of those classes such as the minimum, the maximum and values just outside them.

## Severity and priority
Severity is the technical impact of a defect. Priority is the business urgency of fixing it. A typical bug life cycle is New, Assigned, In Progress, Fixed, Retest, then Verified and Closed, or Reopened if the fix fails.
