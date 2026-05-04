
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
 
## Sources 

check `agents/sources` folder for up to date list

- Business / User Level:
  - kyte website     
    - high level document example -> web scraper
  - support agent:  
    - source code -> focus on prompts and glossary terms already defined
- Application Level:
  - UI:
    - cf_accounting ui analysis:
      - UI components are split over different components / technologies 
      - more recent React projects are e.g. seperate -> cf_pay, cf_preview (sme portal), cf_werklijst
  - Backend:
    - how to capture high level data processing steps? 

## The Team 


### extraction agent:
  
  - given a source build the ontology.
    - source file can be used to tune the scope and purpose of the ontology (and the scope of the extraction run)

  - Status/TODOs:       
    - validation ideas: 
      - coverage of terms from random sample of freshdesk tickets 
      - NLI approach 
    - improvement loops:
      - extraction agent should create a validation.md file with validation notes, questions, summary of scope, ... 
      - human should review and respond in the same file. 
      - human should update the sources yaml file in case of scope changes. 
        - question: should we allow validation agents to update source yaml files? (or communicate via validation.md)
      - validation.md becomes input to the next run. 

### navigation agent:

  - purpose: validation 
  - flow:
    - validation agent (not this one) queries UI ontology for specific user flow
    - navigation agent is used to run the given flow
      - agent should be thinking at similar level of a regular user to evaluate the instructions from the ui ontology. 
      - outcomes:
        - target reached
        - unclear instructions 
        - missing steps 
        - errors
    - navigation agent reports back to validation agent


## review module 



