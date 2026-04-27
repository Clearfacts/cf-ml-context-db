# Ontology

## Metadata
- source_name: support_agent
- source_type: local source code
- status: source_analyzed

## Notes
- This baseline ontology file was initialized by agents/extraction_agent/setup_run.py.
- Extend this file during each run using agents/extraction_agent/schema.md and agents/extraction_agent/program.md.
- Source analyzed from `/Users/dirkvangheel/Documents/dev/projects/clearfacts/cf-ml-support-agent` using `agents/sources/support_agent.yaml`.
- The source YAML entry points use `lanchain_processors/...`, but the repository paths are `langchain_processors/...`; ontology provenance below uses the repository paths.
- Inspected runtime code paths show Freshdesk webhook intake, SQS queueing, ticket classification, and database persistence. The source YAML description also mentions "providing initial responses", but no direct response-generation flow was identified in the inspected code paths.

## Categories
```yaml
categories:
  - id: "cat_support_products_001"
    name: "Support Products"
    description: "Product domains that the support agent classifies tickets for."
    context_layer: "business_concepts"
    source: "code_analysis"
    extracted_from: "langchain_processors/prompts.py:16-22; langchain_processors/glossary.py:16-27"
    confidence_score: 0.99
  - id: "cat_clearfacts_workflows_001"
    name: "Clearfacts Workflows"
    description: "Named Clearfacts workflow stages used as classification context."
    context_layer: "business_concepts"
    source: "code_analysis"
    extracted_from: "langchain_processors/prompts.py:28-75"
    confidence_score: 0.98
  - id: "cat_kyte_modules_001"
    name: "Kyte Modules"
    description: "Named Kyte functional modules used as classification context."
    context_layer: "business_concepts"
    source: "code_analysis"
    extracted_from: "langchain_processors/prompts.py:81-118"
    confidence_score: 0.98
  - id: "cat_support_artifacts_001"
    name: "Support Artifacts"
    description: "Core ticketing and classification data artifacts handled by the system."
    context_layer: "application"
    source: "code_analysis"
    extracted_from: "ticket_classify/handlers/classify_handler.py:19-83; ticket_classify/data/repositories.py:1-57"
    confidence_score: 0.96
  - id: "cat_knowledge_assets_001"
    name: "Knowledge Assets"
    description: "Prompt and glossary assets that ground ticket understanding and classification."
    context_layer: "application"
    source: "code_analysis"
    extracted_from: "langchain_processors/prompts.py:1-420; langchain_processors/glossary.py:1-259"
    confidence_score: 0.97
  - id: "cat_classification_components_001"
    name: "Classification Components"
    description: "Application components that analyze, classify, and refine support tickets."
    context_layer: "application"
    source: "code_analysis"
    extracted_from: "langchain_processors/ticket_classifier_agent.py:21-257; langchain_processors/agents/content_analyzer.py:20-138; langchain_processors/agents/context_retriever.py:19-116; ticket_classify/services/classifier.py:91-257"
    confidence_score: 0.97
  - id: "cat_runtime_integrations_001"
    name: "Runtime Integrations"
    description: "Event-driven infrastructure components used to ingest and process tickets."
    context_layer: "technical"
    source: "code_analysis"
    extracted_from: "lambda/functions/freshdesk_webhook/freshdesk_webhook_lambda.py:16-55; ticket_classify/api/app.py:1-40"
    confidence_score: 0.97
  - id: "cat_persistence_assets_001"
    name: "Persistence Assets"
    description: "Database-backed assets used to store taxonomy and classification results."
    context_layer: "technical"
    source: "code_analysis"
    extracted_from: "ticket_classify/services/classifier.py:210-257; ticket_classify/data/repositories.py:7-57"
    confidence_score: 0.95
```

## Entities
```yaml
entities:
  - id: "entity_support_agent_system_001"
    name: "Support Agent Classification System"
    description: "Support-focused application that ingests Freshdesk tickets and classifies them for Clearfacts and Kyte using product context, LLM prompts, and database-backed taxonomy."
    context_layer: "application"
    aliases: ["support_agent", "LangChain Ticket Classification System"]
    related_terms: ["Freshdesk", "classification", "Clearfacts", "Kyte"]
    source: "code_analysis"
    extracted_from: "README.md:1-191; agents/sources/support_agent.yaml:4-17"
    confidence_score: 0.95
    ambiguous: true
    requires_validation: true
    validation_notes: "The source YAML says the agent also provides initial responses, but inspected runtime code paths show intake, classification, and persistence rather than a response-generation flow."

  - id: "entity_freshdesk_ticket_001"
    name: "Freshdesk Ticket"
    description: "Incoming support case payload carrying ticket ID, subject, and HTML description/body for downstream classification."
    context_layer: "application"
    aliases: ["ticket", "support ticket"]
    related_terms: ["ticket_subject", "ticket_description", "Freshdesk webhook"]
    source: "code_analysis"
    extracted_from: "ticket_classify/handlers/classify_handler.py:19-49; README.md:11-18"
    confidence_score: 0.98

  - id: "entity_clearfacts_001"
    name: "Clearfacts"
    description: "Pre-accounting platform by Wolters Kluwer used as one of the two primary product domains in support ticket classification."
    context_layer: "business_concepts"
    aliases: ["CF", "ClearFacts"]
    related_terms: ["AIR 2.0", "Digital Submission", "Booking Suggestions"]
    source: "code_analysis"
    extracted_from: "langchain_processors/prompts.py:16-22; langchain_processors/glossary.py:18-22"
    confidence_score: 0.99

  - id: "entity_kyte_001"
    name: "Kyte"
    description: "Smart invoicing product by Wolters Kluwer that integrates with Clearfacts and forms the second major support domain."
    context_layer: "business_concepts"
    aliases: ["KYTE"]
    related_terms: ["Facturatie", "Klantenbeheer", "Artikelbeheer"]
    source: "code_analysis"
    extracted_from: "langchain_processors/prompts.py:16-22; langchain_processors/glossary.py:23-27"
    confidence_score: 0.99

  - id: "entity_clearfacts_digital_submission_001"
    name: "Digital Submission"
    description: "Clearfacts intake stage for documents received through OCR, email, mobile app, Dropbox, CodaBox, Zoomit, or Peppol."
    context_layer: "business_concepts"
    aliases: ["Digitaal Aanleveren"]
    related_terms: ["AIR 2.0", "document intake", "OCR"]
    source: "code_analysis"
    extracted_from: "langchain_processors/prompts.py:33-38; langchain_processors/glossary.py:42-46"
    confidence_score: 0.98

  - id: "entity_clearfacts_invoice_approval_001"
    name: "Invoice Approval"
    description: "Clearfacts workflow for validating and approving purchase invoices, including multi-level approval and routing."
    context_layer: "business_concepts"
    aliases: ["Aankoopfacturen Goedkeuren", "Purchase Invoice Approval"]
    related_terms: ["approval workflow", "conditional routing"]
    source: "code_analysis"
    extracted_from: "langchain_processors/prompts.py:39-44; langchain_processors/glossary.py:47-51"
    confidence_score: 0.98

  - id: "entity_clearfacts_booking_suggestions_001"
    name: "Automatic Booking Suggestions"
    description: "Clearfacts capability that uses AI-powered recognition to propose categorization, VAT suggestions, and account codes."
    context_layer: "business_concepts"
    aliases: ["Automatische Boekingsvoorstellen", "Booking Suggestions"]
    related_terms: ["confidence score", "AI recognition", "VAT suggestion"]
    source: "code_analysis"
    extracted_from: "langchain_processors/prompts.py:45-50; langchain_processors/glossary.py:52-56"
    confidence_score: 0.98

  - id: "entity_clearfacts_optimal_booking_001"
    name: "Optimal Booking"
    description: "Clearfacts workflow for reviewing and posting transactions to accounting software with bidirectional synchronization."
    context_layer: "business_concepts"
    aliases: ["Optimaal Inboeken"]
    related_terms: ["batch posting", "accounting sync", "bidirectional sync"]
    source: "code_analysis"
    extracted_from: "langchain_processors/prompts.py:51-56; langchain_processors/glossary.py:57-61"
    confidence_score: 0.97

  - id: "entity_clearfacts_payments_001"
    name: "Payments"
    description: "Clearfacts payment preparation workflow using EPC QR codes, SEPA files, and Ponto integration."
    context_layer: "business_concepts"
    aliases: ["Betalingen"]
    related_terms: ["SEPA", "Ponto", "EPC QR"]
    source: "code_analysis"
    extracted_from: "langchain_processors/prompts.py:57-62; langchain_processors/glossary.py:62-66"
    confidence_score: 0.98

  - id: "entity_clearfacts_insights_001"
    name: "Insights"
    description: "Clearfacts dashboarding and reporting module for KPIs, analytics, and financial visibility."
    context_layer: "business_concepts"
    aliases: ["Inzicht", "Dashboard", "Reporting"]
    related_terms: ["KPI", "analytics", "business intelligence"]
    source: "code_analysis"
    extracted_from: "langchain_processors/prompts.py:63-67; langchain_processors/glossary.py:67-71"
    confidence_score: 0.97

  - id: "entity_kyte_customer_management_001"
    name: "Customer Management"
    description: "Kyte module for maintaining customer records, VAT validation, and Peppol verification."
    context_layer: "business_concepts"
    aliases: ["Klantenbeheer"]
    related_terms: ["VIES", "KBO", "customer database"]
    source: "code_analysis"
    extracted_from: "langchain_processors/prompts.py:86-93; langchain_processors/glossary.py:74-78"
    confidence_score: 0.98

  - id: "entity_kyte_article_management_001"
    name: "Article Management"
    description: "Kyte module for maintaining reusable product and service catalog data."
    context_layer: "business_concepts"
    aliases: ["Artikelbeheer"]
    related_terms: ["product catalog", "price list", "stock tracking"]
    source: "code_analysis"
    extracted_from: "langchain_processors/prompts.py:94-100; langchain_processors/glossary.py:79-83"
    confidence_score: 0.97

  - id: "entity_kyte_invoicing_001"
    name: "Invoicing"
    description: "Kyte module for creating invoices, sending them over Peppol, and handling credit notes, reminders, and recurring invoices."
    context_layer: "business_concepts"
    aliases: ["Facturatie"]
    related_terms: ["Peppol", "credit note", "recurring invoice"]
    source: "code_analysis"
    extracted_from: "langchain_processors/prompts.py:102-118; langchain_processors/glossary.py:84-88"
    confidence_score: 0.98

  - id: "entity_product_context_prompts_001"
    name: "Product Context Prompt Bundle"
    description: "Shared prompt asset that encodes product overview, workflow details, technical context, support patterns, and category examples for classification."
    context_layer: "application"
    related_terms: ["FULL_PRODUCT_CONTEXT", "CATEGORY_EXAMPLES", "PRODUCT_USAGE_EXAMPLES"]
    source: "code_analysis"
    extracted_from: "langchain_processors/prompts.py:1-420"
    confidence_score: 0.98

  - id: "entity_glossary_knowledge_base_001"
    name: "Glossary Knowledge Base"
    description: "Curated terminology dictionary covering products, features, standards, integrations, and accounting terms seen in support tickets."
    context_layer: "application"
    related_terms: ["PRODUCT_TERMS", "TECHNICAL_STANDARDS", "INTEGRATION_SYSTEMS", "BUSINESS_TERMS"]
    source: "code_analysis"
    extracted_from: "langchain_processors/glossary.py:1-259"
    confidence_score: 0.98

  - id: "entity_freshdesk_webhook_lambda_001"
    name: "Freshdesk Webhook Lambda"
    description: "AWS Lambda entry point that receives Freshdesk webhook events and forwards them to the classification SQS queue."
    context_layer: "technical"
    related_terms: ["lambda_handler", "SQS", "Freshdesk webhook"]
    source: "code_analysis"
    extracted_from: "lambda/functions/freshdesk_webhook/freshdesk_webhook_lambda.py:16-55"
    confidence_score: 0.98

  - id: "entity_classification_queue_001"
    name: "Classification Queue"
    description: "SQS queue used to decouple Freshdesk webhook receipt from downstream ticket classification processing."
    context_layer: "technical"
    aliases: ["cf-ml-support-agent classify queue"]
    related_terms: ["SQS", "MessageBody", "queue_url"]
    source: "code_analysis"
    extracted_from: "lambda/functions/freshdesk_webhook/freshdesk_webhook_lambda.py:16-41"
    confidence_score: 0.96

  - id: "entity_ticket_classify_lambda_001"
    name: "Ticket Classify Lambda Consumer"
    description: "AWS Lambda SQS consumer that processes queued records, runs ticket classification, and reports batch completion."
    context_layer: "technical"
    related_terms: ["classify_handler", "SQS consumer", "process_ticket"]
    source: "code_analysis"
    extracted_from: "ticket_classify/api/app.py:1-40; ticket_classify/handlers/classify_handler.py:19-83"
    confidence_score: 0.98

  - id: "entity_ticket_classification_agent_001"
    name: "TicketClassificationAgent"
    description: "LangChain-style orchestrator that can fetch a ticket, analyze content, retrieve context, classify a main category, optionally assign a sub-category, and save the result."
    context_layer: "application"
    related_terms: ["multi-agent", "orchestrator", "classify_ticket", "classify_batch"]
    source: "code_analysis"
    extracted_from: "langchain_processors/ticket_classifier_agent.py:21-257"
    confidence_score: 0.96
    ambiguous: true
    requires_validation: true
    validation_notes: "The repository contains both this orchestrator-based path and a separate Lambda-based classification service; production ownership between the two paths is not fully explicit from the inspected files."

  - id: "entity_content_analyzer_agent_001"
    name: "ContentAnalyzerAgent"
    description: "Sub-agent that extracts ticket features, glossary terms, urgency, sentiment, technical indicators, and a structured analysis summary."
    context_layer: "application"
    related_terms: ["TextAnalyzerTool", "FeatureExtractionTool", "smart_glossary_lookup"]
    source: "code_analysis"
    extracted_from: "langchain_processors/agents/content_analyzer.py:20-138"
    confidence_score: 0.98

  - id: "entity_context_retriever_agent_001"
    name: "ContextRetrieverAgent"
    description: "Sub-agent that retrieves similar historical tickets and summarizes classification patterns and precedents."
    context_layer: "application"
    related_terms: ["SimilarTicketTool", "historical context"]
    source: "code_analysis"
    extracted_from: "langchain_processors/agents/context_retriever.py:19-116"
    confidence_score: 0.98

  - id: "entity_classifier_agent_001"
    name: "ClassifierAgent"
    description: "Decision-making agent role that assigns the main ticket category after ticket analysis and historical-context retrieval."
    context_layer: "application"
    related_terms: ["main category", "confidence", "reasoning"]
    source: "code_analysis"
    extracted_from: "langchain_processors/ticket_classifier_agent.py:14-18; README.md:169-175"
    confidence_score: 0.93

  - id: "entity_subcategory_agent_001"
    name: "SubCategoryAgent"
    description: "Sub-category refinement component used after primary classification to assign or create level-2 categories."
    context_layer: "application"
    related_terms: ["sub-category", "level 2 taxonomy", "REACT"]
    source: "code_analysis"
    extracted_from: "langchain_processors/ticket_classifier_agent.py:17-18; langchain_processors/ticket_classifier_agent.py:163-201; README.md:73-99"
    confidence_score: 0.95

  - id: "entity_classification_taxonomy_001"
    name: "Support Agent Classification Taxonomy"
    description: "Database-backed hierarchical category model with main categories and refined sub-categories used to classify support tickets."
    context_layer: "application"
    aliases: ["support_agent_classification"]
    related_terms: ["level 1", "level 2", "main categories", "sub-categories"]
    source: "code_analysis"
    extracted_from: "README.md:39-99; ticket_classify/services/classifier.py:210-257; langchain_processors/prompts.py:251-394"
    confidence_score: 0.97
    ambiguous: true
    requires_validation: true
    validation_notes: "The classifier service prompt references category types such as 'Task Error' and 'Server Migration', while README and shared category examples center on the product/type taxonomy plus Miscellaneous; active DB categories should be validated against the deployed classification table."

  - id: "entity_ticket_mapping_repository_001"
    name: "Support Agent Ticket Mapping"
    description: "Persistence layer that upserts the selected classification ID, classification name, and reasoning for each ticket."
    context_layer: "technical"
    aliases: ["support_agent_ticket_mapping"]
    related_terms: ["upsert", "reasoning", "classification_id"]
    source: "code_analysis"
    extracted_from: "ticket_classify/data/repositories.py:7-57; README.md:71-72"
    confidence_score: 0.98
```

## Relationships
```yaml
relationships:
  - id: "rel_has_stage_001"
    name: "has_stage"
    description: "A product is organized into named workflow stages."
    directionality: "directed"
    cardinality: "one_to_many"
    semantic_type: "structure"
  - id: "rel_has_module_001"
    name: "has_module"
    description: "A product is organized into named functional modules."
    directionality: "directed"
    cardinality: "one_to_many"
    semantic_type: "structure"
  - id: "rel_uses_001"
    name: "uses"
    description: "A component depends on another component or knowledge asset during processing."
    directionality: "directed"
    cardinality: "many_to_many"
    semantic_type: "dependency"
  - id: "rel_classifies_001"
    name: "classifies"
    description: "A component assigns a classification to a ticket or ticket-like artifact."
    directionality: "directed"
    cardinality: "one_to_many"
    semantic_type: "processing"
  - id: "rel_forwards_to_001"
    name: "forwards_to"
    description: "An ingestion component forwards an event or payload to a downstream runtime destination."
    directionality: "directed"
    cardinality: "one_to_many"
    semantic_type: "event_flow"
  - id: "rel_consumes_from_001"
    name: "consumes_from"
    description: "A runtime component receives work items from a queue or upstream source."
    directionality: "directed"
    cardinality: "many_to_one"
    semantic_type: "event_flow"
  - id: "rel_persists_to_001"
    name: "persists_to"
    description: "A processing component stores output in a database-backed asset."
    directionality: "directed"
    cardinality: "many_to_one"
    semantic_type: "persistence"
  - id: "rel_orchestrates_001"
    name: "orchestrates"
    description: "A higher-level component coordinates specialized sub-components."
    directionality: "directed"
    cardinality: "one_to_many"
    semantic_type: "control_flow"
  - id: "rel_analyzes_001"
    name: "analyzes"
    description: "A component inspects ticket content to derive structured understanding."
    directionality: "directed"
    cardinality: "one_to_many"
    semantic_type: "analysis"
  - id: "rel_retrieves_context_for_001"
    name: "retrieves_context_for"
    description: "A component fetches contextual or historical information to support ticket handling."
    directionality: "directed"
    cardinality: "one_to_many"
    semantic_type: "retrieval"
  - id: "rel_refines_001"
    name: "refines"
    description: "A component refines an earlier classification result into a more specific one."
    directionality: "directed"
    cardinality: "one_to_many"
    semantic_type: "classification"
  - id: "rel_defines_001"
    name: "defines"
    description: "A knowledge asset defines business or classification concepts used elsewhere in the system."
    directionality: "directed"
    cardinality: "one_to_many"
    semantic_type: "knowledge_modeling"
```

## Associations
```yaml
associations:
  - id: "assoc_clearfacts_has_stage_digital_submission"
    source_entity_id: "entity_clearfacts_001"
    relationship_id: "rel_has_stage_001"
    target_entity_id: "entity_clearfacts_digital_submission_001"
    source: "code_analysis"
    extracted_from: "langchain_processors/prompts.py:33-38"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"
  - id: "assoc_clearfacts_has_stage_invoice_approval"
    source_entity_id: "entity_clearfacts_001"
    relationship_id: "rel_has_stage_001"
    target_entity_id: "entity_clearfacts_invoice_approval_001"
    source: "code_analysis"
    extracted_from: "langchain_processors/prompts.py:39-44"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"
  - id: "assoc_clearfacts_has_stage_booking_suggestions"
    source_entity_id: "entity_clearfacts_001"
    relationship_id: "rel_has_stage_001"
    target_entity_id: "entity_clearfacts_booking_suggestions_001"
    source: "code_analysis"
    extracted_from: "langchain_processors/prompts.py:45-50"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"
  - id: "assoc_clearfacts_has_stage_optimal_booking"
    source_entity_id: "entity_clearfacts_001"
    relationship_id: "rel_has_stage_001"
    target_entity_id: "entity_clearfacts_optimal_booking_001"
    source: "code_analysis"
    extracted_from: "langchain_processors/prompts.py:51-56"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"
  - id: "assoc_clearfacts_has_stage_payments"
    source_entity_id: "entity_clearfacts_001"
    relationship_id: "rel_has_stage_001"
    target_entity_id: "entity_clearfacts_payments_001"
    source: "code_analysis"
    extracted_from: "langchain_processors/prompts.py:57-62"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"
  - id: "assoc_clearfacts_has_stage_insights"
    source_entity_id: "entity_clearfacts_001"
    relationship_id: "rel_has_stage_001"
    target_entity_id: "entity_clearfacts_insights_001"
    source: "code_analysis"
    extracted_from: "langchain_processors/prompts.py:63-67"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"
  - id: "assoc_kyte_has_module_customer_management"
    source_entity_id: "entity_kyte_001"
    relationship_id: "rel_has_module_001"
    target_entity_id: "entity_kyte_customer_management_001"
    source: "code_analysis"
    extracted_from: "langchain_processors/prompts.py:86-93"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"
  - id: "assoc_kyte_has_module_article_management"
    source_entity_id: "entity_kyte_001"
    relationship_id: "rel_has_module_001"
    target_entity_id: "entity_kyte_article_management_001"
    source: "code_analysis"
    extracted_from: "langchain_processors/prompts.py:94-100"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"
  - id: "assoc_kyte_has_module_invoicing"
    source_entity_id: "entity_kyte_001"
    relationship_id: "rel_has_module_001"
    target_entity_id: "entity_kyte_invoicing_001"
    source: "code_analysis"
    extracted_from: "langchain_processors/prompts.py:102-118"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"
  - id: "assoc_support_system_classifies_tickets"
    source_entity_id: "entity_support_agent_system_001"
    relationship_id: "rel_classifies_001"
    target_entity_id: "entity_freshdesk_ticket_001"
    source: "code_analysis"
    extracted_from: "README.md:37-119; ticket_classify/handlers/classify_handler.py:19-83"
    confidence_score: 0.97
    implicit_or_explicit: "explicit"
  - id: "assoc_support_system_uses_prompts"
    source_entity_id: "entity_support_agent_system_001"
    relationship_id: "rel_uses_001"
    target_entity_id: "entity_product_context_prompts_001"
    source: "code_analysis"
    extracted_from: "ticket_classify/services/classifier.py:16-23; langchain_processors/agents/content_analyzer.py:42-67"
    confidence_score: 0.97
    implicit_or_explicit: "explicit"
  - id: "assoc_support_system_uses_glossary"
    source_entity_id: "entity_support_agent_system_001"
    relationship_id: "rel_uses_001"
    target_entity_id: "entity_glossary_knowledge_base_001"
    source: "code_analysis"
    extracted_from: "langchain_processors/agents/content_analyzer.py:17-18; langchain_processors/agents/content_analyzer.py:86-96"
    confidence_score: 0.95
    implicit_or_explicit: "explicit"
  - id: "assoc_support_system_uses_taxonomy"
    source_entity_id: "entity_support_agent_system_001"
    relationship_id: "rel_uses_001"
    target_entity_id: "entity_classification_taxonomy_001"
    source: "code_analysis"
    extracted_from: "README.md:39-99; ticket_classify/services/classifier.py:210-257"
    confidence_score: 0.97
    implicit_or_explicit: "explicit"
  - id: "assoc_webhook_forwards_to_queue"
    source_entity_id: "entity_freshdesk_webhook_lambda_001"
    relationship_id: "rel_forwards_to_001"
    target_entity_id: "entity_classification_queue_001"
    source: "code_analysis"
    extracted_from: "lambda/functions/freshdesk_webhook/freshdesk_webhook_lambda.py:35-41"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"
  - id: "assoc_lambda_consumes_from_queue"
    source_entity_id: "entity_ticket_classify_lambda_001"
    relationship_id: "rel_consumes_from_001"
    target_entity_id: "entity_classification_queue_001"
    source: "code_analysis"
    extracted_from: "ticket_classify/api/app.py:11-40"
    confidence_score: 0.96
    implicit_or_explicit: "explicit"
  - id: "assoc_lambda_classifies_ticket"
    source_entity_id: "entity_ticket_classify_lambda_001"
    relationship_id: "rel_classifies_001"
    target_entity_id: "entity_freshdesk_ticket_001"
    source: "code_analysis"
    extracted_from: "ticket_classify/handlers/classify_handler.py:19-83"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"
  - id: "assoc_lambda_persists_mapping"
    source_entity_id: "entity_ticket_classify_lambda_001"
    relationship_id: "rel_persists_to_001"
    target_entity_id: "entity_ticket_mapping_repository_001"
    source: "code_analysis"
    extracted_from: "ticket_classify/handlers/classify_handler.py:56-83; ticket_classify/data/repositories.py:23-57"
    confidence_score: 0.98
    implicit_or_explicit: "explicit"
  - id: "assoc_orchestrator_orchestrates_content_analyzer"
    source_entity_id: "entity_ticket_classification_agent_001"
    relationship_id: "rel_orchestrates_001"
    target_entity_id: "entity_content_analyzer_agent_001"
    source: "code_analysis"
    extracted_from: "langchain_processors/ticket_classifier_agent.py:52-57"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"
  - id: "assoc_orchestrator_orchestrates_context_retriever"
    source_entity_id: "entity_ticket_classification_agent_001"
    relationship_id: "rel_orchestrates_001"
    target_entity_id: "entity_context_retriever_agent_001"
    source: "code_analysis"
    extracted_from: "langchain_processors/ticket_classifier_agent.py:52-57"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"
  - id: "assoc_orchestrator_orchestrates_classifier"
    source_entity_id: "entity_ticket_classification_agent_001"
    relationship_id: "rel_orchestrates_001"
    target_entity_id: "entity_classifier_agent_001"
    source: "code_analysis"
    extracted_from: "langchain_processors/ticket_classifier_agent.py:52-57"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"
  - id: "assoc_orchestrator_orchestrates_subcategory"
    source_entity_id: "entity_ticket_classification_agent_001"
    relationship_id: "rel_orchestrates_001"
    target_entity_id: "entity_subcategory_agent_001"
    source: "code_analysis"
    extracted_from: "langchain_processors/ticket_classifier_agent.py:52-57"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"
  - id: "assoc_content_analyzer_analyzes_ticket"
    source_entity_id: "entity_content_analyzer_agent_001"
    relationship_id: "rel_analyzes_001"
    target_entity_id: "entity_freshdesk_ticket_001"
    source: "code_analysis"
    extracted_from: "langchain_processors/agents/content_analyzer.py:71-138"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"
  - id: "assoc_context_retriever_retrieves_ticket_context"
    source_entity_id: "entity_context_retriever_agent_001"
    relationship_id: "rel_retrieves_context_for_001"
    target_entity_id: "entity_freshdesk_ticket_001"
    source: "code_analysis"
    extracted_from: "langchain_processors/agents/context_retriever.py:70-115"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"
  - id: "assoc_classifier_uses_prompts"
    source_entity_id: "entity_classifier_agent_001"
    relationship_id: "rel_uses_001"
    target_entity_id: "entity_product_context_prompts_001"
    source: "code_analysis"
    extracted_from: "ticket_classify/services/classifier.py:16-23; README.md:169-175"
    confidence_score: 0.95
    implicit_or_explicit: "explicit"
  - id: "assoc_subcategory_refines_taxonomy"
    source_entity_id: "entity_subcategory_agent_001"
    relationship_id: "rel_refines_001"
    target_entity_id: "entity_classification_taxonomy_001"
    source: "code_analysis"
    extracted_from: "langchain_processors/ticket_classifier_agent.py:163-201; README.md:73-99"
    confidence_score: 0.95
    implicit_or_explicit: "explicit"
  - id: "assoc_prompts_define_products"
    source_entity_id: "entity_product_context_prompts_001"
    relationship_id: "rel_defines_001"
    target_entity_id: "entity_clearfacts_001"
    source: "code_analysis"
    extracted_from: "langchain_processors/prompts.py:16-118"
    confidence_score: 0.97
    implicit_or_explicit: "explicit"
  - id: "assoc_glossary_defines_kyte"
    source_entity_id: "entity_glossary_knowledge_base_001"
    relationship_id: "rel_defines_001"
    target_entity_id: "entity_kyte_001"
    source: "code_analysis"
    extracted_from: "langchain_processors/glossary.py:16-27"
    confidence_score: 0.96
    implicit_or_explicit: "explicit"
```

## Category Memberships
```yaml
category_memberships:
  - id: "catmem_clearfacts_product"
    entity_id: "entity_clearfacts_001"
    category_id: "cat_support_products_001"
    source: "code_analysis"
    confidence_score: 0.99
    notes: "Clearfacts is one of the two product domains."
  - id: "catmem_kyte_product"
    entity_id: "entity_kyte_001"
    category_id: "cat_support_products_001"
    source: "code_analysis"
    confidence_score: 0.99
    notes: "Kyte is one of the two product domains."
  - id: "catmem_ticket_artifact"
    entity_id: "entity_freshdesk_ticket_001"
    category_id: "cat_support_artifacts_001"
    source: "code_analysis"
    confidence_score: 0.98
  - id: "catmem_clearfacts_digital_submission"
    entity_id: "entity_clearfacts_digital_submission_001"
    category_id: "cat_clearfacts_workflows_001"
    source: "code_analysis"
    confidence_score: 0.98
  - id: "catmem_clearfacts_invoice_approval"
    entity_id: "entity_clearfacts_invoice_approval_001"
    category_id: "cat_clearfacts_workflows_001"
    source: "code_analysis"
    confidence_score: 0.98
  - id: "catmem_clearfacts_booking_suggestions"
    entity_id: "entity_clearfacts_booking_suggestions_001"
    category_id: "cat_clearfacts_workflows_001"
    source: "code_analysis"
    confidence_score: 0.98
  - id: "catmem_clearfacts_optimal_booking"
    entity_id: "entity_clearfacts_optimal_booking_001"
    category_id: "cat_clearfacts_workflows_001"
    source: "code_analysis"
    confidence_score: 0.97
  - id: "catmem_clearfacts_payments"
    entity_id: "entity_clearfacts_payments_001"
    category_id: "cat_clearfacts_workflows_001"
    source: "code_analysis"
    confidence_score: 0.98
  - id: "catmem_clearfacts_insights"
    entity_id: "entity_clearfacts_insights_001"
    category_id: "cat_clearfacts_workflows_001"
    source: "code_analysis"
    confidence_score: 0.97
  - id: "catmem_kyte_customer_management"
    entity_id: "entity_kyte_customer_management_001"
    category_id: "cat_kyte_modules_001"
    source: "code_analysis"
    confidence_score: 0.98
  - id: "catmem_kyte_article_management"
    entity_id: "entity_kyte_article_management_001"
    category_id: "cat_kyte_modules_001"
    source: "code_analysis"
    confidence_score: 0.97
  - id: "catmem_kyte_invoicing"
    entity_id: "entity_kyte_invoicing_001"
    category_id: "cat_kyte_modules_001"
    source: "code_analysis"
    confidence_score: 0.98
  - id: "catmem_prompt_bundle"
    entity_id: "entity_product_context_prompts_001"
    category_id: "cat_knowledge_assets_001"
    source: "code_analysis"
    confidence_score: 0.98
  - id: "catmem_glossary"
    entity_id: "entity_glossary_knowledge_base_001"
    category_id: "cat_knowledge_assets_001"
    source: "code_analysis"
    confidence_score: 0.98
  - id: "catmem_support_system"
    entity_id: "entity_support_agent_system_001"
    category_id: "cat_classification_components_001"
    source: "code_analysis"
    confidence_score: 0.95
  - id: "catmem_orchestrator"
    entity_id: "entity_ticket_classification_agent_001"
    category_id: "cat_classification_components_001"
    source: "code_analysis"
    confidence_score: 0.96
  - id: "catmem_content_analyzer"
    entity_id: "entity_content_analyzer_agent_001"
    category_id: "cat_classification_components_001"
    source: "code_analysis"
    confidence_score: 0.98
  - id: "catmem_context_retriever"
    entity_id: "entity_context_retriever_agent_001"
    category_id: "cat_classification_components_001"
    source: "code_analysis"
    confidence_score: 0.98
  - id: "catmem_classifier"
    entity_id: "entity_classifier_agent_001"
    category_id: "cat_classification_components_001"
    source: "code_analysis"
    confidence_score: 0.93
  - id: "catmem_subcategory"
    entity_id: "entity_subcategory_agent_001"
    category_id: "cat_classification_components_001"
    source: "code_analysis"
    confidence_score: 0.95
  - id: "catmem_taxonomy"
    entity_id: "entity_classification_taxonomy_001"
    category_id: "cat_support_artifacts_001"
    source: "code_analysis"
    confidence_score: 0.97
  - id: "catmem_webhook_lambda"
    entity_id: "entity_freshdesk_webhook_lambda_001"
    category_id: "cat_runtime_integrations_001"
    source: "code_analysis"
    confidence_score: 0.98
  - id: "catmem_queue"
    entity_id: "entity_classification_queue_001"
    category_id: "cat_runtime_integrations_001"
    source: "code_analysis"
    confidence_score: 0.96
  - id: "catmem_ticket_lambda"
    entity_id: "entity_ticket_classify_lambda_001"
    category_id: "cat_runtime_integrations_001"
    source: "code_analysis"
    confidence_score: 0.98
  - id: "catmem_ticket_mapping"
    entity_id: "entity_ticket_mapping_repository_001"
    category_id: "cat_persistence_assets_001"
    source: "code_analysis"
    confidence_score: 0.98
```

## Validation Notes
```yaml
validation_notes:
  - id: "validation_entry_point_typo_001"
    description: "The source YAML entry points reference `lanchain_processors`, but the repository contains `langchain_processors`."
    source: "source_yaml_and_code_comparison"
    extracted_from: "agents/sources/support_agent.yaml:10-14; cf-ml-support-agent/langchain_processors/"
    confidence_score: 0.99
  - id: "validation_response_generation_gap_001"
    description: "The YAML description mentions initial responses, but inspected runtime code paths show webhook receipt, queueing, classification, and persistence without an identified response-generation component."
    source: "code_analysis"
    extracted_from: "agents/sources/support_agent.yaml:5-7; lambda/functions/freshdesk_webhook/freshdesk_webhook_lambda.py:31-55; ticket_classify/api/app.py:11-40; ticket_classify/handlers/classify_handler.py:19-83"
    confidence_score: 0.83
  - id: "validation_taxonomy_variation_001"
    description: "The classifier service prompt includes 'Task Error' and 'Server Migration' as category types, while README and shared prompt examples emphasize the Clearfacts/Kyte issue-question-todo-feature taxonomy plus Miscellaneous."
    source: "code_analysis"
    extracted_from: "ticket_classify/services/classifier.py:134-139; README.md:45-55; langchain_processors/prompts.py:251-394"
    confidence_score: 0.9
```
