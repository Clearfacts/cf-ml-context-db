# Ontology

## Metadata
- source_name: kyte_website
- source_type: website
- source_url: https://clearfacts.be/nl/kyte/
- status: completed
- extraction_scope: Kyte product website content at https://clearfacts.be/nl/kyte/, including the landing page, FAQ, and audience pages under /voor-wie/, plus visible body copy and in-page form text
- language: nl-BE

## Entities
```yaml
entities:
  - id: entity_kyte_001
    name: Kyte
    description: A smart invoicing tool embedded in Clearfacts that helps users create, manage, share, and send e-invoices via Peppol.
    context_layer: application
    aliases:
      - "Kyte by Clearfacts"
      - "facturatietool"
    related_terms:
      - "e-facturatie"
      - "factureren"
      - "Peppol"
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/ (hero section, feature blocks, 'Over Kyte')"
    confidence_score: 0.99
    ambiguous: false
    requires_validation: false

  - id: entity_clearfacts_001
    name: Clearfacts
    description: The Clearfacts portal/platform in which Kyte is embedded and from which customer data is immediately available.
    context_layer: application
    aliases:
      - "Clearfacts-portaal"
    related_terms:
      - "portal"
      - "platform"
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/ (hero section, feature block 'Klantgegevens direct beschikbaar')"
    confidence_score: 0.96
    ambiguous: true
    requires_validation: true
    validation_notes: The page refers to Clearfacts as both a portal and a broader integrated environment; this extraction models it as a single application entity.

  - id: entity_invoice_001
    name: Invoice
    description: A bill that Kyte helps users create, manage, share, and send correctly as part of e-invoicing.
    context_layer: business_concepts
    aliases:
      - "Factuur"
      - "E-factuur"
    related_terms:
      - "factureren"
      - "Peppol"
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/ (hero section, 'Snel, correct en digitaal', 'Over Kyte')"
    confidence_score: 0.96
    ambiguous: false
    requires_validation: false

  - id: entity_peppol_001
    name: Peppol
    description: The network/channel through which Kyte sends invoices.
    context_layer: application
    related_terms:
      - "e-facturatie"
      - "conform factureren"
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/ (hero section, feature block 'Altijd conform factureren', 'Over Kyte')"
    confidence_score: 0.98
    ambiguous: false
    requires_validation: false

  - id: entity_customer_001
    name: Customer
    description: A business object that users manage in Kyte and whose related data is available from Clearfacts.
    context_layer: business_concepts
    aliases:
      - "Klant"
    related_terms:
      - "klantgegevens"
      - "klantenbeheer"
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/ (feature block 'Klantgegevens direct beschikbaar', 'Over Kyte')"
    confidence_score: 0.93
    ambiguous: false
    requires_validation: false

  - id: entity_article_001
    name: Article
    description: A business object that users manage in Kyte alongside customers.
    context_layer: business_concepts
    aliases:
      - "Artikel"
    related_terms:
      - "artikelbeheer"
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/ ('Over Kyte')"
    confidence_score: 0.91
    ambiguous: false
    requires_validation: false

  - id: entity_peppol_e_invoice_001
    name: Peppol e-invoice
    description: A fully digital invoice exchanged via Peppol as an XML file structured according to the UBL standard.
    context_layer: business_concepts
    aliases:
      - "digitale factuur"
      - "xml-factuur"
      - "UBL-factuur"
    related_terms:
      - "Peppol"
      - "xml-bestand"
      - "UBL-standaard"
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/faq/ (Peppol explanation), https://clearfacts.be/nl/kyte/ (hero section)"
    confidence_score: 0.98
    ambiguous: false
    requires_validation: false

  - id: entity_pdf_invoice_001
    name: PDF invoice
    description: A PDF-form invoice explicitly contrasted on the Kyte FAQ page with the fully digital XML invoices exchanged through Peppol.
    context_layer: business_concepts
    aliases:
      - "pdf-factuur"
    related_terms:
      - "factuur"
      - "digitale factuur"
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/faq/ (Peppol explanation)"
    confidence_score: 0.96
    ambiguous: false
    requires_validation: false

  - id: entity_ubl_standard_001
    name: UBL standard
    description: Universal Business Language, the international standard named on the Kyte FAQ page for structuring digital business documents such as Peppol invoices.
    context_layer: technical
    aliases:
      - "Universal Business Language"
      - "UBL"
    related_terms:
      - "xml"
      - "digitale zakelijke documenten"
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/faq/ (Peppol explanation)"
    confidence_score: 0.98
    ambiguous: false
    requires_validation: false

  - id: entity_vat_number_001
    name: VAT number
    description: A VAT identifier that Kyte automatically checks and fills when compliant invoices are created.
    context_layer: business_concepts
    aliases:
      - "Btw-nummer"
    related_terms:
      - "conforme factuur"
      - "automatisch gecontroleerd"
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/voor-wie/accountants/ (conform invoice details)"
    confidence_score: 0.95
    ambiguous: false
    requires_validation: false

  - id: entity_business_address_001
    name: Business address
    description: An address field that Kyte automatically checks and fills as part of compliant invoicing.
    context_layer: business_concepts
    aliases:
      - "Adres"
    related_terms:
      - "factuurgegevens"
      - "automatisch ingevuld"
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/voor-wie/accountants/ (conform invoice details)"
    confidence_score: 0.94
    ambiguous: false
    requires_validation: false

  - id: entity_customer_activity_001
    name: Customer activity
    description: A customer-related movement or activity that flows from Kyte into Clearfacts and helps maintain live operational oversight.
    context_layer: business_concepts
    aliases:
      - "Klantbeweging"
    related_terms:
      - "live opvolging"
      - "actuele cijfers"
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/voor-wie/accountants/ (live overview), https://clearfacts.be/nl/kyte/voor-wie/kmos/ (tracking customer activity)"
    confidence_score: 0.93
    ambiguous: false
    requires_validation: false

  - id: entity_business_figures_001
    name: Business figures
    description: Current business figures or metrics that Kyte users can consult to understand where they stand and make decisions faster.
    context_layer: business_concepts
    aliases:
      - "cijfers"
      - "actuele cijfers"
    related_terms:
      - "overzicht"
      - "live opvolging"
      - "inzicht"
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/voor-wie/zelfstandigen/ (insight into figures), https://clearfacts.be/nl/kyte/voor-wie/kmos/ (see immediately where you stand), https://clearfacts.be/nl/kyte/voor-wie/accountants/ (always work with current figures)"
    confidence_score: 0.91
    ambiguous: false
    requires_validation: false

  - id: entity_administration_001
    name: Administration
    description: The administrative work and overview that Kyte keeps ordered by bringing customers, articles, and invoices together in one place.
    context_layer: business_concepts
    aliases:
      - "Administratie"
    related_terms:
      - "één plek"
      - "overzicht"
      - "op orde"
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/voor-wie/kmos/ (one place overview), https://clearfacts.be/nl/kyte/voor-wie/zelfstandigen/ (administration in the right place), https://clearfacts.be/nl/kyte/voor-wie/accountants/ (administration in order)"
    confidence_score: 0.96
    ambiguous: false
    requires_validation: false

  - id: entity_accountant_role_001
    name: Accountant
    description: A target user role for Kyte and the role that activates Kyte for entrepreneurs or SMEs.
    context_layer: business_concepts
    aliases:
      - "Accountant"
    related_terms:
      - "kantoor"
      - "klanten"
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/ ('Waarom accountants fan zijn van Kyte', demo form, 'Over Kyte')"
    confidence_score: 0.98
    ambiguous: false
    requires_validation: false

  - id: entity_entrepreneur_role_001
    name: Entrepreneur
    description: A target user role for Kyte that is instructed to ask its accountant for activation.
    context_layer: business_concepts
    aliases:
      - "Ondernemer"
      - "Zelfstandige"
    related_terms:
      - "e-facturatie"
      - "activatie"
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/ (hero section, demo form text, 'Over Kyte'), https://clearfacts.be/nl/kyte/voor-wie/zelfstandigen/"
    confidence_score: 0.95
    ambiguous: false
    requires_validation: false

  - id: entity_sme_role_001
    name: SME
    description: A target user role for Kyte that is instructed to ask its accountant for activation.
    context_layer: business_concepts
    aliases:
      - "KMO"
    related_terms:
      - "e-facturatie"
      - "activatie"
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/ (feature block 'Betrouwbare ondersteuning op maat', demo form text, 'Over Kyte')"
    confidence_score: 0.95
    ambiguous: false
    requires_validation: false

  - id: entity_e_invoicing_mandate_2026_001
    name: January 2026 e-invoicing obligation
    description: The upcoming mandatory e-invoicing requirement that the page frames as a driver for adopting Kyte.
    context_layer: business_concepts
    aliases:
      - "e-facturatie verplicht"
      - "Peppol-deadline"
    related_terms:
      - "conformiteit"
      - "futureproof"
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/ (hero section, 'E-facturatie verplicht? Jij loopt voorop')"
    confidence_score: 0.97
    ambiguous: false
    requires_validation: false

  - id: entity_support_resources_001
    name: Support resources
    description: Practical guides, videos, and help offered around Kyte for SMEs, entrepreneurs, and accountants.
    context_layer: application
    aliases:
      - "Praktische gidsen"
      - "Video's"
      - "Hulp"
    related_terms:
      - "ondersteuning"
      - "demo"
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/ (feature block 'Betrouwbare ondersteuning op maat')"
    confidence_score: 0.94
    ambiguous: false
    requires_validation: false
```

## Relationships
```yaml
relationships:
  - id: rel_integrates_with_001
    name: integrates_with
    description: Indicates that one application is embedded in or integrates seamlessly with another application.
    directionality: directed
    cardinality: many_to_one
    semantic_type: integration

  - id: rel_enables_management_of_001
    name: enables_management_of
    description: Indicates that an application enables users to create, manage, share, or otherwise handle a business object.
    directionality: directed
    cardinality: one_to_many
    semantic_type: capability

  - id: rel_validates_and_prefills_001
    name: validates_and_prefills
    description: Indicates that an application automatically checks and pre-fills key invoicing data.
    directionality: directed
    cardinality: one_to_many
    semantic_type: data_quality

  - id: rel_conforms_to_001
    name: conforms_to
    description: Indicates that a document type or data format follows a named standard.
    directionality: directed
    cardinality: many_to_one
    semantic_type: standardization

  - id: rel_contrasts_with_001
    name: contrasts_with
    description: Indicates that one document type is explicitly contrasted with another to clarify the intended digital invoicing model.
    directionality: bidirectional
    cardinality: many_to_many
    semantic_type: distinction
    reverse_name: contrasts_with

  - id: rel_flows_to_001
    name: flows_to
    description: Indicates that a document or business activity is transferred directly into another application.
    directionality: directed
    cardinality: many_to_one
    semantic_type: data_flow

  - id: rel_provides_visibility_into_001
    name: provides_visibility_into
    description: Indicates that an application gives users live or immediate visibility into a business concept, state, or metric.
    directionality: directed
    cardinality: one_to_many
    semantic_type: visibility

  - id: rel_organizes_001
    name: organizes
    description: Indicates that an application keeps an administrative domain ordered and structured.
    directionality: directed
    cardinality: one_to_many
    semantic_type: operational_support

  - id: rel_is_variant_of_001
    name: is_variant_of
    description: Indicates that one business document is a more specific form of another business document.
    directionality: directed
    cardinality: many_to_one
    semantic_type: specialization

  - id: rel_sends_via_001
    name: sends_via
    description: Indicates that an application uses a specific network or channel to send business documents.
    directionality: directed
    cardinality: one_to_many
    semantic_type: delivery_channel

  - id: rel_uses_prefilled_data_from_001
    name: uses_prefilled_data_from
    description: Indicates that an application reuses immediately available data from another application.
    directionality: directed
    cardinality: many_to_one
    semantic_type: data_dependency

  - id: rel_used_by_001
    name: used_by
    description: Indicates that a product or application is used by a particular user role.
    directionality: directed
    cardinality: many_to_many
    semantic_type: actor_usage

  - id: rel_activated_by_001
    name: activated_by
    description: Indicates that a product is activated by a particular role.
    directionality: directed
    cardinality: many_to_many
    semantic_type: onboarding

  - id: rel_requests_activation_from_001
    name: requests_activation_from
    description: Indicates that one role must ask another role to activate Kyte on its behalf.
    directionality: directed
    cardinality: many_to_one
    semantic_type: workflow

  - id: rel_addresses_001
    name: addresses
    description: Indicates that a product helps users respond to or comply with a business driver or external requirement.
    directionality: directed
    cardinality: many_to_many
    semantic_type: business_alignment

  - id: rel_provides_001
    name: provides
    description: Indicates that a product offers a supporting resource or enablement asset.
    directionality: directed
    cardinality: one_to_many
    semantic_type: enablement
```

## Associations
```yaml
associations:
  - id: assoc_kyte_integrates_with_clearfacts
    source_entity_id: entity_kyte_001
    relationship_id: rel_integrates_with_001
    target_entity_id: entity_clearfacts_001
    confidence_score: 0.99
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/ (hero section, 'Over Kyte')"
    notes: "The page says Kyte is built into and integrates seamlessly with Clearfacts."
    implicit_or_explicit: explicit

  - id: assoc_kyte_enables_management_of_invoices
    source_entity_id: entity_kyte_001
    relationship_id: rel_enables_management_of_001
    target_entity_id: entity_invoice_001
    confidence_score: 0.98
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/ (hero section, 'Snel, correct en digitaal', 'Over Kyte')"
    notes: "Kyte is described as enabling invoice creation, management, sharing, and sending."
    implicit_or_explicit: explicit

  - id: assoc_kyte_sends_via_peppol
    source_entity_id: entity_kyte_001
    relationship_id: rel_sends_via_001
    target_entity_id: entity_peppol_001
    confidence_score: 0.98
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/ (hero section, feature block 'Altijd conform factureren', 'Over Kyte')"
    notes: "The page states that invoices are sent via Peppol."
    implicit_or_explicit: explicit

  - id: assoc_kyte_uses_prefilled_data_from_clearfacts
    source_entity_id: entity_kyte_001
    relationship_id: rel_uses_prefilled_data_from_001
    target_entity_id: entity_clearfacts_001
    confidence_score: 0.95
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/ (feature block 'Klantgegevens direct beschikbaar')"
    notes: "The page says all customer data from Clearfacts is immediately ready, avoiding duplicate work."
    implicit_or_explicit: explicit

  - id: assoc_kyte_enables_management_of_customers
    source_entity_id: entity_kyte_001
    relationship_id: rel_enables_management_of_001
    target_entity_id: entity_customer_001
    confidence_score: 0.94
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/ ('Over Kyte')"
    notes: "The page states Kyte is used to manage customers."
    implicit_or_explicit: explicit

  - id: assoc_kyte_enables_management_of_articles
    source_entity_id: entity_kyte_001
    relationship_id: rel_enables_management_of_001
    target_entity_id: entity_article_001
    confidence_score: 0.92
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/ ('Over Kyte')"
    notes: "The page states Kyte is used to manage articles."
    implicit_or_explicit: explicit

  - id: assoc_kyte_enables_management_of_peppol_e_invoices
    source_entity_id: entity_kyte_001
    relationship_id: rel_enables_management_of_001
    target_entity_id: entity_peppol_e_invoice_001
    confidence_score: 0.97
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/faq/ (Peppol explanation), https://clearfacts.be/nl/kyte/ (hero section)"
    notes: "Kyte is presented as the tool for creating and sending e-invoices through Peppol; the FAQ clarifies that these are XML invoices structured with UBL."
    implicit_or_explicit: explicit

  - id: assoc_peppol_e_invoice_is_variant_of_invoice
    source_entity_id: entity_peppol_e_invoice_001
    relationship_id: rel_is_variant_of_001
    target_entity_id: entity_invoice_001
    confidence_score: 0.98
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/faq/ (Peppol explanation)"
    notes: "The FAQ describes the Peppol invoice as the digital XML form of an invoice."
    implicit_or_explicit: explicit

  - id: assoc_peppol_e_invoice_conforms_to_ubl_standard
    source_entity_id: entity_peppol_e_invoice_001
    relationship_id: rel_conforms_to_001
    target_entity_id: entity_ubl_standard_001
    confidence_score: 0.99
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/faq/ (Peppol explanation)"
    notes: "The FAQ explicitly says Peppol invoices are XML files set up according to the UBL standard."
    implicit_or_explicit: explicit

  - id: assoc_peppol_e_invoice_contrasts_with_pdf_invoice
    source_entity_id: entity_peppol_e_invoice_001
    relationship_id: rel_contrasts_with_001
    target_entity_id: entity_pdf_invoice_001
    confidence_score: 0.96
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/faq/ (Peppol explanation)"
    notes: "The FAQ explicitly contrasts Peppol invoices with PDF invoices to explain that only fully digital XML invoices are sent through the network."
    implicit_or_explicit: explicit

  - id: assoc_pdf_invoice_is_variant_of_invoice
    source_entity_id: entity_pdf_invoice_001
    relationship_id: rel_is_variant_of_001
    target_entity_id: entity_invoice_001
    confidence_score: 0.94
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/faq/ (Peppol explanation)"
    notes: "The FAQ refers to PDF invoices as a contrasting invoice form, so they are modeled as a variant of invoice."
    implicit_or_explicit: explicit

  - id: assoc_kyte_validates_and_prefills_vat_numbers
    source_entity_id: entity_kyte_001
    relationship_id: rel_validates_and_prefills_001
    target_entity_id: entity_vat_number_001
    confidence_score: 0.95
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/voor-wie/accountants/ (conform invoice details)"
    notes: "The accountants page states that VAT numbers are automatically checked and filled in."
    implicit_or_explicit: explicit

  - id: assoc_kyte_validates_and_prefills_business_addresses
    source_entity_id: entity_kyte_001
    relationship_id: rel_validates_and_prefills_001
    target_entity_id: entity_business_address_001
    confidence_score: 0.94
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/voor-wie/accountants/ (conform invoice details)"
    notes: "The accountants page states that addresses are automatically checked and filled in."
    implicit_or_explicit: explicit

  - id: assoc_invoice_flows_to_clearfacts
    source_entity_id: entity_invoice_001
    relationship_id: rel_flows_to_001
    target_entity_id: entity_clearfacts_001
    confidence_score: 0.95
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/voor-wie/accountants/ (live overview)"
    notes: "The accountants page says every invoice flows directly through to Clearfacts."
    implicit_or_explicit: explicit

  - id: assoc_customer_activity_flows_to_clearfacts
    source_entity_id: entity_customer_activity_001
    relationship_id: rel_flows_to_001
    target_entity_id: entity_clearfacts_001
    confidence_score: 0.93
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/voor-wie/accountants/ (live overview), https://clearfacts.be/nl/kyte/voor-wie/kmos/ (tracking customer activity)"
    notes: "Customer activity is described as flowing into Clearfacts and being tracked for live oversight."
    implicit_or_explicit: explicit

  - id: assoc_kyte_provides_visibility_into_business_figures
    source_entity_id: entity_kyte_001
    relationship_id: rel_provides_visibility_into_001
    target_entity_id: entity_business_figures_001
    confidence_score: 0.91
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/voor-wie/zelfstandigen/ (insight into figures), https://clearfacts.be/nl/kyte/voor-wie/kmos/ (see immediately where you stand)"
    notes: "The self-employed and SME pages say Kyte helps users gain insight into their figures and quickly see where they stand."
    implicit_or_explicit: explicit

  - id: assoc_clearfacts_provides_visibility_into_business_figures
    source_entity_id: entity_clearfacts_001
    relationship_id: rel_provides_visibility_into_001
    target_entity_id: entity_business_figures_001
    confidence_score: 0.89
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/voor-wie/accountants/ (always work with current figures)"
    notes: "The accountants page says work becomes immediately visible in Clearfacts and accountants always work with current figures."
    implicit_or_explicit: explicit

  - id: assoc_kyte_organizes_administration
    source_entity_id: entity_kyte_001
    relationship_id: rel_organizes_001
    target_entity_id: entity_administration_001
    confidence_score: 0.96
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/voor-wie/kmos/ (one place overview), https://clearfacts.be/nl/kyte/voor-wie/zelfstandigen/ (administration in the right place), https://clearfacts.be/nl/kyte/voor-wie/accountants/ (administration in order)"
    notes: "Across the audience pages, Kyte is described as keeping administration in order by bringing key records together in one overview."
    implicit_or_explicit: explicit

  - id: assoc_kyte_used_by_accountants
    source_entity_id: entity_kyte_001
    relationship_id: rel_used_by_001
    target_entity_id: entity_accountant_role_001
    confidence_score: 0.98
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/ ('Waarom accountants fan zijn van Kyte', 'Over Kyte')"
    notes: "Accountants are explicitly named as Kyte users and beneficiaries."
    implicit_or_explicit: explicit

  - id: assoc_kyte_used_by_entrepreneurs
    source_entity_id: entity_kyte_001
    relationship_id: rel_used_by_001
    target_entity_id: entity_entrepreneur_role_001
    confidence_score: 0.96
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/ (hero section, demo form text, 'Over Kyte')"
    notes: "Entrepreneurs are explicitly named as Kyte users."
    implicit_or_explicit: explicit

  - id: assoc_kyte_used_by_smes
    source_entity_id: entity_kyte_001
    relationship_id: rel_used_by_001
    target_entity_id: entity_sme_role_001
    confidence_score: 0.96
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/ (feature block 'Betrouwbare ondersteuning op maat', demo form text, 'Over Kyte')"
    notes: "SMEs are explicitly named as Kyte users."
    implicit_or_explicit: explicit

  - id: assoc_kyte_activated_by_accountants
    source_entity_id: entity_kyte_001
    relationship_id: rel_activated_by_001
    target_entity_id: entity_accountant_role_001
    confidence_score: 0.93
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/ (demo form text), https://clearfacts.be/nl/kyte/faq/ (activation explanation), https://clearfacts.be/nl/kyte/voor-wie/kmos/ (activation explanation), https://clearfacts.be/nl/kyte/voor-wie/zelfstandigen/ (activation explanation)"
    notes: "The product, FAQ, and audience pages all say accountants activate Kyte for entrepreneurs and SMEs."
    implicit_or_explicit: explicit

  - id: assoc_entrepreneur_requests_activation_from_accountant
    source_entity_id: entity_entrepreneur_role_001
    relationship_id: rel_requests_activation_from_001
    target_entity_id: entity_accountant_role_001
    confidence_score: 0.94
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/ (demo form text), https://clearfacts.be/nl/kyte/faq/ (activation explanation), https://clearfacts.be/nl/kyte/voor-wie/zelfstandigen/ (activation explanation)"
    notes: "Entrepreneurs/self-employed users are instructed to ask their accountant to activate Kyte."
    implicit_or_explicit: explicit

  - id: assoc_sme_requests_activation_from_accountant
    source_entity_id: entity_sme_role_001
    relationship_id: rel_requests_activation_from_001
    target_entity_id: entity_accountant_role_001
    confidence_score: 0.94
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/ (demo form text), https://clearfacts.be/nl/kyte/faq/ (activation explanation), https://clearfacts.be/nl/kyte/voor-wie/kmos/ (activation explanation)"
    notes: "SMEs are instructed to ask their accountant to activate Kyte."
    implicit_or_explicit: explicit

  - id: assoc_kyte_addresses_e_invoicing_mandate
    source_entity_id: entity_kyte_001
    relationship_id: rel_addresses_001
    target_entity_id: entity_e_invoicing_mandate_2026_001
    confidence_score: 0.97
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/ (hero section, 'E-facturatie verplicht? Jij loopt voorop')"
    notes: "Kyte is positioned as a response to the upcoming mandatory e-invoicing requirement."
    implicit_or_explicit: explicit

  - id: assoc_kyte_provides_support_resources
    source_entity_id: entity_kyte_001
    relationship_id: rel_provides_001
    target_entity_id: entity_support_resources_001
    confidence_score: 0.94
    source: website_documentation
    extracted_from: "https://clearfacts.be/nl/kyte/ (feature block 'Betrouwbare ondersteuning op maat')"
    notes: "Kyte is promoted together with practical guides, videos, and help."
    implicit_or_explicit: explicit
```

## Categories
```yaml
categories:
  - id: cat_kyte_application_ecosystem_001
    name: Kyte application ecosystem
    description: Applications, platforms, and networks that make up the Kyte operating environment.
    context_layer: application
    source: website_documentation

  - id: cat_kyte_business_objects_001
    name: Kyte business objects
    description: Business objects that Kyte users create, manage, exchange, or monitor.
    context_layer: business_concepts
    source: website_documentation

  - id: cat_kyte_invoice_data_001
    name: Kyte invoice data
    description: Invoice variants and data elements that Kyte uses to prepare compliant e-invoices.
    context_layer: business_concepts
    source: website_documentation

  - id: cat_kyte_user_roles_001
    name: Kyte user roles
    description: User roles explicitly identified as Kyte users or activation actors.
    context_layer: business_concepts
    source: website_documentation

  - id: cat_kyte_business_drivers_001
    name: Kyte business drivers
    description: External pressures or requirements used to motivate adoption of Kyte.
    context_layer: business_concepts
    source: website_documentation

  - id: cat_kyte_enablement_assets_001
    name: Kyte enablement assets
    description: Supporting resources presented as part of the Kyte offering.
    context_layer: application
    source: website_documentation

  - id: cat_kyte_standards_001
    name: Kyte standards
    description: Standards and technical specifications explicitly referenced in the Kyte e-invoicing flow.
    context_layer: technical
    source: website_documentation

  - id: cat_kyte_operational_concepts_001
    name: Kyte operational concepts
    description: Operational administration concepts that Kyte keeps ordered or syncs with Clearfacts.
    context_layer: business_concepts
    source: website_documentation
```

## Category Memberships
```yaml
category_memberships:
  - id: catmem_kyte_application_ecosystem_001
    entity_id: entity_kyte_001
    category_id: cat_kyte_application_ecosystem_001
    confidence_score: 0.99
    source: website_documentation

  - id: catmem_clearfacts_application_ecosystem_001
    entity_id: entity_clearfacts_001
    category_id: cat_kyte_application_ecosystem_001
    confidence_score: 0.96
    source: website_documentation

  - id: catmem_peppol_application_ecosystem_001
    entity_id: entity_peppol_001
    category_id: cat_kyte_application_ecosystem_001
    confidence_score: 0.98
    source: website_documentation

  - id: catmem_invoice_business_objects_001
    entity_id: entity_invoice_001
    category_id: cat_kyte_business_objects_001
    confidence_score: 0.96
    source: website_documentation

  - id: catmem_customer_business_objects_001
    entity_id: entity_customer_001
    category_id: cat_kyte_business_objects_001
    confidence_score: 0.93
    source: website_documentation

  - id: catmem_article_business_objects_001
    entity_id: entity_article_001
    category_id: cat_kyte_business_objects_001
    confidence_score: 0.91
    source: website_documentation

  - id: catmem_peppol_e_invoice_business_objects_001
    entity_id: entity_peppol_e_invoice_001
    category_id: cat_kyte_business_objects_001
    confidence_score: 0.98
    source: website_documentation

  - id: catmem_pdf_invoice_business_objects_001
    entity_id: entity_pdf_invoice_001
    category_id: cat_kyte_business_objects_001
    confidence_score: 0.96
    source: website_documentation

  - id: catmem_invoice_invoice_data_001
    entity_id: entity_invoice_001
    category_id: cat_kyte_invoice_data_001
    confidence_score: 0.95
    source: website_documentation

  - id: catmem_peppol_e_invoice_invoice_data_001
    entity_id: entity_peppol_e_invoice_001
    category_id: cat_kyte_invoice_data_001
    confidence_score: 0.98
    source: website_documentation

  - id: catmem_pdf_invoice_invoice_data_001
    entity_id: entity_pdf_invoice_001
    category_id: cat_kyte_invoice_data_001
    confidence_score: 0.95
    source: website_documentation

  - id: catmem_vat_number_invoice_data_001
    entity_id: entity_vat_number_001
    category_id: cat_kyte_invoice_data_001
    confidence_score: 0.95
    source: website_documentation

  - id: catmem_business_address_invoice_data_001
    entity_id: entity_business_address_001
    category_id: cat_kyte_invoice_data_001
    confidence_score: 0.94
    source: website_documentation

  - id: catmem_accountant_user_roles_001
    entity_id: entity_accountant_role_001
    category_id: cat_kyte_user_roles_001
    confidence_score: 0.98
    source: website_documentation

  - id: catmem_entrepreneur_user_roles_001
    entity_id: entity_entrepreneur_role_001
    category_id: cat_kyte_user_roles_001
    confidence_score: 0.95
    source: website_documentation

  - id: catmem_sme_user_roles_001
    entity_id: entity_sme_role_001
    category_id: cat_kyte_user_roles_001
    confidence_score: 0.95
    source: website_documentation

  - id: catmem_e_invoicing_mandate_business_drivers_001
    entity_id: entity_e_invoicing_mandate_2026_001
    category_id: cat_kyte_business_drivers_001
    confidence_score: 0.97
    source: website_documentation

  - id: catmem_support_resources_enablement_assets_001
    entity_id: entity_support_resources_001
    category_id: cat_kyte_enablement_assets_001
    confidence_score: 0.94
    source: website_documentation

  - id: catmem_ubl_standard_standards_001
    entity_id: entity_ubl_standard_001
    category_id: cat_kyte_standards_001
    confidence_score: 0.98
    source: website_documentation

  - id: catmem_customer_activity_operational_concepts_001
    entity_id: entity_customer_activity_001
    category_id: cat_kyte_operational_concepts_001
    confidence_score: 0.93
    source: website_documentation

  - id: catmem_business_figures_operational_concepts_001
    entity_id: entity_business_figures_001
    category_id: cat_kyte_operational_concepts_001
    confidence_score: 0.91
    source: website_documentation

  - id: catmem_administration_operational_concepts_001
    entity_id: entity_administration_001
    category_id: cat_kyte_operational_concepts_001
    confidence_score: 0.96
    source: website_documentation
```

## Notes
- Extraction is limited to the Kyte product pages under `https://clearfacts.be/nl/kyte/`, specifically the landing page, FAQ, and audience pages under `/voor-wie/`.
- FAQ content was used to refine the e-invoicing model with explicit XML and UBL details for Peppol invoices, plus the explicit contrast with PDF invoices.
- Audience-specific pages were used to strengthen the activation flow and add source-backed operational concepts such as automatic VAT/address checks, live flow to Clearfacts, visibility into current figures, and administration kept in one place.
- A French fallback snippet was visible on the `/voor-wie/` overview page, but no ontology facts were derived from that non-Dutch marketing fragment.
