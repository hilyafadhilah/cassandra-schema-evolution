# Preliminary Tests

The term "preliminary tests" in our research refers to load testing a running Cassandra database
that are done for the purpose of:

1. To formulate the evolution cost model, during the development of the methodology
2. To get the fitted/calibrated function, during the evaluation of the methodology

It is not to be confused with the case study tests that are done in the evaluation stage of
our research.

## Modules

1. `prelim/scripts`: [Scripts Module 🔗](./scripts/)  
   Contains modular code that can be run on your own machine to do your own load testing.  
   *Note that we use ScyllaDB, not Cassandra*.
2. `prelim/results`: [Results Module 🔗](./results/)  
   Contains the results of **our** own load testing on our own environment, with standalone
   AI-generated scripts to process those results. Documentations on how we analyze the data to get
   the evolution cost model & the fitted functions can be found here.