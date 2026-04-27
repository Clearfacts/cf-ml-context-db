
# cf-ml-context-db

project to setup and manage the clearfacts context layers. 
we'll build an ontology to describe the clearfacts pre-accounting platform 
and related systems. 
we'll define different context layers like a business layer, application and architecture layers, 
to even more detailed technical describing databases and data processing flows.

this will be our base context system from which we'll build a series of AI agents.

## project setup 

- based on cf-ml-debug-agent.
  - copy over gitignore, cf-ml-common, mlbase, config folder
  - copy over the github workflows regarding blackduck, checkmarx and sonarqube (updating the names should be sufficient, but please check)
  - checkout README and copy over the
- main source folder: context_db
  - folder structure: similar like debug_agent
- from cf-ml-insights-agent:
  - copy over config/fab_models.yaml and the insights_agent/llm
- additional folders in context_db:
  - model (model classes), data (orm repositories)
- create data folder in project root
  

 
##  data model

- entity:
  - id
  - context_layer_id: fk
  - name: varchar
  - description: text
  - aliases: List[str]
  - related_terms: List[str]
- context_layer:
  - id
  - name
  - description
- category
  - id
  - name: (e.g. 'Accounting Concepts', 'Document Types', 'Accounting Software Systems')
  - + link table to entity (M-N rel)
- relationship
  - id
  - name
  - description
- entity_relationship
  - link table for entity (source) -> relationship -> entity (target)
 
- create ORM repository and classes
- create sql create script in sql/entity_model.sql
- database: ContextDb 
 
## The Team 


- extraction agent:
  - per component 1 folder
  - extract entities:
    - how to define entities -> see model
    - 

folder: scripts/import 

01_support_agent.sql <- convert entities defined in cf-ml-support-agent/langchain_processors/glossary.py  
and convert into insert statements. use comments and other info from the file to create initial entity types
that make sense in our setting

cf-ml-support-agent/langchain_processors/prompts.py  -> have an agent populate the tables 

validation: 

- coverage of terms from random sample of freshdesk tickets 

## review module 



