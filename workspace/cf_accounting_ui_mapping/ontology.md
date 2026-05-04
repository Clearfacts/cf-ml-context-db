# Ontology

## Metadata
- source_name: cf_accounting_ui_mapping
- source_type: local source code
- status: completed
- source_location: /Users/dirkvangheel/Documents/dev/projects/clearfacts/cf-accounting
- source_location_resolution: Resolved `<parent_source_folder>/cf-accounting` from `agents/sources/cf_accounting_ui_mapping.yaml` against the parent folder of this repository.
- extraction_scope: Main client-side navigation, inbox/document-processing flows, settlements and payments, financial/history views, client settings, workflow automation, accountant monitoring entry points, payment processing hub (to-process/executed/to-approve tabs), accountant integrations (API keys/PATs), notification configuration, and Peppol inbox call-to-action in the ClearFacts accounting webapp.

## Notes
- This run-local ontology extends the initialized baseline using only source-grounded evidence from the declared `cf-accounting` repository.
- The extracted model focuses on high-value UI screens, visible business objects, primary actions, and cross-screen user journeys rather than low-level component details.
- ClearFacts and BookMate variants share part of the navigation structure. Where BookMate suppresses menu items, that difference is captured as uncertainty instead of being flattened away.

## Categories
```yaml
categories:
  - id: "cat_cf_ui_screens_001"
    name: "UI Screens"
    description: "Primary screens and navigation entry points exposed to end users in the accounting web application."
    context_layer: "application"
    source: "code_analysis"
    extracted_from: "templates/ClearFacts/clientSideNav.html.twig:1-228; assets/react/applications/business/index.tsx:27-37; assets/react/applications/workflow/WorkflowApp.tsx:11-21; src/Tactics/Bundle/AccountantBundle/Resources/views/Monitoring/monitoring.html.twig:12-113"
    confidence_score: 0.97

  - id: "cat_cf_business_objects_001"
    name: "Business Objects"
    description: "Main domain objects surfaced through the UI such as documents, settlements, payments, accounts, and automation rules."
    context_layer: "business_concepts"
    source: "code_analysis"
    extracted_from: "src/Tactics/Bundle/ClientBundle/Resources/views/Default/inbox.html.twig:23-151; assets/react/applications/business/pages/invoices/components/SettlementsTable.tsx:71-168; assets/react/applications/client-financial/components/FinancialStatements.tsx:77-135; assets/react/api/bookingAutomation/types.ts:1-42"
    confidence_score: 0.96

  - id: "cat_cf_configuration_001"
    name: "Configuration and Automation"
    description: "Configuration surfaces that let users manage dossier settings, payment settings, and booking automations."
    context_layer: "application"
    source: "code_analysis"
    extracted_from: "assets/react/applications/business/pages/client-settings/ClientSettingsPage.tsx:8-31; assets/react/applications/workflow/pages/automation/Automation.tsx:40-80; assets/react/applications/workflow/components/automation/rules/Rules.tsx:81-137"
    confidence_score: 0.97

  - id: "cat_cf_monitoring_001"
    name: "Monitoring and Integrations"
    description: "Monitoring screens and integration status surfaces for Kyte, Peppol, and related synchronization follow-up."
    context_layer: "application"
    source: "code_analysis"
    extracted_from: "src/Tactics/Bundle/AccountantBundle/Resources/views/Monitoring/monitoring.html.twig:12-113; assets/react/applications/monitoring/kyte/components/KyteTable.tsx:33-121; assets/react/applications/monitoring/peppol/components/PeppolTable.tsx:30-113"
    confidence_score: 0.96

  - id: "cat_cf_user_journeys_001"
    name: "User Journeys"
    description: "High-level user journeys supported by the application across multiple screens."
    context_layer: "application"
    source: "code_analysis"
    extracted_from: "templates/ClearFacts/clientSideNav.html.twig:21-228; src/Tactics/Bundle/ClientBundle/Resources/views/Default/inbox.html.twig:23-151; assets/react/applications/business/index.tsx:27-37; assets/react/applications/workflow/WorkflowApp.tsx:11-21; src/Tactics/Bundle/AccountantBundle/Resources/views/Monitoring/monitoring.html.twig:12-113"
    confidence_score: 0.95
```

## Entities
```yaml
entities:
  - id: "entity_client_dossier_workspace_001"
    name: "Client dossier workspace"
    description: "The main client workspace that exposes dossier navigation for document intake, sending/processing, in-progress work, communication, VAT validation, and product-specific entry points such as Kyte and Peppol."
    context_layer: "application"
    aliases: ["client workspace", "dossier workspace"]
    related_terms: ["main-nav", "client side navigation", "dossier"]
    source: "code_analysis"
    extracted_from: "templates/ClearFacts/clientSideNav.html.twig:1-228"
    confidence_score: 0.98
    ambiguous: false
    requires_validation: false
    ui_entry_points:
      - "left side navigation"
      - "client dossier shell"

  - id: "entity_purchase_inbox_screen_001"
    name: "Purchase inbox screen"
    description: "Inbox screen for incoming purchase documents where users can drop, scan, upload, filter, merge, approve, deny, download, and send purchase invoices for processing."
    context_layer: "application"
    related_terms: ["purchase", "aankoop", "document intake", "approval"]
    source: "code_analysis"
    extracted_from: "templates/ClearFacts/clientSideNav.html.twig:21-52; src/Tactics/Bundle/ClientBundle/Resources/views/Default/inbox.html.twig:23-151"
    confidence_score: 0.99
    ambiguous: false
    requires_validation: false
    screen_type: "client_document_intake"
    primary_actions:
      - "open purchase inbox"
      - "scan documents"
      - "upload documents"
      - "filter selected purchase documents"
      - "delete selected documents"
      - "merge selected documents"
      - "download original or PDF"
      - "approve or deny selected purchase documents"
      - "send selected documents to a journal/worklist"

  - id: "entity_sale_inbox_screen_001"
    name: "Sales inbox screen"
    description: "Inbox screen for incoming sales documents where users upload, scan, merge, download, and send sales invoices for processing."
    context_layer: "application"
    aliases: ["sale inbox", "verkoop inbox"]
    related_terms: ["sale", "verkoop", "document intake"]
    source: "code_analysis"
    extracted_from: "templates/ClearFacts/clientSideNav.html.twig:53-70; src/Tactics/Bundle/ClientBundle/Resources/views/Default/inbox.html.twig:27-36; src/Tactics/Bundle/ClientBundle/Resources/views/Default/inbox.html.twig:60-151"
    confidence_score: 0.97
    ambiguous: false
    requires_validation: false
    screen_type: "client_document_intake"
    primary_actions:
      - "open sales inbox"
      - "scan documents"
      - "upload documents"
      - "delete selected documents"
      - "merge selected documents"
      - "download original or PDF"
      - "send selected documents to a journal/worklist"

  - id: "entity_various_inbox_screen_001"
    name: "Various documents inbox screen"
    description: "Inbox screen for miscellaneous documents that supports the same intake pattern as purchase and sales documents, with dedicated processing for various documents."
    context_layer: "application"
    aliases: ["various inbox", "diverse documenten"]
    related_terms: ["various", "divers", "document intake"]
    source: "code_analysis"
    extracted_from: "templates/ClearFacts/clientSideNav.html.twig:71-88; src/Tactics/Bundle/ClientBundle/Resources/views/Default/inbox.html.twig:33-35; src/Tactics/Bundle/ClientBundle/Resources/views/Default/inbox.html.twig:60-151"
    confidence_score: 0.96
    ambiguous: false
    requires_validation: false
    screen_type: "client_document_intake"
    primary_actions:
      - "open various documents inbox"
      - "scan documents"
      - "upload documents"
      - "delete selected documents"
      - "merge selected documents"
      - "download original or PDF"
      - "process selected various documents"

  - id: "entity_outbox_process_screen_001"
    name: "Outbox or process screen"
    description: "Navigation target used after intake to send or process prepared documents toward the accountant, with naming and badge semantics depending on the client's annotation mode."
    context_layer: "application"
    aliases: ["outbox", "process", "verzenden"]
    related_terms: ["documents in outbox", "documents in workbox"]
    source: "code_analysis"
    extracted_from: "templates/ClearFacts/clientSideNav.html.twig:90-127"
    confidence_score: 0.88
    ambiguous: true
    requires_validation: true
    validation_notes: "The navigation behavior is explicit, but this extraction did not inspect the target outbox/process page implementation itself."
    screen_type: "client_transfer_stage"

  - id: "entity_in_progress_screen_001"
    name: "In progress screen"
    description: "Screen showing documents that are currently in processing at the accountant or shared processing flow, depending on the dossier setup."
    context_layer: "application"
    aliases: ["in verwerking"]
    related_terms: ["processing status", "accountant processing"]
    source: "code_analysis"
    extracted_from: "templates/ClearFacts/clientSideNav.html.twig:129-166"
    confidence_score: 0.9
    ambiguous: true
    requires_validation: true
    validation_notes: "Only the navigation entry point and tooltip text were inspected, not the underlying screen implementation."
    screen_type: "client_status_overview"

  - id: "entity_document_history_screen_001"
    name: "Document history screen"
    description: "History screen where users review previously processed purchase or sales documents, filter by metadata such as status/source/date, and execute row-level actions."
    context_layer: "application"
    aliases: ["documenthistoriek"]
    related_terms: ["history", "processed documents", "row actions"]
    source: "code_analysis"
    extracted_from: "src/Tactics/Bundle/ClientBundle/Resources/views/Default/menu.html.twig:40-47; assets/react/applications/client-history/HistoryPage.tsx:20-39; assets/react/applications/client-history/components/HistoryFilters.tsx:92-203; assets/react/applications/client-history/components/HistoryDataTable.tsx:49-120"
    confidence_score: 0.98
    ambiguous: false
    requires_validation: false
    screen_type: "client_audit_trail"
    primary_actions:
      - "switch between purchase and sales history"
      - "filter by name"
      - "filter by status"
      - "filter by source"
      - "filter by processed flag"
      - "filter by date range"
      - "open history actions"

  - id: "entity_financial_screen_001"
    name: "Financial screen"
    description: "Financial overview where users select a financial account, filter transactions, review financial statements, and export the visible results."
    context_layer: "application"
    aliases: ["financial", "bank overview"]
    related_terms: ["financial accounts", "transactions", "Ponto"]
    source: "code_analysis"
    extracted_from: "assets/react/applications/client-financial/FinancialPage.tsx:9-27; assets/react/applications/client-financial/components/FinancialAccounts.tsx:88-148; assets/react/applications/client-financial/components/FinancialFilters.tsx:86-223; assets/react/applications/client-financial/components/FinancialStatements.tsx:77-135"
    confidence_score: 0.98
    ambiguous: false
    requires_validation: false
    screen_type: "client_financial_overview"
    primary_actions:
      - "select a financial account"
      - "filter by counterparty"
      - "filter by incoming or outgoing direction"
      - "filter by date range"
      - "filter by amount range"
      - "filter by statement status"
      - "export visible results"

  - id: "entity_sale_settlements_screen_001"
    name: "Sales settlements screen"
    description: "Sales invoice settlement screen that lists customer-side settlements, supports filtering and pagination, and allows status updates and row actions."
    context_layer: "application"
    aliases: ["sales settlements", "sale invoices screen"]
    related_terms: ["customer", "settlement status", "pagination"]
    source: "code_analysis"
    extracted_from: "assets/react/applications/business/index.tsx:27-30; assets/react/applications/business/pages/invoices/sale/SaleSettlementsPage.tsx:19-45; assets/react/applications/business/pages/invoices/components/SettlementFilters.tsx:126-340; assets/react/applications/business/pages/invoices/components/SettlementsTable.tsx:71-168"
    confidence_score: 0.97
    ambiguous: false
    requires_validation: false
    screen_type: "client_settlement_list"

  - id: "entity_purchase_settlements_screen_001"
    name: "Purchase settlements screen"
    description: "Purchase invoice settlement screen that lists supplier-side settlements and adds payment-specific bulk actions such as moving payable documents to the payment basket."
    context_layer: "application"
    aliases: ["purchase settlements", "purchase invoices screen"]
    related_terms: ["supplier", "payable documents", "payment basket"]
    source: "code_analysis"
    extracted_from: "assets/react/applications/business/index.tsx:27-30; assets/react/applications/business/pages/invoices/purchase/PurchaseSettlementsPage.tsx:22-50; assets/react/applications/business/pages/invoices/components/SettlementFilters.tsx:126-340; assets/react/applications/business/pages/invoices/purchase/components/BulkToPaymentBasketButton.tsx:9-40; assets/react/applications/business/pages/invoices/components/SettlementsTable.tsx:71-168"
    confidence_score: 0.99
    ambiguous: false
    requires_validation: false
    screen_type: "client_settlement_list"

  - id: "entity_payment_order_history_screen_001"
    name: "Payment order history screen"
    description: "History page that displays recent payment orders and provides a direct back-navigation to the executed payments page."
    context_layer: "application"
    aliases: ["recent payment order history"]
    related_terms: ["betalingsopdrachten", "executed payments"]
    source: "code_analysis"
    extracted_from: "assets/react/applications/business/index.tsx:30-36; assets/react/applications/business/pages/payments/history/PaymentOrderHistoryPage.tsx:14-31"
    confidence_score: 0.96
    ambiguous: false
    requires_validation: false
    screen_type: "client_payment_history"

  - id: "entity_client_settings_screen_001"
    name: "Client settings screen"
    description: "Tabbed dossier settings screen exposing general settings, client details, users, and permission-gated payment settings."
    context_layer: "application"
    aliases: ["dossier settings", "client settings"]
    related_terms: ["general", "client details", "users", "payments"]
    source: "code_analysis"
    extracted_from: "assets/react/applications/business/index.tsx:31-36; assets/react/applications/business/pages/client-settings/ClientSettingsPage.tsx:8-31"
    confidence_score: 0.98
    ambiguous: false
    requires_validation: false
    screen_type: "client_configuration"
    tabs:
      - "general"
      - "client-details"
      - "users"
      - "payments"

  - id: "entity_workflow_automation_screen_001"
    name: "Workflow automation screen"
    description: "Workflow screen where users browse purchase and sales automations, create automations, rename them, activate them, and configure rule sets."
    context_layer: "application"
    aliases: ["workflow", "automation"]
    related_terms: ["purchase automation", "sales automation", "rules"]
    source: "code_analysis"
    extracted_from: "assets/react/applications/workflow/WorkflowApp.tsx:11-21; assets/react/applications/workflow/components/sidenav/SideNav.tsx:42-95; assets/react/applications/workflow/pages/automation/Automation.tsx:40-80; assets/react/applications/workflow/components/automation/header/Header.tsx:54-123; assets/react/applications/workflow/components/automation/rules/Rules.tsx:81-137"
    confidence_score: 0.99
    ambiguous: false
    requires_validation: false
    screen_type: "workflow_configuration"
    primary_actions:
      - "open purchase automations"
      - "open sales automations"
      - "create a new automation"
      - "rename an automation"
      - "toggle automation active or inactive"
      - "edit rule configuration"
      - "toggle individual rules"

  - id: "entity_accountant_monitoring_screen_001"
    name: "Accountant monitoring screen"
    description: "Tabbed monitoring area for synchronization follow-up and usage monitoring, including client invoice processing, AIR, SEPA, CodaBox, mobile, Kyte, and Peppol tabs depending on feature flags."
    context_layer: "application"
    aliases: ["monitoring"]
    related_terms: ["synchronization follow-up", "usage monitoring", "tabs"]
    source: "code_analysis"
    extracted_from: "src/Tactics/Bundle/AccountantBundle/Resources/views/Monitoring/monitoring.html.twig:12-113"
    confidence_score: 0.95
    ambiguous: true
    requires_validation: true
    validation_notes: "The Kyte and Peppol React tabs were inspected in detail, while the other server-rendered monitoring tabs were only identified from the host template."
    screen_type: "accountant_monitoring_hub"

  - id: "entity_kyte_monitoring_screen_001"
    name: "Kyte monitoring screen"
    description: "Monitoring table for Kyte adoption and activity across dossiers, including status, activation/deactivation dates, optional billable date, and period counts."
    context_layer: "application"
    aliases: ["Kyte monitoring"]
    related_terms: ["Kyte status", "activation date", "billable date"]
    source: "code_analysis"
    extracted_from: "src/Tactics/Bundle/AccountantBundle/Resources/views/Monitoring/monitoring.html.twig:57-69; assets/react/applications/monitoring/kyte/KyteMonitoring.tsx:7-13; assets/react/applications/monitoring/kyte/components/KyteFilters.tsx:55-95; assets/react/applications/monitoring/kyte/components/KyteTable.tsx:33-121"
    confidence_score: 0.98
    ambiguous: false
    requires_validation: false
    screen_type: "integration_monitoring"

  - id: "entity_peppol_monitoring_screen_001"
    name: "Peppol monitoring screen"
    description: "Monitoring table for Peppol adoption and activity across dossiers, including status, dossier metadata, counts by period, and a status information modal."
    context_layer: "application"
    aliases: ["Peppol monitoring"]
    related_terms: ["Peppol status", "counts", "status info"]
    source: "code_analysis"
    extracted_from: "src/Tactics/Bundle/AccountantBundle/Resources/views/Monitoring/monitoring.html.twig:64-70; assets/react/applications/monitoring/peppol/PeppolMonitoring.tsx:7-13; assets/react/applications/monitoring/peppol/components/PeppolFilters.tsx:69-129; assets/react/applications/monitoring/peppol/components/PeppolTable.tsx:30-113"
    confidence_score: 0.98
    ambiguous: false
    requires_validation: false
    screen_type: "integration_monitoring"

  - id: "entity_purchase_invoice_001"
    name: "Purchase invoice"
    description: "A supplier-facing document that appears in purchase intake, settlement, history, approval, and payment preparation flows."
    context_layer: "business_concepts"
    aliases: ["supplier invoice", "aankoopfactuur"]
    related_terms: ["supplier", "approval", "payment basket"]
    source: "code_analysis"
    extracted_from: "src/Tactics/Bundle/ClientBundle/Resources/views/Default/inbox.html.twig:27-29; assets/react/applications/business/pages/invoices/purchase/PurchaseSettlementsPage.tsx:22-50; assets/react/applications/client-history/HistoryPage.tsx:26-39"
    confidence_score: 0.97
    ambiguous: false
    requires_validation: false

  - id: "entity_sale_invoice_001"
    name: "Sales invoice"
    description: "A customer-facing document that appears in sales intake, settlements, and document history."
    context_layer: "business_concepts"
    aliases: ["sales document", "verkoopfactuur"]
    related_terms: ["customer", "document history"]
    source: "code_analysis"
    extracted_from: "src/Tactics/Bundle/ClientBundle/Resources/views/Default/inbox.html.twig:30-32; assets/react/applications/business/pages/invoices/sale/SaleSettlementsPage.tsx:19-45; assets/react/applications/client-history/HistoryPage.tsx:26-39"
    confidence_score: 0.96
    ambiguous: false
    requires_validation: false

  - id: "entity_various_document_001"
    name: "Various document"
    description: "A miscellaneous document category handled through its own intake lane and bulk processing path."
    context_layer: "business_concepts"
    aliases: ["diverse document"]
    related_terms: ["various inbox", "multiple process button"]
    source: "code_analysis"
    extracted_from: "templates/ClearFacts/clientSideNav.html.twig:71-88; src/Tactics/Bundle/ClientBundle/Resources/views/Default/inbox.html.twig:100-104"
    confidence_score: 0.94
    ambiguous: false
    requires_validation: false

  - id: "entity_settlement_001"
    name: "Settlement"
    description: "A settlement row representing an invoice/payment state with amounts, dates, folder, currency, status, preview links, tags, and actions."
    context_layer: "business_concepts"
    aliases: ["invoice settlement"]
    related_terms: ["outstanding amount", "payment status", "attachments"]
    source: "code_analysis"
    extracted_from: "assets/react/applications/business/pages/invoices/components/SettlementsTable.tsx:71-168"
    confidence_score: 0.98
    ambiguous: false
    requires_validation: false

  - id: "entity_payment_basket_001"
    name: "Payment basket"
    description: "The destination container for payable purchase settlements selected through the bulk 'Naar betaalmand' action."
    context_layer: "business_concepts"
    aliases: ["betaalmand"]
    related_terms: ["payable settlements", "bulk payment preparation"]
    source: "code_analysis"
    extracted_from: "assets/react/applications/business/pages/invoices/purchase/components/BulkToPaymentBasketButton.tsx:9-40"
    confidence_score: 0.97
    ambiguous: false
    requires_validation: false

  - id: "entity_payment_order_001"
    name: "Payment order"
    description: "A payment execution artifact surfaced in the recent payment order history page."
    context_layer: "business_concepts"
    aliases: ["betalingsopdracht"]
    related_terms: ["recent payment orders", "executed payments"]
    source: "code_analysis"
    extracted_from: "assets/react/applications/business/pages/payments/history/PaymentOrderHistoryPage.tsx:18-31"
    confidence_score: 0.93
    ambiguous: false
    requires_validation: false

  - id: "entity_financial_account_001"
    name: "Financial account"
    description: "A selectable financial journal/account shown with display name, IBAN, last processed date, balance, and currency in the financial overview."
    context_layer: "business_concepts"
    aliases: ["bank account", "financial journal"]
    related_terms: ["IBAN", "balance", "processed date", "Ponto"]
    source: "code_analysis"
    extracted_from: "assets/react/applications/client-financial/components/FinancialAccounts.tsx:88-148; src/Tactics/Bundle/AccountantBundle/Resources/views/ClientFinancialJournal/clientFinancialJournal.html.twig:1-118"
    confidence_score: 0.98
    ambiguous: false
    requires_validation: false

  - id: "entity_financial_statement_001"
    name: "Financial statement entry"
    description: "A financial transaction row with date, counterparty, IBAN, message, amount, and status values such as new, processed, or matched."
    context_layer: "business_concepts"
    aliases: ["financial transaction", "statement row"]
    related_terms: ["matched", "processed", "new"]
    source: "code_analysis"
    extracted_from: "assets/react/applications/client-financial/components/FinancialStatements.tsx:77-135"
    confidence_score: 0.97
    ambiguous: false
    requires_validation: false

  - id: "entity_booking_automation_001"
    name: "Booking automation"
    description: "A named purchase or sales automation that can be created, renamed, activated, and configured from the workflow screen."
    context_layer: "business_concepts"
    aliases: ["automation", "workflow automation"]
    related_terms: ["active", "inactive", "purchase automation", "sales automation"]
    source: "code_analysis"
    extracted_from: "assets/react/api/bookingAutomation/types.ts:9-15; assets/react/applications/workflow/pages/automation/Automation.tsx:40-80; assets/react/applications/workflow/components/automation/header/Header.tsx:54-123"
    confidence_score: 0.98
    ambiguous: false
    requires_validation: false

  - id: "entity_booking_automation_rule_001"
    name: "Booking automation rule"
    description: "A rule belonging to an automation, with configurable types for confidence, suppliers, amount, administrations, and document format."
    context_layer: "business_concepts"
    aliases: ["automation rule", "workflow rule"]
    related_terms: ["confidence", "suppliers", "amount", "administrations", "format"]
    source: "code_analysis"
    extracted_from: "assets/react/api/bookingAutomation/types.ts:1-7; assets/react/applications/workflow/components/automation/rules/ruleTypes.ts:1-5; assets/react/applications/workflow/components/automation/rules/Rules.tsx:32-137"
    confidence_score: 0.99
    ambiguous: false
    requires_validation: false

  - id: "entity_journey_document_intake_001"
    name: "Document intake and submission journey"
    description: "Journey where a client drops, scans, uploads, filters, optionally approves, and sends documents from inbox lanes toward accounting processing."
    context_layer: "application"
    source: "code_analysis"
    extracted_from: "templates/ClearFacts/clientSideNav.html.twig:21-166; src/Tactics/Bundle/ClientBundle/Resources/views/Default/inbox.html.twig:23-151"
    confidence_score: 0.97
    ambiguous: false
    requires_validation: false
    journey_steps:
      - "open purchase, sales, or various inbox"
      - "scan or upload documents"
      - "filter and select documents"
      - "merge, download, or approve documents when applicable"
      - "send or process selected documents"

  - id: "entity_journey_payment_preparation_001"
    name: "Settlement review and payment preparation journey"
    description: "Journey where users review settlements, update statuses, move payable purchase documents into the payment basket, and consult recent payment orders."
    context_layer: "application"
    source: "code_analysis"
    extracted_from: "assets/react/applications/business/pages/invoices/purchase/PurchaseSettlementsPage.tsx:22-50; assets/react/applications/business/pages/invoices/purchase/components/BulkToPaymentBasketButton.tsx:9-40; assets/react/applications/business/pages/payments/history/PaymentOrderHistoryPage.tsx:18-31"
    confidence_score: 0.97
    ambiguous: false
    requires_validation: false
    journey_steps:
      - "open purchase settlements"
      - "filter and review settlement rows"
      - "update payment statuses"
      - "add payable rows to the payment basket"
      - "review recent payment order history"

  - id: "entity_journey_financial_review_001"
    name: "Financial review journey"
    description: "Journey where users select financial accounts, filter transaction statements, and export the resulting financial overview."
    context_layer: "application"
    source: "code_analysis"
    extracted_from: "assets/react/applications/client-financial/FinancialPage.tsx:9-27; assets/react/applications/client-financial/components/FinancialAccounts.tsx:88-148; assets/react/applications/client-financial/components/FinancialFilters.tsx:86-223; assets/react/applications/client-financial/components/FinancialStatements.tsx:77-135"
    confidence_score: 0.98
    ambiguous: false
    requires_validation: false
    journey_steps:
      - "select all accounts or a specific account"
      - "apply financial filters"
      - "review transactions and status badges"
      - "export the filtered dataset"

  - id: "entity_journey_configuration_001"
    name: "Configuration and automation journey"
    description: "Journey where users navigate dossier settings and workflow automation screens to manage configuration, rules, and activation state."
    context_layer: "application"
    source: "code_analysis"
    extracted_from: "assets/react/applications/business/pages/client-settings/ClientSettingsPage.tsx:8-31; assets/react/applications/workflow/pages/automation/Automation.tsx:40-80; assets/react/applications/workflow/components/automation/header/Header.tsx:54-123; assets/react/applications/workflow/components/automation/rules/Rules.tsx:81-137"
    confidence_score: 0.97
    ambiguous: false
    requires_validation: false
    journey_steps:
      - "open dossier settings tabs"
      - "open workflow automation"
      - "create or select an automation"
      - "edit rules"
      - "activate or deactivate automation"

  - id: "entity_journey_integration_monitoring_001"
    name: "Integration monitoring journey"
    description: "Journey where accountant users review monitoring tabs and drill into Kyte and Peppol status information per dossier."
    context_layer: "application"
    source: "code_analysis"
    extracted_from: "src/Tactics/Bundle/AccountantBundle/Resources/views/Monitoring/monitoring.html.twig:12-113; assets/react/applications/monitoring/kyte/components/KyteTable.tsx:33-121; assets/react/applications/monitoring/peppol/components/PeppolTable.tsx:30-113"
    confidence_score: 0.95
    ambiguous: false
    requires_validation: false
    journey_steps:
      - "open monitoring"
      - "switch to Kyte or Peppol tab"
      - "filter dossiers by name or status"
      - "review counts and status badges"
      - "open client settings from monitoring rows"

  - id: "entity_payments_hub_screen_001"
    name: "Payments hub screen"
    description: "Main tabbed payment management page for clients exposing up to four tabs: Betaallijst (invoice/settlement list), Betalingen (to-approve, conditional), Uit te voeren (to-process), and Uitgevoerde (executed)."
    context_layer: "application"
    aliases: ["payments page", "client payments", "betalingen"]
    related_terms: ["Betaallijst", "Uit te voeren", "Uitgevoerde", "SEPA", "payment approval"]
    source: "code_analysis"
    extracted_from: "src/Tactics/Bundle/PaymentBundle/Resources/views/Payment/payments.html.twig:1-80"
    confidence_score: 0.98
    ambiguous: false
    requires_validation: false
    screen_type: "client_payment_hub"
    tabs:
      - "invoices (Betaallijst) — conditional on invoicesEnabled"
      - "to-approve (Betalingen) — conditional on paymentApprovalFlowEnabled"
      - "to-process (Uit te voeren)"
      - "executed (Uitgevoerde)"

  - id: "entity_to_process_payments_screen_001"
    name: "To process payments screen"
    description: "Screen listing payments that have been approved and are ready to be sent to the bank. Allows filtering by journal/IBAN and free text, setting a result limit, bulk-processing selected payments into a SEPA file, bulk-deleting, and adding a manual payment."
    context_layer: "application"
    aliases: ["Uit te voeren", "to-process", "approved payments"]
    related_terms: ["SEPA file", "process payments", "IBAN filter", "manual payment", "financial journal"]
    source: "code_analysis"
    extracted_from: "assets/react/applications/client-payments/pages/to-process/ToProcessPaymentsPage.tsx:1-250; assets/react/applications/client-payments/pages/to-process/components/ProcessPaymentsModal.tsx:1-50"
    confidence_score: 0.97
    ambiguous: false
    requires_validation: false
    screen_type: "client_payment_processing"
    primary_actions:
      - "filter by IBAN/journal"
      - "filter by free text"
      - "set result limit"
      - "select payments"
      - "bulk process selected payments (creates SEPA file)"
      - "bulk delete selected payments"
      - "add manual payment"

  - id: "entity_executed_payments_screen_001"
    name: "Executed payments screen"
    description: "Screen listing payments that have already been executed (sent to the bank). Includes an optional rejected payments sub-tab when the payment approval flow is enabled. Supports free-text filtering and back-navigation to SEPA order history."
    context_layer: "application"
    aliases: ["Uitgevoerde", "executed", "processed payments"]
    related_terms: ["Verworpen betalingen", "rejected payments", "SEPA orders executed", "payment approval flow"]
    source: "code_analysis"
    extracted_from: "assets/react/applications/client-payments/pages/executed/ExecutedPaymentsPage.tsx:1-80"
    confidence_score: 0.96
    ambiguous: false
    requires_validation: false
    screen_type: "client_payment_history"
    primary_actions:
      - "filter by free text"
      - "switch to rejected payments tab (when approval flow enabled)"
      - "navigate to SEPA order history"

  - id: "entity_to_approve_payments_screen_001"
    name: "To approve payments screen"
    description: "Payment approval screen showing payments submitted for approval, split between payments awaiting the current user's approval and payments awaiting a colleague's approval. Only accessible when the dossier's payment approval flow is enabled."
    context_layer: "application"
    aliases: ["Betalingen (approval)", "to-approve tab"]
    related_terms: ["paymentApprovalFlowEnabled", "approve payment", "deny payment", "colleague approval"]
    source: "code_analysis"
    extracted_from: "src/Tactics/Bundle/PaymentBundle/Resources/views/Payment/payments.html.twig:21-28; src/Tactics/Bundle/PaymentBundle/Resources/views/Payment/toApprove.html.twig:1-5"
    confidence_score: 0.84
    ambiguous: true
    requires_validation: true
    validation_notes: "Only the navigation entry and controller delegation were inspected; the detail React component for the approval table was not analyzed in this run."
    screen_type: "client_payment_approval"

  - id: "entity_accountant_integrations_screen_001"
    name: "Accountant integrations screen"
    description: "Accountant-level settings screen for managing API Keys and Personal Access Tokens used for external integrations. Accessible from the accountant's personal dropdown menu under 'Integraties'."
    context_layer: "application"
    aliases: ["Integraties", "integrations"]
    related_terms: ["API key", "Personal Access Token", "accountant menu"]
    source: "code_analysis"
    extracted_from: "src/Tactics/Bundle/AccountantBundle/Resources/views/Accountant/integrations.html.twig:1-18; assets/react/applications/accountant/pages/integrations/IntegrationsPage.tsx:1-100"
    confidence_score: 0.97
    ambiguous: false
    requires_validation: false
    screen_type: "accountant_integration_management"
    primary_actions:
      - "create API key"
      - "edit API key"
      - "delete API key"
      - "copy API key client ID"
      - "create Personal Access Token"
      - "delete Personal Access Token"

  - id: "entity_notification_configuration_widget_001"
    name: "Notification configuration widget"
    description: "Profile-level widget that lets users configure which email notification types they receive. Covers Peppol invoice notifications, invoice approval notifications, and payment approval notifications. Only rendered when at least one notification type is available for the user."
    context_layer: "application"
    aliases: ["Email Notifications", "notification settings"]
    related_terms: ["peppol_invoice", "invoice_approval", "payment_approval", "profile"]
    source: "code_analysis"
    extracted_from: "assets/react/applications/profile/notifications/NotificationConfigurationWidget.tsx:1-70"
    confidence_score: 0.95
    ambiguous: false
    requires_validation: false
    screen_type: "user_notification_configuration"

  - id: "entity_peppol_inbox_cta_001"
    name: "Peppol registration call-to-action"
    description: "Inline alert component rendered inside the purchase inbox when a client has not yet connected to Peppol and has not dismissed the banner. Provides a 'Start registration' button that opens the Peppol registration modal."
    context_layer: "application"
    aliases: ["Peppol CTA", "peppol-inbox-purchase-cta"]
    related_terms: ["Peppol registration", "NOT_CONNECTED", "dismiss", "RegistrationModal"]
    source: "code_analysis"
    extracted_from: "assets/react/applications/client-inbox/PeppolCallToAction/PeppolCallToAction.tsx:1-55"
    confidence_score: 0.96
    ambiguous: false
    requires_validation: false
    screen_type: "inline_call_to_action"

  - id: "entity_payment_001"
    name: "Payment"
    description: "A payment record with supplier name, IBAN, amount, currency, journal IBAN, payment date, payment reference, method, status, and approval metadata. Statuses include in_approval, approved, denied, paid, and processing."
    context_layer: "business_concepts"
    aliases: ["betaling"]
    related_terms: ["to-process payment", "executed payment", "status", "SEPA", "approval"]
    source: "code_analysis"
    extracted_from: "assets/react/api/payment/types.ts:1-30"
    confidence_score: 0.98
    ambiguous: false
    requires_validation: false

  - id: "entity_api_key_001"
    name: "API key"
    description: "An accountant-level API credential used for external integrations, with a client ID that can be copied, and lifecycle management (create, edit, delete)."
    context_layer: "business_concepts"
    aliases: ["API key", "integration key"]
    related_terms: ["client ID", "integrations", "external system"]
    source: "code_analysis"
    extracted_from: "assets/react/applications/accountant/pages/integrations/ApiKeys/ApiKeysTable.tsx:1-50; assets/react/applications/accountant/pages/integrations/IntegrationsPage.tsx:40-65"
    confidence_score: 0.96
    ambiguous: false
    requires_validation: false

  - id: "entity_personal_access_token_001"
    name: "Personal Access Token"
    description: "A personal API token tied to a user account, used for authenticating external integrations. Can be created and deleted from both the accountant integrations screen and the user profile."
    context_layer: "business_concepts"
    aliases: ["PAT", "personal token"]
    related_terms: ["API access", "token", "integrations"]
    source: "code_analysis"
    extracted_from: "assets/react/applications/accountant/pages/integrations/IntegrationsPage.tsx:65-100; assets/react/applications/profile/personalAccessTokens/PersonalAccessTokensTable.tsx"
    confidence_score: 0.93
    ambiguous: false
    requires_validation: false

  - id: "entity_journey_payment_processing_001"
    name: "Payment processing journey"
    description: "Journey where a client reviews to-process payments (approved by accountant or via approval flow), optionally filters by IBAN/journal, selects payments, processes them into a SEPA file, and then verifies the result in the executed payments screen."
    context_layer: "application"
    source: "code_analysis"
    extracted_from: "assets/react/applications/client-payments/pages/to-process/ToProcessPaymentsPage.tsx:1-250; assets/react/applications/client-payments/pages/executed/ExecutedPaymentsPage.tsx:1-80"
    confidence_score: 0.95
    ambiguous: false
    requires_validation: false
    journey_steps:
      - "open payments hub"
      - "navigate to to-process tab"
      - "filter by IBAN/journal and text"
      - "select payments to process"
      - "confirm process payments and create SEPA file"
      - "verify in executed payments tab"
```

## Relationships
```yaml
relationships:
  - id: "rel_routes_to_001"
    name: "routes_to"
    description: "A workspace or navigation surface links users to a screen."
    directionality: "directed"
    cardinality: "one_to_many"
    semantic_type: "navigation"
    reverse_name: "reachable_from"

  - id: "rel_processes_001"
    name: "processes"
    description: "A screen is used to intake, review, or process a business object."
    directionality: "directed"
    cardinality: "one_to_many"
    semantic_type: "workflow"
    reverse_name: "processed_in"

  - id: "rel_lists_001"
    name: "lists"
    description: "A screen presents a list or table of business objects."
    directionality: "directed"
    cardinality: "one_to_many"
    semantic_type: "presentation"
    reverse_name: "listed_in"

  - id: "rel_filters_001"
    name: "filters"
    description: "A screen applies filter controls over a business object collection."
    directionality: "directed"
    cardinality: "one_to_many"
    semantic_type: "interaction"
    reverse_name: "filterable_in"

  - id: "rel_configures_001"
    name: "configures"
    description: "A screen manages configuration for a target entity."
    directionality: "directed"
    cardinality: "one_to_many"
    semantic_type: "configuration"
    reverse_name: "configured_in"

  - id: "rel_contains_001"
    name: "contains"
    description: "A parent screen or business object contains another screen or object."
    directionality: "directed"
    cardinality: "one_to_many"
    semantic_type: "composition"
    reverse_name: "contained_in"

  - id: "rel_initiates_001"
    name: "initiates"
    description: "A screen or journey starts a downstream action or workflow stage."
    directionality: "directed"
    cardinality: "one_to_many"
    semantic_type: "workflow"
    reverse_name: "initiated_from"

  - id: "rel_monitors_001"
    name: "monitors"
    description: "A monitoring screen follows the status or usage of an integration or business area."
    directionality: "directed"
    cardinality: "one_to_many"
    semantic_type: "observability"
    reverse_name: "monitored_in"

  - id: "rel_uses_screen_001"
    name: "uses_screen"
    description: "A user journey traverses or depends on a UI screen."
    directionality: "directed"
    cardinality: "one_to_many"
    semantic_type: "journey_mapping"
    reverse_name: "used_in_journey"

  - id: "rel_acts_on_001"
    name: "acts_on"
    description: "A user journey manipulates or reviews a business object."
    directionality: "directed"
    cardinality: "one_to_many"
    semantic_type: "journey_mapping"
    reverse_name: "acted_on_in_journey"
```

## Associations
```yaml
associations:
  - id: "assoc_workspace_routes_purchase_inbox"
    source_entity_id: "entity_client_dossier_workspace_001"
    relationship_id: "rel_routes_to_001"
    target_entity_id: "entity_purchase_inbox_screen_001"
    source: "code_analysis"
    extracted_from: "templates/ClearFacts/clientSideNav.html.twig:21-52"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"

  - id: "assoc_workspace_routes_sale_inbox"
    source_entity_id: "entity_client_dossier_workspace_001"
    relationship_id: "rel_routes_to_001"
    target_entity_id: "entity_sale_inbox_screen_001"
    source: "code_analysis"
    extracted_from: "templates/ClearFacts/clientSideNav.html.twig:53-70"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"

  - id: "assoc_workspace_routes_various_inbox"
    source_entity_id: "entity_client_dossier_workspace_001"
    relationship_id: "rel_routes_to_001"
    target_entity_id: "entity_various_inbox_screen_001"
    source: "code_analysis"
    extracted_from: "templates/ClearFacts/clientSideNav.html.twig:71-88"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"

  - id: "assoc_workspace_routes_outbox"
    source_entity_id: "entity_client_dossier_workspace_001"
    relationship_id: "rel_routes_to_001"
    target_entity_id: "entity_outbox_process_screen_001"
    source: "code_analysis"
    extracted_from: "templates/ClearFacts/clientSideNav.html.twig:90-127"
    confidence_score: 0.94
    implicit_or_explicit: "explicit"

  - id: "assoc_workspace_routes_inprogress"
    source_entity_id: "entity_client_dossier_workspace_001"
    relationship_id: "rel_routes_to_001"
    target_entity_id: "entity_in_progress_screen_001"
    source: "code_analysis"
    extracted_from: "templates/ClearFacts/clientSideNav.html.twig:129-166"
    confidence_score: 0.94
    implicit_or_explicit: "explicit"

  - id: "assoc_purchase_inbox_processes_purchase_invoice"
    source_entity_id: "entity_purchase_inbox_screen_001"
    relationship_id: "rel_processes_001"
    target_entity_id: "entity_purchase_invoice_001"
    source: "code_analysis"
    extracted_from: "src/Tactics/Bundle/ClientBundle/Resources/views/Default/inbox.html.twig:27-29; src/Tactics/Bundle/ClientBundle/Resources/views/Default/inbox.html.twig:39-151"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"

  - id: "assoc_sale_inbox_processes_sale_invoice"
    source_entity_id: "entity_sale_inbox_screen_001"
    relationship_id: "rel_processes_001"
    target_entity_id: "entity_sale_invoice_001"
    source: "code_analysis"
    extracted_from: "src/Tactics/Bundle/ClientBundle/Resources/views/Default/inbox.html.twig:30-32; src/Tactics/Bundle/ClientBundle/Resources/views/Default/inbox.html.twig:60-151"
    confidence_score: 0.98
    implicit_or_explicit: "explicit"

  - id: "assoc_various_inbox_processes_various_document"
    source_entity_id: "entity_various_inbox_screen_001"
    relationship_id: "rel_processes_001"
    target_entity_id: "entity_various_document_001"
    source: "code_analysis"
    extracted_from: "src/Tactics/Bundle/ClientBundle/Resources/views/Default/inbox.html.twig:33-35; src/Tactics/Bundle/ClientBundle/Resources/views/Default/inbox.html.twig:100-104"
    confidence_score: 0.97
    implicit_or_explicit: "explicit"

  - id: "assoc_document_history_lists_purchase_invoice"
    source_entity_id: "entity_document_history_screen_001"
    relationship_id: "rel_lists_001"
    target_entity_id: "entity_purchase_invoice_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/client-history/HistoryPage.tsx:26-39; assets/react/applications/client-history/components/HistoryDataTable.tsx:49-120"
    confidence_score: 0.96
    implicit_or_explicit: "explicit"

  - id: "assoc_document_history_lists_sale_invoice"
    source_entity_id: "entity_document_history_screen_001"
    relationship_id: "rel_lists_001"
    target_entity_id: "entity_sale_invoice_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/client-history/HistoryPage.tsx:26-39; assets/react/applications/client-history/components/HistoryDataTable.tsx:49-120"
    confidence_score: 0.96
    implicit_or_explicit: "explicit"

  - id: "assoc_document_history_filters_invoices"
    source_entity_id: "entity_document_history_screen_001"
    relationship_id: "rel_filters_001"
    target_entity_id: "entity_purchase_invoice_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/client-history/components/HistoryFilters.tsx:92-203"
    confidence_score: 0.93
    implicit_or_explicit: "explicit"
    notes: "The filter form is shared across purchase and sales history modes."

  - id: "assoc_financial_screen_lists_accounts"
    source_entity_id: "entity_financial_screen_001"
    relationship_id: "rel_lists_001"
    target_entity_id: "entity_financial_account_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/client-financial/components/FinancialAccounts.tsx:88-148"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"

  - id: "assoc_financial_screen_lists_statements"
    source_entity_id: "entity_financial_screen_001"
    relationship_id: "rel_lists_001"
    target_entity_id: "entity_financial_statement_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/client-financial/components/FinancialStatements.tsx:77-135"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"

  - id: "assoc_financial_screen_filters_statements"
    source_entity_id: "entity_financial_screen_001"
    relationship_id: "rel_filters_001"
    target_entity_id: "entity_financial_statement_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/client-financial/components/FinancialFilters.tsx:86-223"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"

  - id: "assoc_sale_settlements_lists_settlements"
    source_entity_id: "entity_sale_settlements_screen_001"
    relationship_id: "rel_lists_001"
    target_entity_id: "entity_settlement_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/business/pages/invoices/sale/SaleSettlementsPage.tsx:19-45; assets/react/applications/business/pages/invoices/components/SettlementsTable.tsx:71-168"
    confidence_score: 0.98
    implicit_or_explicit: "explicit"

  - id: "assoc_purchase_settlements_lists_settlements"
    source_entity_id: "entity_purchase_settlements_screen_001"
    relationship_id: "rel_lists_001"
    target_entity_id: "entity_settlement_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/business/pages/invoices/purchase/PurchaseSettlementsPage.tsx:22-50; assets/react/applications/business/pages/invoices/components/SettlementsTable.tsx:71-168"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"

  - id: "assoc_purchase_settlements_filters_settlements"
    source_entity_id: "entity_purchase_settlements_screen_001"
    relationship_id: "rel_filters_001"
    target_entity_id: "entity_settlement_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/business/pages/invoices/components/SettlementFilters.tsx:126-340"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"

  - id: "assoc_sale_settlements_filters_settlements"
    source_entity_id: "entity_sale_settlements_screen_001"
    relationship_id: "rel_filters_001"
    target_entity_id: "entity_settlement_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/business/pages/invoices/components/SettlementFilters.tsx:126-340"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"

  - id: "assoc_purchase_settlements_initiates_payment_basket"
    source_entity_id: "entity_purchase_settlements_screen_001"
    relationship_id: "rel_initiates_001"
    target_entity_id: "entity_payment_basket_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/business/pages/invoices/purchase/components/BulkToPaymentBasketButton.tsx:9-40"
    confidence_score: 0.98
    implicit_or_explicit: "explicit"

  - id: "assoc_payment_history_lists_payment_orders"
    source_entity_id: "entity_payment_order_history_screen_001"
    relationship_id: "rel_lists_001"
    target_entity_id: "entity_payment_order_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/business/pages/payments/history/PaymentOrderHistoryPage.tsx:18-31"
    confidence_score: 0.95
    implicit_or_explicit: "explicit"

  - id: "assoc_client_settings_configures_workspace"
    source_entity_id: "entity_client_settings_screen_001"
    relationship_id: "rel_configures_001"
    target_entity_id: "entity_client_dossier_workspace_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/business/pages/client-settings/ClientSettingsPage.tsx:8-31"
    confidence_score: 0.91
    implicit_or_explicit: "inferred"
    notes: "The settings screen is route-scoped to a client slug and is modeled as configuring dossier-level behavior."

  - id: "assoc_workflow_screen_lists_automations"
    source_entity_id: "entity_workflow_automation_screen_001"
    relationship_id: "rel_lists_001"
    target_entity_id: "entity_booking_automation_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/workflow/components/sidenav/SideNav.tsx:62-89; assets/react/applications/workflow/pages/automation/Automation.tsx:22-39"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"

  - id: "assoc_workflow_screen_configures_automations"
    source_entity_id: "entity_workflow_automation_screen_001"
    relationship_id: "rel_configures_001"
    target_entity_id: "entity_booking_automation_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/workflow/pages/automation/Automation.tsx:40-80; assets/react/applications/workflow/components/automation/header/Header.tsx:54-123"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"

  - id: "assoc_workflow_screen_configures_rules"
    source_entity_id: "entity_workflow_automation_screen_001"
    relationship_id: "rel_configures_001"
    target_entity_id: "entity_booking_automation_rule_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/workflow/components/automation/rules/Rules.tsx:81-137; assets/react/applications/workflow/components/automation/rules/ruleTypes.ts:1-5"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"

  - id: "assoc_booking_automation_contains_rule"
    source_entity_id: "entity_booking_automation_001"
    relationship_id: "rel_contains_001"
    target_entity_id: "entity_booking_automation_rule_001"
    source: "code_analysis"
    extracted_from: "assets/react/api/bookingAutomation/types.ts:9-15"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"

  - id: "assoc_monitoring_contains_kyte"
    source_entity_id: "entity_accountant_monitoring_screen_001"
    relationship_id: "rel_contains_001"
    target_entity_id: "entity_kyte_monitoring_screen_001"
    source: "code_analysis"
    extracted_from: "src/Tactics/Bundle/AccountantBundle/Resources/views/Monitoring/monitoring.html.twig:57-63; src/Tactics/Bundle/AccountantBundle/Resources/views/Monitoring/monitoring.html.twig:103-106"
    confidence_score: 0.98
    implicit_or_explicit: "explicit"

  - id: "assoc_monitoring_contains_peppol"
    source_entity_id: "entity_accountant_monitoring_screen_001"
    relationship_id: "rel_contains_001"
    target_entity_id: "entity_peppol_monitoring_screen_001"
    source: "code_analysis"
    extracted_from: "src/Tactics/Bundle/AccountantBundle/Resources/views/Monitoring/monitoring.html.twig:64-70; src/Tactics/Bundle/AccountantBundle/Resources/views/Monitoring/monitoring.html.twig:108-111"
    confidence_score: 0.98
    implicit_or_explicit: "explicit"

  - id: "assoc_kyte_monitoring_monitors_workspace"
    source_entity_id: "entity_kyte_monitoring_screen_001"
    relationship_id: "rel_monitors_001"
    target_entity_id: "entity_client_dossier_workspace_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/monitoring/kyte/components/KyteTable.tsx:34-103"
    confidence_score: 0.9
    implicit_or_explicit: "inferred"
    notes: "Kyte monitoring rows are dossier-centric, with each row linking out to client settings by slug."

  - id: "assoc_peppol_monitoring_monitors_workspace"
    source_entity_id: "entity_peppol_monitoring_screen_001"
    relationship_id: "rel_monitors_001"
    target_entity_id: "entity_client_dossier_workspace_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/monitoring/peppol/components/PeppolTable.tsx:31-97"
    confidence_score: 0.9
    implicit_or_explicit: "inferred"
    notes: "Peppol monitoring rows are dossier-centric, with each row linking out to client settings by slug."

  - id: "assoc_journey_document_intake_uses_purchase_inbox"
    source_entity_id: "entity_journey_document_intake_001"
    relationship_id: "rel_uses_screen_001"
    target_entity_id: "entity_purchase_inbox_screen_001"
    source: "code_analysis"
    extracted_from: "templates/ClearFacts/clientSideNav.html.twig:21-52; src/Tactics/Bundle/ClientBundle/Resources/views/Default/inbox.html.twig:23-151"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"

  - id: "assoc_journey_document_intake_uses_sale_inbox"
    source_entity_id: "entity_journey_document_intake_001"
    relationship_id: "rel_uses_screen_001"
    target_entity_id: "entity_sale_inbox_screen_001"
    source: "code_analysis"
    extracted_from: "templates/ClearFacts/clientSideNav.html.twig:53-70; src/Tactics/Bundle/ClientBundle/Resources/views/Default/inbox.html.twig:23-151"
    confidence_score: 0.98
    implicit_or_explicit: "explicit"

  - id: "assoc_journey_document_intake_uses_various_inbox"
    source_entity_id: "entity_journey_document_intake_001"
    relationship_id: "rel_uses_screen_001"
    target_entity_id: "entity_various_inbox_screen_001"
    source: "code_analysis"
    extracted_from: "templates/ClearFacts/clientSideNav.html.twig:71-88; src/Tactics/Bundle/ClientBundle/Resources/views/Default/inbox.html.twig:23-151"
    confidence_score: 0.98
    implicit_or_explicit: "explicit"

  - id: "assoc_journey_document_intake_initiates_outbox"
    source_entity_id: "entity_journey_document_intake_001"
    relationship_id: "rel_initiates_001"
    target_entity_id: "entity_outbox_process_screen_001"
    source: "code_analysis"
    extracted_from: "templates/ClearFacts/clientSideNav.html.twig:90-127; src/Tactics/Bundle/ClientBundle/Resources/views/Default/inbox.html.twig:99-141"
    confidence_score: 0.94
    implicit_or_explicit: "inferred"

  - id: "assoc_journey_document_intake_acts_on_purchase_invoice"
    source_entity_id: "entity_journey_document_intake_001"
    relationship_id: "rel_acts_on_001"
    target_entity_id: "entity_purchase_invoice_001"
    source: "code_analysis"
    extracted_from: "src/Tactics/Bundle/ClientBundle/Resources/views/Default/inbox.html.twig:27-29; src/Tactics/Bundle/ClientBundle/Resources/views/Default/inbox.html.twig:39-141"
    confidence_score: 0.98
    implicit_or_explicit: "explicit"

  - id: "assoc_journey_document_intake_acts_on_sale_invoice"
    source_entity_id: "entity_journey_document_intake_001"
    relationship_id: "rel_acts_on_001"
    target_entity_id: "entity_sale_invoice_001"
    source: "code_analysis"
    extracted_from: "src/Tactics/Bundle/ClientBundle/Resources/views/Default/inbox.html.twig:30-32; src/Tactics/Bundle/ClientBundle/Resources/views/Default/inbox.html.twig:60-141"
    confidence_score: 0.97
    implicit_or_explicit: "explicit"

  - id: "assoc_journey_payment_uses_purchase_settlements"
    source_entity_id: "entity_journey_payment_preparation_001"
    relationship_id: "rel_uses_screen_001"
    target_entity_id: "entity_purchase_settlements_screen_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/business/pages/invoices/purchase/PurchaseSettlementsPage.tsx:22-50"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"

  - id: "assoc_journey_payment_uses_payment_history"
    source_entity_id: "entity_journey_payment_preparation_001"
    relationship_id: "rel_uses_screen_001"
    target_entity_id: "entity_payment_order_history_screen_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/business/pages/payments/history/PaymentOrderHistoryPage.tsx:18-31"
    confidence_score: 0.96
    implicit_or_explicit: "explicit"

  - id: "assoc_journey_payment_acts_on_settlement"
    source_entity_id: "entity_journey_payment_preparation_001"
    relationship_id: "rel_acts_on_001"
    target_entity_id: "entity_settlement_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/business/pages/invoices/components/SettlementsTable.tsx:71-168"
    confidence_score: 0.98
    implicit_or_explicit: "explicit"

  - id: "assoc_journey_payment_acts_on_payment_basket"
    source_entity_id: "entity_journey_payment_preparation_001"
    relationship_id: "rel_acts_on_001"
    target_entity_id: "entity_payment_basket_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/business/pages/invoices/purchase/components/BulkToPaymentBasketButton.tsx:9-40"
    confidence_score: 0.97
    implicit_or_explicit: "explicit"

  - id: "assoc_journey_financial_uses_financial_screen"
    source_entity_id: "entity_journey_financial_review_001"
    relationship_id: "rel_uses_screen_001"
    target_entity_id: "entity_financial_screen_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/client-financial/FinancialPage.tsx:9-27"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"

  - id: "assoc_journey_financial_acts_on_accounts"
    source_entity_id: "entity_journey_financial_review_001"
    relationship_id: "rel_acts_on_001"
    target_entity_id: "entity_financial_account_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/client-financial/components/FinancialAccounts.tsx:88-148"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"

  - id: "assoc_journey_financial_acts_on_statements"
    source_entity_id: "entity_journey_financial_review_001"
    relationship_id: "rel_acts_on_001"
    target_entity_id: "entity_financial_statement_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/client-financial/components/FinancialStatements.tsx:77-135"
    confidence_score: 0.98
    implicit_or_explicit: "explicit"

  - id: "assoc_journey_configuration_uses_settings"
    source_entity_id: "entity_journey_configuration_001"
    relationship_id: "rel_uses_screen_001"
    target_entity_id: "entity_client_settings_screen_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/business/pages/client-settings/ClientSettingsPage.tsx:8-31"
    confidence_score: 0.97
    implicit_or_explicit: "explicit"

  - id: "assoc_journey_configuration_uses_workflow"
    source_entity_id: "entity_journey_configuration_001"
    relationship_id: "rel_uses_screen_001"
    target_entity_id: "entity_workflow_automation_screen_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/workflow/WorkflowApp.tsx:11-21"
    confidence_score: 0.99
    implicit_or_explicit: "explicit"

  - id: "assoc_journey_configuration_acts_on_automation"
    source_entity_id: "entity_journey_configuration_001"
    relationship_id: "rel_acts_on_001"
    target_entity_id: "entity_booking_automation_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/workflow/pages/automation/Automation.tsx:40-80; assets/react/applications/workflow/components/automation/header/Header.tsx:54-123"
    confidence_score: 0.98
    implicit_or_explicit: "explicit"

  - id: "assoc_journey_monitoring_uses_monitoring_hub"
    source_entity_id: "entity_journey_integration_monitoring_001"
    relationship_id: "rel_uses_screen_001"
    target_entity_id: "entity_accountant_monitoring_screen_001"
    source: "code_analysis"
    extracted_from: "src/Tactics/Bundle/AccountantBundle/Resources/views/Monitoring/monitoring.html.twig:12-113"
    confidence_score: 0.97
    implicit_or_explicit: "explicit"

  - id: "assoc_journey_monitoring_uses_kyte"
    source_entity_id: "entity_journey_integration_monitoring_001"
    relationship_id: "rel_uses_screen_001"
    target_entity_id: "entity_kyte_monitoring_screen_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/monitoring/kyte/components/KyteTable.tsx:33-121"
    confidence_score: 0.98
    implicit_or_explicit: "explicit"

  - id: "assoc_journey_monitoring_uses_peppol"
    source_entity_id: "entity_journey_integration_monitoring_001"
    relationship_id: "rel_uses_screen_001"
    target_entity_id: "entity_peppol_monitoring_screen_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/monitoring/peppol/components/PeppolTable.tsx:30-113"
    confidence_score: 0.98
    implicit_or_explicit: "explicit"

  - id: "assoc_workspace_routes_payments_hub"
    source_entity_id: "entity_client_dossier_workspace_001"
    relationship_id: "rel_routes_to_001"
    target_entity_id: "entity_payments_hub_screen_001"
    source: "code_analysis"
    extracted_from: "src/Tactics/Bundle/PaymentBundle/Resources/views/Payment/payments.html.twig:1-5"
    confidence_score: 0.93
    implicit_or_explicit: "inferred"
    notes: "The payments page extends client.html.twig, confirming it is a client-side route. The precise nav entry point was not inspected in this run."

  - id: "assoc_payments_hub_contains_to_process"
    source_entity_id: "entity_payments_hub_screen_001"
    relationship_id: "rel_contains_001"
    target_entity_id: "entity_to_process_payments_screen_001"
    source: "code_analysis"
    extracted_from: "src/Tactics/Bundle/PaymentBundle/Resources/views/Payment/payments.html.twig:36-40"
    confidence_score: 0.98
    implicit_or_explicit: "explicit"

  - id: "assoc_payments_hub_contains_executed"
    source_entity_id: "entity_payments_hub_screen_001"
    relationship_id: "rel_contains_001"
    target_entity_id: "entity_executed_payments_screen_001"
    source: "code_analysis"
    extracted_from: "src/Tactics/Bundle/PaymentBundle/Resources/views/Payment/payments.html.twig:41-46"
    confidence_score: 0.98
    implicit_or_explicit: "explicit"

  - id: "assoc_payments_hub_contains_to_approve"
    source_entity_id: "entity_payments_hub_screen_001"
    relationship_id: "rel_contains_001"
    target_entity_id: "entity_to_approve_payments_screen_001"
    source: "code_analysis"
    extracted_from: "src/Tactics/Bundle/PaymentBundle/Resources/views/Payment/payments.html.twig:21-28"
    confidence_score: 0.87
    implicit_or_explicit: "explicit"
    notes: "Tab is only rendered when client.paymentApprovalFlowEnabled is true."

  - id: "assoc_to_process_lists_payment"
    source_entity_id: "entity_to_process_payments_screen_001"
    relationship_id: "rel_lists_001"
    target_entity_id: "entity_payment_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/client-payments/pages/to-process/ToProcessPaymentsPage.tsx:75-90"
    confidence_score: 0.97
    implicit_or_explicit: "explicit"

  - id: "assoc_executed_lists_payment"
    source_entity_id: "entity_executed_payments_screen_001"
    relationship_id: "rel_lists_001"
    target_entity_id: "entity_payment_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/client-payments/pages/executed/ExecutedPaymentsPage.tsx:15-40"
    confidence_score: 0.97
    implicit_or_explicit: "explicit"

  - id: "assoc_to_process_filters_payment"
    source_entity_id: "entity_to_process_payments_screen_001"
    relationship_id: "rel_filters_001"
    target_entity_id: "entity_payment_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/client-payments/pages/to-process/ToProcessPaymentsPage.tsx:85-145"
    confidence_score: 0.96
    implicit_or_explicit: "explicit"

  - id: "assoc_purchase_inbox_contains_peppol_cta"
    source_entity_id: "entity_purchase_inbox_screen_001"
    relationship_id: "rel_contains_001"
    target_entity_id: "entity_peppol_inbox_cta_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/client-inbox/PeppolCallToAction/PeppolCallToAction.tsx:1-55"
    confidence_score: 0.94
    implicit_or_explicit: "inferred"
    notes: "The PeppolCallToAction component is conditionally rendered in the purchase inbox context when the client is not yet connected to Peppol."

  - id: "assoc_integrations_screen_lists_api_keys"
    source_entity_id: "entity_accountant_integrations_screen_001"
    relationship_id: "rel_lists_001"
    target_entity_id: "entity_api_key_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/accountant/pages/integrations/IntegrationsPage.tsx:40-65; assets/react/applications/accountant/pages/integrations/ApiKeys/ApiKeysTable.tsx:1-50"
    confidence_score: 0.98
    implicit_or_explicit: "explicit"

  - id: "assoc_integrations_screen_lists_pats"
    source_entity_id: "entity_accountant_integrations_screen_001"
    relationship_id: "rel_lists_001"
    target_entity_id: "entity_personal_access_token_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/accountant/pages/integrations/IntegrationsPage.tsx:65-100"
    confidence_score: 0.97
    implicit_or_explicit: "explicit"

  - id: "assoc_integrations_screen_configures_api_keys"
    source_entity_id: "entity_accountant_integrations_screen_001"
    relationship_id: "rel_configures_001"
    target_entity_id: "entity_api_key_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/accountant/pages/integrations/IntegrationsPage.tsx:40-65"
    confidence_score: 0.97
    implicit_or_explicit: "explicit"

  - id: "assoc_integrations_screen_configures_pats"
    source_entity_id: "entity_accountant_integrations_screen_001"
    relationship_id: "rel_configures_001"
    target_entity_id: "entity_personal_access_token_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/accountant/pages/integrations/IntegrationsPage.tsx:65-100"
    confidence_score: 0.97
    implicit_or_explicit: "explicit"

  - id: "assoc_journey_payment_processing_uses_payments_hub"
    source_entity_id: "entity_journey_payment_processing_001"
    relationship_id: "rel_uses_screen_001"
    target_entity_id: "entity_payments_hub_screen_001"
    source: "code_analysis"
    extracted_from: "src/Tactics/Bundle/PaymentBundle/Resources/views/Payment/payments.html.twig:1-80"
    confidence_score: 0.95
    implicit_or_explicit: "explicit"

  - id: "assoc_journey_payment_processing_uses_to_process"
    source_entity_id: "entity_journey_payment_processing_001"
    relationship_id: "rel_uses_screen_001"
    target_entity_id: "entity_to_process_payments_screen_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/client-payments/pages/to-process/ToProcessPaymentsPage.tsx:1-250"
    confidence_score: 0.97
    implicit_or_explicit: "explicit"

  - id: "assoc_journey_payment_processing_uses_executed"
    source_entity_id: "entity_journey_payment_processing_001"
    relationship_id: "rel_uses_screen_001"
    target_entity_id: "entity_executed_payments_screen_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/client-payments/pages/executed/ExecutedPaymentsPage.tsx:1-80"
    confidence_score: 0.95
    implicit_or_explicit: "explicit"

  - id: "assoc_journey_payment_processing_acts_on_payment"
    source_entity_id: "entity_journey_payment_processing_001"
    relationship_id: "rel_acts_on_001"
    target_entity_id: "entity_payment_001"
    source: "code_analysis"
    extracted_from: "assets/react/applications/client-payments/pages/to-process/ToProcessPaymentsPage.tsx:1-250"
    confidence_score: 0.97
    implicit_or_explicit: "explicit"
```

## Category Memberships
```yaml
category_memberships:
  - id: "catmem_ui_workspace"
    entity_id: "entity_client_dossier_workspace_001"
    category_id: "cat_cf_ui_screens_001"
    source: "code_analysis"
    confidence_score: 0.99
  - id: "catmem_ui_purchase_inbox"
    entity_id: "entity_purchase_inbox_screen_001"
    category_id: "cat_cf_ui_screens_001"
    source: "code_analysis"
    confidence_score: 0.99
  - id: "catmem_ui_sale_inbox"
    entity_id: "entity_sale_inbox_screen_001"
    category_id: "cat_cf_ui_screens_001"
    source: "code_analysis"
    confidence_score: 0.98
  - id: "catmem_ui_various_inbox"
    entity_id: "entity_various_inbox_screen_001"
    category_id: "cat_cf_ui_screens_001"
    source: "code_analysis"
    confidence_score: 0.98
  - id: "catmem_ui_outbox"
    entity_id: "entity_outbox_process_screen_001"
    category_id: "cat_cf_ui_screens_001"
    source: "code_analysis"
    confidence_score: 0.92
  - id: "catmem_ui_inprogress"
    entity_id: "entity_in_progress_screen_001"
    category_id: "cat_cf_ui_screens_001"
    source: "code_analysis"
    confidence_score: 0.92
  - id: "catmem_ui_history"
    entity_id: "entity_document_history_screen_001"
    category_id: "cat_cf_ui_screens_001"
    source: "code_analysis"
    confidence_score: 0.99
  - id: "catmem_ui_financial"
    entity_id: "entity_financial_screen_001"
    category_id: "cat_cf_ui_screens_001"
    source: "code_analysis"
    confidence_score: 0.99
  - id: "catmem_ui_sale_settlements"
    entity_id: "entity_sale_settlements_screen_001"
    category_id: "cat_cf_ui_screens_001"
    source: "code_analysis"
    confidence_score: 0.98
  - id: "catmem_ui_purchase_settlements"
    entity_id: "entity_purchase_settlements_screen_001"
    category_id: "cat_cf_ui_screens_001"
    source: "code_analysis"
    confidence_score: 0.99
  - id: "catmem_ui_payment_history"
    entity_id: "entity_payment_order_history_screen_001"
    category_id: "cat_cf_ui_screens_001"
    source: "code_analysis"
    confidence_score: 0.96
  - id: "catmem_ui_settings"
    entity_id: "entity_client_settings_screen_001"
    category_id: "cat_cf_ui_screens_001"
    source: "code_analysis"
    confidence_score: 0.98
  - id: "catmem_ui_workflow"
    entity_id: "entity_workflow_automation_screen_001"
    category_id: "cat_cf_ui_screens_001"
    source: "code_analysis"
    confidence_score: 0.99
  - id: "catmem_ui_monitoring"
    entity_id: "entity_accountant_monitoring_screen_001"
    category_id: "cat_cf_ui_screens_001"
    source: "code_analysis"
    confidence_score: 0.96
  - id: "catmem_monitoring_kyte"
    entity_id: "entity_kyte_monitoring_screen_001"
    category_id: "cat_cf_monitoring_001"
    source: "code_analysis"
    confidence_score: 0.99
  - id: "catmem_monitoring_peppol"
    entity_id: "entity_peppol_monitoring_screen_001"
    category_id: "cat_cf_monitoring_001"
    source: "code_analysis"
    confidence_score: 0.99
  - id: "catmem_obj_purchase_invoice"
    entity_id: "entity_purchase_invoice_001"
    category_id: "cat_cf_business_objects_001"
    source: "code_analysis"
    confidence_score: 0.98
  - id: "catmem_obj_sale_invoice"
    entity_id: "entity_sale_invoice_001"
    category_id: "cat_cf_business_objects_001"
    source: "code_analysis"
    confidence_score: 0.97
  - id: "catmem_obj_various_document"
    entity_id: "entity_various_document_001"
    category_id: "cat_cf_business_objects_001"
    source: "code_analysis"
    confidence_score: 0.95
  - id: "catmem_obj_settlement"
    entity_id: "entity_settlement_001"
    category_id: "cat_cf_business_objects_001"
    source: "code_analysis"
    confidence_score: 0.99
  - id: "catmem_obj_payment_basket"
    entity_id: "entity_payment_basket_001"
    category_id: "cat_cf_business_objects_001"
    source: "code_analysis"
    confidence_score: 0.98
  - id: "catmem_obj_payment_order"
    entity_id: "entity_payment_order_001"
    category_id: "cat_cf_business_objects_001"
    source: "code_analysis"
    confidence_score: 0.95
  - id: "catmem_obj_financial_account"
    entity_id: "entity_financial_account_001"
    category_id: "cat_cf_business_objects_001"
    source: "code_analysis"
    confidence_score: 0.99
  - id: "catmem_obj_financial_statement"
    entity_id: "entity_financial_statement_001"
    category_id: "cat_cf_business_objects_001"
    source: "code_analysis"
    confidence_score: 0.98
  - id: "catmem_config_automation"
    entity_id: "entity_booking_automation_001"
    category_id: "cat_cf_configuration_001"
    source: "code_analysis"
    confidence_score: 0.99
  - id: "catmem_config_rule"
    entity_id: "entity_booking_automation_rule_001"
    category_id: "cat_cf_configuration_001"
    source: "code_analysis"
    confidence_score: 0.99
  - id: "catmem_journey_document_intake"
    entity_id: "entity_journey_document_intake_001"
    category_id: "cat_cf_user_journeys_001"
    source: "code_analysis"
    confidence_score: 0.99
  - id: "catmem_journey_payment"
    entity_id: "entity_journey_payment_preparation_001"
    category_id: "cat_cf_user_journeys_001"
    source: "code_analysis"
    confidence_score: 0.98
  - id: "catmem_journey_financial"
    entity_id: "entity_journey_financial_review_001"
    category_id: "cat_cf_user_journeys_001"
    source: "code_analysis"
    confidence_score: 0.99
  - id: "catmem_journey_configuration"
    entity_id: "entity_journey_configuration_001"
    category_id: "cat_cf_user_journeys_001"
    source: "code_analysis"
    confidence_score: 0.98
  - id: "catmem_journey_monitoring"
    entity_id: "entity_journey_integration_monitoring_001"
    category_id: "cat_cf_user_journeys_001"
    source: "code_analysis"
    confidence_score: 0.97
  - id: "catmem_ui_payments_hub"
    entity_id: "entity_payments_hub_screen_001"
    category_id: "cat_cf_ui_screens_001"
    source: "code_analysis"
    confidence_score: 0.98
  - id: "catmem_ui_to_process_payments"
    entity_id: "entity_to_process_payments_screen_001"
    category_id: "cat_cf_ui_screens_001"
    source: "code_analysis"
    confidence_score: 0.97
  - id: "catmem_ui_executed_payments"
    entity_id: "entity_executed_payments_screen_001"
    category_id: "cat_cf_ui_screens_001"
    source: "code_analysis"
    confidence_score: 0.96
  - id: "catmem_ui_to_approve_payments"
    entity_id: "entity_to_approve_payments_screen_001"
    category_id: "cat_cf_ui_screens_001"
    source: "code_analysis"
    confidence_score: 0.84
  - id: "catmem_ui_accountant_integrations"
    entity_id: "entity_accountant_integrations_screen_001"
    category_id: "cat_cf_monitoring_001"
    source: "code_analysis"
    confidence_score: 0.97
  - id: "catmem_obj_payment"
    entity_id: "entity_payment_001"
    category_id: "cat_cf_business_objects_001"
    source: "code_analysis"
    confidence_score: 0.98
  - id: "catmem_obj_api_key"
    entity_id: "entity_api_key_001"
    category_id: "cat_cf_business_objects_001"
    source: "code_analysis"
    confidence_score: 0.95
  - id: "catmem_obj_personal_access_token"
    entity_id: "entity_personal_access_token_001"
    category_id: "cat_cf_business_objects_001"
    source: "code_analysis"
    confidence_score: 0.93
  - id: "catmem_journey_payment_processing"
    entity_id: "entity_journey_payment_processing_001"
    category_id: "cat_cf_user_journeys_001"
    source: "code_analysis"
    confidence_score: 0.95
```

## Validation Notes
- `entity_outbox_process_screen_001` and `entity_in_progress_screen_001` are grounded in navigation evidence, but their internal page implementations were not inspected in this run.
- `entity_accountant_monitoring_screen_001` clearly exposes additional tabs beyond Kyte and Peppol (`tasks`, `client invoices`, `AIR`, `SEPA`, `CodaBox`, `mobile`), but only the Kyte and Peppol React tabs were analyzed at screen-component level.
- `src/BookMate/BookMateBundle/Resources/views/ClientDefault/menu.html.twig:3-13` suppresses the worklist, history, and help blocks inherited from the default client menu, so some client-menu capabilities vary by product variant.
- `entity_to_approve_payments_screen_001` is grounded in the host template and controller delegation only; the approval table React components were not analyzed in this run.
- `entity_notification_configuration_widget_001` is identified as a profile-level widget but its exact host page (client profile vs. standalone) was not confirmed from a navigation entry point in this run.
- The precise client-side nav entry point for `entity_payments_hub_screen_001` was not inspected (payments.html.twig extends `client.html.twig`, confirming it is client-scoped but the side-nav link was not located).
