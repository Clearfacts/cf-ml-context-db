# Ontology Extraction Schema

This schema defines the format agents should use when extracting ontology components (entities, relationships, categories) from various sources. The schema is **flexible by design**: it enforces a core structure for consistency and combinability, while explicitly allowing extensions for source-specific insights, confidence metadata, and custom properties.

---

## Core Ontology Units

### Entity

An **Entity** represents a concept, component, or element within the ClearFacts ontology. Entities are the primary building blocks.

**Required fields:**

```yaml
Entity:
  id: string                          # Unique identifier (e.g., "entity_accounting_001")
  name: string                        # The entity name (e.g., "Invoice", "Account")
  description: string                 # What this entity represents
  context_layer: string               # Which layer it belongs to (e.g., "business_concepts", "application", "technical")
```

**Recommended optional fields:**

```yaml
Entity:
  id: "entity_invoice_001"
  name: "Invoice"
  description: "A commercial document requesting payment for goods or services"
  context_layer: "business_concepts"
  
  # Optional metadata for better combination and validation
  aliases:                            # Alternative names or synonyms
    - "Bill"
    - "Invoice Document"
  related_terms:                      # Related concepts
    - "Payment"
    - "Line Item"
    - "Customer"
  
  # Source and confidence tracking
  source: "code_analysis"             # Where this entity came from
  extracted_from: "cf_ml_common/llm/token_tracker.py"
  confidence_score: 0.95              # 0.0-1.0, agent's confidence in this extraction
  
  # Custom agent-added fields (see Extension section)
  custom_field: "any_value"
```

**Extensibility:** Agents may add custom fields (e.g., `code_patterns`, `domain_specific_metadata`, `business_rules`) but must preserve all core required and recommended fields.

---

### Relationship

A **Relationship** defines how entities connect or interact.

**Required fields:**

```yaml
Relationship:
  id: string                          # Unique identifier (e.g., "rel_contains_001")
  name: string                        # The relationship type (e.g., "contains", "inherits_from", "processes")
  description: string                 # What this relationship represents
```

**Recommended optional fields:**

```yaml
Relationship:
  id: "rel_contains_001"
  name: "contains"
  description: "Entity A contains or is composed of Entity B"
  
  # Optional metadata
  directionality: "directed"          # "directed" or "bidirectional"
  cardinality: "one_to_many"          # "one_to_one", "one_to_many", "many_to_many", "many_to_one"
  
  # Extensibility examples
  semantic_type: "composition"        # Additional semantic classification
  reverse_name: "contained_by"        # If bidirectional, what's the reverse relationship name?
```

**Extensibility:** Agents may add semantic classifications, constraints, or domain-specific relationship properties.

---

### Association

An **Association** links two entities via a relationship. This is the glue that creates the knowledge graph.

**Required fields:**

```yaml
Association:
  id: string                          # Unique identifier (e.g., "assoc_001")
  source_entity_id: string            # Foreign key to source Entity
  relationship_id: string             # Foreign key to Relationship
  target_entity_id: string            # Foreign key to target Entity
```

**Recommended optional fields:**

```yaml
Association:
  id: "assoc_invoice_contains_line_items"
  source_entity_id: "entity_invoice_001"
  relationship_id: "rel_contains_001"
  target_entity_id: "entity_line_item_001"
  
  # Optional metadata
  confidence_score: 0.88              # Agent's confidence in this relationship
  source: "code_analysis"
  extracted_from: "context_db/model/__init__.py:45-52"
  notes: "Inferred from Invoice class composition"
  
  # Custom agent-added fields
  implicit_or_explicit: "explicit"    # Was this relationship explicitly stated or inferred?
  bidirectional: true
```

**Extensibility:** Agents may add relationship constraints, strength metrics, or contextual metadata.

---

### Category

A **Category** groups related entities by domain, function, or context. An entity may belong to multiple categories.

**Required fields:**

```yaml
Category:
  id: string                          # Unique identifier (e.g., "cat_accounting_concepts_001")
  name: string                        # Category name (e.g., "Accounting Concepts", "Document Types")
  description: string                 # What entities this category contains
```

**Recommended optional fields:**

```yaml
Category:
  id: "cat_accounting_concepts_001"
  name: "Accounting Concepts"
  description: "Core business concepts related to accounting and financial transactions"
  
  # Optional metadata
  parent_category_id: null            # For hierarchical categories
  context_layer: "business_concepts"  # Which layer this category serves
  
  # Extensibility
  domain: "accounting"
  priority: 1                         # Priority within its layer
```

**Extensibility:** Agents may add hierarchy depth, priority ordering, or domain-specific taxonomy information.

---

### Category Membership

An **Entity** belongs to one or more **Categories**. Track this separately for flexibility.

**Required fields:**

```yaml
CategoryMembership:
  id: string                          # Unique identifier
  entity_id: string                   # Foreign key to Entity
  category_id: string                 # Foreign key to Category
```

**Recommended optional fields:**

```yaml
CategoryMembership:
  id: "catmem_001"
  entity_id: "entity_invoice_001"
  category_id: "cat_accounting_concepts_001"
  
  confidence_score: 0.92
  source: "domain_documentation"
  notes: "Extracted from accounting glossary"
```

---

## Extensibility Rules

Agents are encouraged to extend the schema with custom fields, but should follow these conventions:

### 1. Metadata Fields (Recommended for all extractions)

Add these fields to track provenance and confidence:

```yaml
Entity:
  id: "entity_example_001"
  name: "Example Entity"
  # ... core fields ...
  
  # Provenance metadata
  source: string                      # Where extracted from (e.g., "code_analysis", "documentation", "conversation")
  extracted_from: string              # Specific file/section (e.g., "src/models/invoice.py:10-25")
  confidence_score: float             # 0.0-1.0, agent's confidence
  
  # Discovery insights
  ambiguous: boolean                  # Is there ambiguity in definition or usage?
  requires_validation: boolean        # Should this be verified by domain expert?
  validation_notes: string            # If ambiguous or needs validation, note why
```

### 2. Source-Specific Custom Fields

Based on extraction source, add relevant fields:

**From Code Analysis:**
```yaml
Entity:
  # ... core fields ...
  code_patterns:
    - class_definition: "Invoice"
      file: "context_db/model/invoice.py"
      line_range: "10-45"
  functions_related:
    - "validate_invoice()"
    - "calculate_total()"
  module_path: "context_db.model"
```

**From Documentation:**
```yaml
Entity:
  # ... core fields ...
  doc_references:
    - document: "Accounting_Glossary_v2.pdf"
      page: 15
      quote: "An invoice is a commercial document..."
  regulatory_references:
    - "IFRS Standards Section 15"
  domain_expert_source: "John Smith, Accounting Lead"
```

**From Database Schema:**
```yaml
Entity:
  # ... core fields ...
  database_mapping:
    table: "invoices"
    columns:
      - "id"
      - "customer_id"
      - "total_amount"
    primary_key: "id"
  data_type: "object"
```

**From System Conversations/Discussions:**
```yaml
Entity:
  # ... core fields ...
  conversation_context:
    discussed_in: "Architecture Review - 2025-04-20"
    participants: ["Alice", "Bob"]
    decision_outcome: "Approved for Q3 implementation"
  informal_synonyms:
    - "receipt"
    - "bill of sale"
```

### 3. Custom Domain Properties

Agents may add domain-specific properties relevant to their source:

```yaml
Entity:
  # ... core fields ...
  
  # Custom business rules (for accounting domain)
  accounting_rules:
    must_be_signed: true
    retention_period_months: 84
    audit_relevant: true
  
  # Custom technical properties
  api_endpoints:
    - "/invoices"
    - "/invoices/{id}"
  
  # Custom discovery properties
  discovery_method: "inferred_from_codebase_analysis"
  frequency_in_codebase: 23             # Number of references found
```

### 4. Guidelines for Custom Fields

- **Naming:** Use snake_case for field names, avoid spaces
- **Uniqueness:** Don't duplicate core field information in custom fields
- **Clarity:** Document what the custom field contains and why it's useful
- **Mergeability:** Consider how this field will combine with outputs from other agents (if two agents extract the same entity, how should custom fields merge?)
- **Non-invasive:** Never remove or rename core required fields

---

## Source-Specific Extraction Guidance

Agents will extract ontology components from different sources. Here's how to map source content to ontology units:

### From Code (Python, SQL, etc.)

**Entities:**
- Classes → Entities (e.g., `class Invoice` → Entity "Invoice")
- Database tables → Entities (e.g., `table invoices` → Entity "Invoice")
- Modules/packages → Entities (optional, if domain-relevant)

**Relationships:**
- Inheritance → "inherits_from"
- Composition → "contains"
- Foreign keys → "references"
- Method calls → "uses" or "calls"
- Imports → "depends_on"

**Example extraction from code:**

```python
class Invoice:
    """A commercial document for billing."""
    def __init__(self, customer_id, items):
        self.customer_id = customer_id
        self.items = items
```

Becomes:

```yaml
entities:
  - id: "entity_invoice_code_001"
    name: "Invoice"
    description: "A commercial document for billing"
    context_layer: "application"
    source: "code_analysis"
    extracted_from: "context_db/model/invoice.py:1-10"
    confidence_score: 0.98
    code_patterns:
      - class_definition: "Invoice"
        file: "context_db/model/invoice.py"

  - id: "entity_customer_code_001"
    name: "Customer"
    description: "Entity referenced in Invoice initialization"
    context_layer: "application"
    source: "code_analysis"
    extracted_from: "context_db/model/invoice.py:5"
    confidence_score: 0.85

associations:
  - id: "assoc_invoice_references_customer"
    source_entity_id: "entity_invoice_code_001"
    relationship_id: "rel_references_001"
    target_entity_id: "entity_customer_code_001"
    source: "code_analysis"
    implicit_or_explicit: "explicit"
    confidence_score: 0.95
```

### From Documentation (Markdown, PDFs, wikis)

**Entities:**
- Defined concepts or terms → Entities
- Mentioned systems or components → Entities
- Business objects described → Entities

**Relationships:**
- Explicit statements ("X manages Y") → Relationships
- Context clues ("X is used with Y") → Relationships
- Cross-references → Relationships

**Example extraction from documentation:**

```markdown
## Accounting Concepts

**Invoice:** A commercial document requesting payment for goods or services provided.

**Line Item:** A single line in an invoice representing one product or service.

An invoice contains multiple line items.
```

Becomes:

```yaml
entities:
  - id: "entity_invoice_doc_001"
    name: "Invoice"
    description: "A commercial document requesting payment for goods or services provided"
    context_layer: "business_concepts"
    source: "documentation"
    extracted_from: "docs/accounting_guide.md:15-20"
    confidence_score: 0.99
    doc_references:
      - document: "accounting_guide.md"
        page_or_section: "Accounting Concepts"

  - id: "entity_line_item_doc_001"
    name: "Line Item"
    description: "A single line in an invoice representing one product or service"
    context_layer: "business_concepts"
    source: "documentation"
    extracted_from: "docs/accounting_guide.md:22-25"
    confidence_score: 0.99

associations:
  - id: "assoc_invoice_contains_line_items"
    source_entity_id: "entity_invoice_doc_001"
    relationship_id: "rel_contains_001"
    target_entity_id: "entity_line_item_doc_001"
    source: "documentation"
    implicit_or_explicit: "explicit"
    confidence_score: 0.99
    notes: "Explicitly stated in documentation"
```

### From Databases

**Entities:**
- Tables → Entities
- Views → Entities (or Relationships, if derived)
- Data domain concepts → Entities

**Relationships:**
- Foreign keys → "references"
- Join logic → domain-specific relationships

**Example extraction from database schema:**

```sql
CREATE TABLE invoices (
  id INT PRIMARY KEY,
  customer_id INT FOREIGN KEY,
  total_amount DECIMAL
);
```

Becomes:

```yaml
entities:
  - id: "entity_invoice_db_001"
    name: "Invoice"
    description: "Database table containing invoice records"
    context_layer: "technical"
    source: "database_schema"
    extracted_from: "config/database.ini - ClearFacts DB"
    confidence_score: 0.99
    database_mapping:
      table: "invoices"
      columns:
        - id: "INT"
        - customer_id: "INT"
        - total_amount: "DECIMAL"
      primary_key: "id"

associations:
  - id: "assoc_invoice_references_customer_db"
    source_entity_id: "entity_invoice_db_001"
    relationship_id: "rel_references_001"
    target_entity_id: "entity_customer_db_001"
    source: "database_schema"
    implicit_or_explicit: "explicit"
    confidence_score: 0.99
    notes: "Foreign key constraint"
```

### From Conversations / Expert Discussions

**Entities:**
- Mentioned systems, concepts, or decisions → Entities
- Implied stakeholder interests → Entities

**Relationships:**
- Stated dependencies or discussions → Relationships
- Inferred from context → Relationships (mark as lower confidence)

**Example extraction from conversation:**

```
Alice: "We need to track invoice approvals separately."
Bob: "Yeah, the approval process involves multiple stakeholders."
```

Becomes:

```yaml
entities:
  - id: "entity_invoice_approval_conv_001"
    name: "Invoice Approval"
    description: "Process for approving invoices before processing"
    context_layer: "business_processes"
    source: "conversation"
    extracted_from: "Architecture Review - 2025-04-20"
    confidence_score: 0.75
    ambiguous: true
    validation_notes: "Need clarification on approval workflow details"
    conversation_context:
      discussed_in: "Architecture Review - 2025-04-20"
      participants: ["Alice", "Bob"]

associations:
  - id: "assoc_invoice_requires_approval"
    source_entity_id: "entity_invoice_001"
    relationship_id: "rel_requires_001"
    target_entity_id: "entity_invoice_approval_conv_001"
    source: "conversation"
    implicit_or_explicit: "inferred"
    confidence_score: 0.65
    notes: "Inferred from discussion; needs validation"
```

---

## Validation & Consistency Rules

Agents should validate their outputs against these rules before submission:

### 1. Entity Validation

- **Uniqueness within layer:** Entity names must be unique within their `context_layer` (or clearly marked as duplicates with different meanings)
- **Non-empty descriptions:** Every entity must have a meaningful description (at least 10 characters)
- **Valid context layer:** `context_layer` must be one of: `business_concepts`, `application`, `technical`, `architecture`, `database_schema` (or agent may propose new layers with justification)

### 2. Relationship Validation

- **Valid targets:** Every Association's `source_entity_id` and `target_entity_id` must reference valid entities in the extraction output
- **Named relationships:** Relationships should have descriptive names (avoid generic "related_to" unless no better option)
- **Cardinality clarity:** For compositions/contains relationships, specify cardinality (one-to-one, one-to-many, etc.) if determinable

### 3. Category Validation

- **Coverage:** Categories should group related entities meaningfully
- **Avoiding overlap:** Minimize entity overlap between categories (unless multi-category membership is justified)
- **Named clearly:** Category names should indicate the grouping principle

### 4. Confidence Score Guidance

- **High confidence (0.85-1.0):** Explicitly stated, well-documented, direct extraction
- **Medium confidence (0.65-0.84):** Inferred from context, some ambiguity, requires minor interpretation
- **Low confidence (0.0-0.64):** Highly speculative, unclear, requires validation
- **Default:** If no confidence score provided, assume 0.80 (moderate confidence)

### 5. Source Tracking

- **Always include:** `source` field (code_analysis, documentation, database_schema, conversation, other)
- **Include location:** `extracted_from` field should point to specific file/section/line if applicable
- **Mark ambiguity:** Use `ambiguous: true` and `validation_notes` if extraction is uncertain

---

## Output Structure

When submitting extraction results, organize output in this structure:

```yaml
# extraction_results.yaml
metadata:
  agent_name: string                  # Name of the agent performing extraction
  extraction_timestamp: ISO8601       # When extraction occurred
  source_type: string                 # Overall source type (code, docs, db, conversation, mixed)
  context_layer_focus: string         # Primary layer focused on

entities:
  - # Entity 1
  - # Entity 2
  # ... more entities

relationships:
  - # Relationship 1
  - # Relationship 2
  # ... more relationships

associations:
  - # Association 1
  - # Association 2
  # ... more associations

categories:
  - # Category 1
  - # Category 2
  # ... more categories

category_memberships:
  - # Membership 1
  - # Membership 2
  # ... more memberships

# Optional: Extraction insights
extraction_notes: |
  Any notable findings, challenges, or recommendations.
  E.g., "Found 3 conflicting definitions of 'Invoice' across codebase"

conflicts_or_ambiguities:
  - entity_id: "entity_xxx_001"
    issue: "Multiple definitions found in different sources"
    details: "Code defines X as A, but documentation defines X as B"
    recommendation: "Requires domain expert review"

# Optional: Metrics
metrics:
  total_entities_extracted: number
  total_relationships_extracted: number
  average_confidence_score: float
  entities_requiring_validation: number
```

---

## Notes on Combination & Merging

This schema design supports later combination and consensus logic:

### Merging Strategy (To be refined by Consensus Agent)

When combining outputs from multiple agents:

1. **Entity Deduplication:** Match entities by (name, context_layer) pair
   - If same entity extracted by multiple agents, merge custom fields and take highest confidence score
   - If conflicting definitions, flag for human review

2. **Relationship Merging:** Match relationships by (name, directionality) pair
   - Combine confidence scores via averaging or other aggregation
   - Preserve all source citations

3. **Association Merging:** Match by (source_entity_id, relationship_id, target_entity_id) triple
   - Combine metadata, keep highest confidence
   - If agents disagree on cardinality/properties, flag conflict

4. **Category Merging:** Match by (name, context_layer) pair
   - Merge entity memberships, resolving duplicates

### Fields Requiring Special Merge Handling

- `confidence_score` → Aggregate (average, max, weighted vote)
- `source` + `extracted_from` → Combine into list of sources
- `ambiguous` + `validation_notes` → Collect all flags and notes
- Custom fields → Merge if compatible, keep all if divergent (flag for review)

### Conflict Resolution

When agents disagree on entity definition or relationship, mark as conflict with:

```yaml
conflict_marker: true
conflicting_sources:
  - source: "code_analysis"
    definition: "..."
    confidence: 0.95
  - source: "documentation"
    definition: "..."
    confidence: 0.88
merge_recommendation: "Requires domain expert consensus"
```

---

## Quick Reference: Field Checklist

**Always include:**
- ✅ `id` (Entity, Relationship, Category)
- ✅ `name` (Entity, Relationship, Category)
- ✅ `description` (Entity, Relationship, Category)
- ✅ `context_layer` (Entity, Category)

**Strongly recommended:**
- ✅ `source` (origin of extraction)
- ✅ `confidence_score` (0.0-1.0)
- ✅ `extracted_from` (specific location)

**Optional but valuable:**
- ✅ `aliases`, `related_terms` (Entity)
- ✅ `ambiguous`, `requires_validation` (any unit)
- ✅ Source-specific custom fields (code_patterns, doc_references, etc.)

**For Associations:**
- ✅ `source_entity_id`, `relationship_id`, `target_entity_id` (required)
- ✅ `confidence_score`, `source` (recommended)
- ✅ `implicit_or_explicit` (helpful for merge logic)

---

## Summary

This schema provides **clear structure** (core fields) with **maximum flexibility** (custom extensions). Agents should:

1. Extract and map source content to entities, relationships, and associations
2. Include core required fields + recommended metadata fields
3. Add source-specific custom fields as relevant
4. Validate outputs against consistency rules
5. Include confidence scores and source citations for later combination
6. Mark ambiguities and items requiring validation

The result: compatible outputs from diverse sources that can be intelligently merged, deduplicated, and used to build a rich, layered ontology.
