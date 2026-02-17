# Deployment Guide: Regulated RAG Architecture on Azure

> **Step-by-step guide to deploying a production-grade RAG system with embedded AI governance**

---

## Prerequisites

### Azure Resources Required

- **Azure OpenAI Service** (GPT-4 or GPT-3.5-turbo)
- **Azure AI Search** (Standard tier or higher for security features)
- **Azure Kubernetes Service (AKS)** or **Azure App Services**
- **Azure Key Vault** (for secrets management)
- **Azure Monitor + Application Insights** (for observability)
- **Azure Blob Storage** (for document storage)
- **Azure Active Directory** (for authentication)

### Local Development Tools

- Azure CLI (`az`)
- kubectl (for AKS deployments)
- Docker (for containerization)
- Python 3.11+ or .NET 8 SDK
- Terraform or Bicep (for infrastructure-as-code)

---

## Architecture Deployment Phases

### Phase 1: Foundation Layer (Security & Identity)

**Objective:** Set up authentication, authorization, and secrets management.

#### Step 1.1: Configure Azure Active Directory

```bash
# Create Azure AD app registration for the RAG application
az ad app create \
  --display-name "regulated-rag-app" \
  --sign-in-audience AzureADMyOrg

# Create service principal
az ad sp create --id <APP_ID>

# Define app roles in manifest (for RBAC)
# Roles: junior_underwriter, senior_underwriter, manager, auditor
```

**App Roles Configuration (manifest.json):**

```json
{
  "appRoles": [
    {
      "id": "uuid-1",
      "displayName": "Junior Underwriter",
      "description": "Can access public and internal documents",
      "value": "junior_underwriter",
      "allowedMemberTypes": ["User"]
    },
    {
      "id": "uuid-2",
      "displayName": "Senior Underwriter",
      "description": "Can access up to confidential documents",
      "value": "senior_underwriter",
      "allowedMemberTypes": ["User"]
    },
    {
      "id": "uuid-3",
      "displayName": "Manager",
      "description": "Can access all document classifications",
      "value": "manager",
      "allowedMemberTypes": ["User"]
    }
  ]
}
```

#### Step 1.2: Set Up Azure Key Vault

```bash
# Create Key Vault
az keyvault create \
  --name regulated-rag-kv \
  --resource-group regulated-rag-rg \
  --location eastus \
  --enable-rbac-authorization true

# Store secrets
az keyvault secret set --vault-name regulated-rag-kv --name "OpenAI-ApiKey" --value "<key>"
az keyvault secret set --vault-name regulated-rag-kv --name "AzureSearch-ApiKey" --value "<key>"

# Grant application access to Key Vault
az role assignment create \
  --role "Key Vault Secrets User" \
  --assignee <APP_SERVICE_PRINCIPAL_ID> \
  --scope /subscriptions/<SUBSCRIPTION_ID>/resourceGroups/regulated-rag-rg/providers/Microsoft.KeyVault/vaults/regulated-rag-kv
```

---

### Phase 2: Data Layer (Document Ingestion & Vector Database)

**Objective:** Ingest policy documents and build searchable vector index with access control metadata.

#### Step 2.1: Create Azure AI Search Index with RBAC Fields

```bash
# Create Azure AI Search service
az search service create \
  --name regulated-rag-search \
  --resource-group regulated-rag-rg \
  --sku standard \
  --location eastus
```

**Index Schema (with RBAC metadata):**

```json
{
  "name": "underwriting-knowledge-base",
  "fields": [
    {"name": "id", "type": "Edm.String", "key": true},
    {"name": "content", "type": "Edm.String", "searchable": true},
    {"name": "embedding", "type": "Collection(Edm.Single)", "searchable": true, "dimensions": 1536},
    {"name": "title", "type": "Edm.String", "searchable": true, "filterable": true},
    {"name": "source_document", "type": "Edm.String", "filterable": true},
    {"name": "page_number", "type": "Edm.Int32", "filterable": true},
    
    // RBAC metadata fields
    {"name": "classification", "type": "Edm.String", "filterable": true},
    {"name": "authorized_roles", "type": "Collection(Edm.String)", "filterable": true},
    {"name": "department", "type": "Edm.String", "filterable": true},
    {"name": "document_version", "type": "Edm.String", "filterable": true},
    {"name": "last_updated", "type": "Edm.DateTimeOffset", "filterable": true}
  ]
}
```

#### Step 2.2: Document Ingestion Pipeline

```python
# Example: Ingest documents with RBAC metadata
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI

def ingest_document_with_metadata(document_path: str, classification: str, authorized_roles: List[str]):
    """
    Ingest a document into Azure AI Search with RBAC metadata
    """
    # 1. Extract text from document (PDF, DOCX, etc.)
    text_chunks = extract_and_chunk_document(document_path)
    
    # 2. Generate embeddings using Azure OpenAI
    openai_client = AzureOpenAI(endpoint="...", api_key="...")
    
    documents_to_index = []
    for i, chunk in enumerate(text_chunks):
        # Generate embedding
        embedding_response = openai_client.embeddings.create(
            model="text-embedding-ada-002",
            input=chunk['text']
        )
        embedding = embedding_response.data[0].embedding
        
        # Build document with RBAC metadata
        doc = {
            "id": f"{document_path}-chunk-{i}",
            "content": chunk['text'],
            "embedding": embedding,
            "title": chunk['title'],
            "source_document": document_path,
            "page_number": chunk['page'],
            
            # RBAC metadata (CRITICAL FOR GOVERNANCE)
            "classification": classification,  # e.g., "confidential"
            "authorized_roles": authorized_roles,  # e.g., ["senior_underwriter", "manager"]
            "department": "underwriting",
            "document_version": "v2.3",
            "last_updated": "2024-01-15T00:00:00Z"
        }
        documents_to_index.append(doc)
    
    # 3. Upload to Azure AI Search
    search_client = SearchClient(endpoint="...", index_name="underwriting-knowledge-base", credential=...)
    search_client.upload_documents(documents=documents_to_index)
    
    print(f"Ingested {len(documents_to_index)} chunks from {document_path}")

# Usage
ingest_document_with_metadata(
    document_path="policy-manual-v2.3.pdf",
    classification="confidential",
    authorized_roles=["senior_underwriter", "manager"]
)
```

---

### Phase 3: AI Processing Layer (LLM Gateway & Governance)

**Objective:** Deploy LLM gateway with prompt guards and content filtering.

#### Step 3.1: Deploy Azure OpenAI with Content Filtering

```bash
# Create Azure OpenAI resource
az cognitiveservices account create \
  --name regulated-rag-openai \
  --resource-group regulated-rag-rg \
  --kind OpenAI \
  --sku S0 \
  --location eastus

# Deploy GPT-4 model
az cognitiveservices account deployment create \
  --resource-group regulated-rag-rg \
  --name regulated-rag-openai \
  --deployment-name gpt-4 \
  --model-name gpt-4 \
  --model-version "0613" \
  --model-format OpenAI \
  --sku-capacity 10 \
  --sku-name Standard
```

#### Step 3.2: Implement LLM Gateway with Governance Controls

```python
# Example: LLM gateway with citation enforcement
from openai import AzureOpenAI

class GovernedLLMGateway:
    """LLM gateway with embedded governance controls"""
    
    SYSTEM_PROMPT = """You are an AI assistant for insurance underwriters. 

CRITICAL RULES:
1. ALWAYS cite the source document for every claim you make.
2. Format citations as: [Source: Policy Manual v2.3, Section 4.2]
3. If you cannot find information in the provided context, say "I don't have information on this topic."
4. NEVER make up policy interpretations. Only use provided documents.
5. If asked about denying coverage or exceptions, remind user to consult a senior underwriter.

You have access to the following documents:
{document_context}
"""
    
    def __init__(self, azure_openai_endpoint: str, api_key: str):
        self.client = AzureOpenAI(endpoint=azure_openai_endpoint, api_key=api_key)
    
    def generate_response(self, user_query: str, retrieved_documents: List[Dict]) -> Dict:
        """
        Generate LLM response with governance controls
        
        Returns:
            {
                "response": "...",
                "citations": [...],
                "safety_check_passed": True/False
            }
        """
        # Build document context with citation metadata
        doc_context = self._format_documents_with_citations(retrieved_documents)
        
        # Generate response
        completion = self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT.format(document_context=doc_context)},
                {"role": "user", "content": user_query}
            ],
            temperature=0.0,  # Low temperature for factual accuracy
            max_tokens=500
        )
        
        response_text = completion.choices[0].message.content
        
        # Validate response (governance check)
        validation_result = self._validate_response(response_text, retrieved_documents)
        
        return {
            "response": response_text,
            "citations": validation_result["citations"],
            "safety_check_passed": validation_result["has_citations"],
            "requires_hitl": validation_result["requires_human_review"]
        }
    
    def _validate_response(self, response: str, retrieved_docs: List[Dict]) -> Dict:
        """
        Validate that response includes proper citations
        """
        # Check if response contains citation markers
        has_citations = "[Source:" in response or "Policy Manual" in response
        
        # Determine if human review is needed (example logic)
        high_risk_keywords = ["deny", "exception", "override", "claim rejection"]
        requires_human_review = any(keyword in response.lower() for keyword in high_risk_keywords)
        
        return {
            "has_citations": has_citations,
            "requires_human_review": requires_human_review,
            "citations": self._extract_citations(response)
        }
```

---

### Phase 4: Orchestration Layer (RBAC + HITL + Audit Logging)

**Objective:** Deploy the orchestration layer that ties everything together.

#### Step 4.1: Deploy RAG Orchestrator Service

```python
# Example: Main RAG orchestrator with all governance layers
from rbac_gateway import RBACGateway
from llm_gateway import GovernedLLMGateway
from audit_logger import AuditLogger
from hitl_queue import HITLQueue

class RegulatedRAGOrchestrator:
    """
    Main orchestrator for regulated RAG system.
    Coordinates RBAC, retrieval, LLM, HITL, and audit logging.
    """
    
    def __init__(self):
        self.rbac_gateway = RBACGateway()
        self.llm_gateway = GovernedLLMGateway(endpoint="...", api_key="...")
        self.audit_logger = AuditLogger()
        self.hitl_queue = HITLQueue()
    
    async def process_query(self, user: User, query: str) -> Dict:
        """
        Process user query through governed RAG pipeline
        """
        query_id = str(uuid.uuid4())
        
        # Step 1: Log query
        self.audit_logger.log_query(user, query, query_id)
        
        # Step 2: Apply RBAC filter
        search_filter = self.rbac_gateway.build_vector_search_filter(user)
        
        # Step 3: Retrieve documents (with RBAC enforcement)
        retrieved_docs = await self.vector_search(query, search_filter)
        
        # Step 4: Generate LLM response
        llm_result = self.llm_gateway.generate_response(query, retrieved_docs)
        
        # Step 5: Check if human review is needed
        if llm_result["requires_hitl"]:
            # Queue for human approval
            self.hitl_queue.enqueue(user, query, llm_result, query_id)
            return {
                "status": "pending_review",
                "message": "This query requires human review. You'll be notified when approved.",
                "query_id": query_id
            }
        
        # Step 6: Log response
        self.audit_logger.log_response(user, query, llm_result, query_id)
        
        # Step 7: Return response
        return {
            "status": "success",
            "response": llm_result["response"],
            "citations": llm_result["citations"],
            "query_id": query_id
        }
```

---

## Deployment Checklist

### Pre-Production Validation

- [ ] **Security Review**: All secrets in Key Vault, no hardcoded credentials
- [ ] **RBAC Testing**: Verify users can only access authorized documents
- [ ] **HITL Workflows**: Test high-risk query routing and approval process
- [ ] **Audit Logging**: Confirm all queries, retrievals, and responses are logged
- [ ] **Performance Testing**: Load test with expected query volume
- [ ] **Disaster Recovery**: Backup strategy for vector index and audit logs
- [ ] **Monitoring**: Dashboards and alerts configured in Azure Monitor
- [ ] **Compliance Sign-Off**: Risk committee and legal approval obtained

### Go-Live Procedure

1. Deploy to staging environment
2. Run smoke tests with real user roles
3. Conduct red team exercise (adversarial testing)
4. Review audit logs for anomalies
5. Deploy to production during maintenance window
6. Monitor first 24 hours closely
7. Conduct post-deployment review

---

## Monitoring & Maintenance

### Key Metrics to Track

- **Retrieval quality**: Relevance scores, citation coverage
- **RBAC violations**: Unauthorized access attempts
- **HITL approval rate**: % of queries requiring human review
- **Response latency**: P50, P95, P99 latencies
- **User satisfaction**: Thumbs up/down ratings

### Quarterly Reviews

- **Bias testing**: Test with diverse scenarios
- **Risk reassessment**: Update risk matrix based on incidents
- **Governance refresh**: Review and update ADRs
- **Model updates**: Evaluate new LLM versions

---

## Troubleshooting

### Common Issues

**Issue:** Users seeing "Access Denied" for documents they should access
- **Fix:** Check role assignments in Azure AD and authorized_roles in vector index

**Issue:** Responses missing citations
- **Fix:** Review system prompt, add citation validation logic

**Issue:** High HITL approval rate (>30%)
- **Fix:** Refine risk thresholds, provide better training data

---

## Support & Contact

For deployment assistance:
- **Technical Questions**: sundarnalli@gmail.com
- **Architecture Reviews**: Schedule a consultation
- **Production Issues**: [Create GitHub issue](https://github.com/YourUsername/regulated-rag-architecture/issues)

---

**Next Steps:** After successful deployment, consider:
- Expanding to additional use cases (claims processing, compliance Q&A)
- Integrating with existing underwriting platforms
- Implementing continuous monitoring and alerting
- Conducting quarterly governance reviews
