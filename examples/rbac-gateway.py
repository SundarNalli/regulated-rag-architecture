# RBAC Gateway for RAG System - Example Implementation

"""
This module demonstrates how to enforce role-based access control (RBAC)
at the retrieval layer of a RAG system in regulated environments.

Key Principle: Users should only retrieve documents they're authorized to access,
regardless of what they ask the LLM.

Author: Sundar Nalli
License: MIT
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UserRole(Enum):
    """Defined user roles in the insurance underwriting system"""
    JUNIOR_UNDERWRITER = "junior_underwriter"
    SENIOR_UNDERWRITER = "senior_underwriter"
    MANAGER = "manager"
    AUDITOR = "auditor"
    GUEST = "guest"


class DocumentClassification(Enum):
    """Document security classifications"""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


@dataclass
class User:
    """User with authentication and authorization details"""
    user_id: str
    name: str
    role: UserRole
    department: str


@dataclass
class Document:
    """Document metadata in the vector database"""
    document_id: str
    title: str
    classification: DocumentClassification
    authorized_roles: List[UserRole]
    department: Optional[str] = None


class RBACGateway:
    """
    Role-Based Access Control Gateway for RAG retrieval.
    
    This class enforces access policies BEFORE querying the vector database,
    ensuring users can only retrieve documents they're authorized to see.
    """
    
    # Define role hierarchy (higher roles inherit lower role permissions)
    ROLE_HIERARCHY = {
        UserRole.GUEST: [DocumentClassification.PUBLIC],
        UserRole.JUNIOR_UNDERWRITER: [
            DocumentClassification.PUBLIC,
            DocumentClassification.INTERNAL
        ],
        UserRole.SENIOR_UNDERWRITER: [
            DocumentClassification.PUBLIC,
            DocumentClassification.INTERNAL,
            DocumentClassification.CONFIDENTIAL
        ],
        UserRole.MANAGER: [
            DocumentClassification.PUBLIC,
            DocumentClassification.INTERNAL,
            DocumentClassification.CONFIDENTIAL,
            DocumentClassification.RESTRICTED
        ],
        UserRole.AUDITOR: [  # Auditors have read-only access to all
            DocumentClassification.PUBLIC,
            DocumentClassification.INTERNAL,
            DocumentClassification.CONFIDENTIAL,
            DocumentClassification.RESTRICTED
        ]
    }
    
    def __init__(self):
        """Initialize the RBAC gateway with audit logging"""
        self.access_log: List[Dict] = []
    
    def get_authorized_classifications(self, user: User) -> List[DocumentClassification]:
        """
        Get document classifications a user role is authorized to access.
        
        Args:
            user: User object with role information
            
        Returns:
            List of document classifications the user can access
        """
        return self.ROLE_HIERARCHY.get(user.role, [DocumentClassification.PUBLIC])
    
    def is_authorized(self, user: User, document: Document) -> bool:
        """
        Check if a user is authorized to access a specific document.
        
        This implements defense-in-depth by checking:
        1. Document classification vs. user role permissions
        2. Explicit document-level authorization list
        3. Department-based access (if applicable)
        
        Args:
            user: User requesting access
            document: Document being accessed
            
        Returns:
            True if user is authorized, False otherwise
        """
        # Check 1: Classification-based access
        authorized_classifications = self.get_authorized_classifications(user)
        if document.classification not in authorized_classifications:
            self._log_access_denial(user, document, "Classification not authorized")
            return False
        
        # Check 2: Explicit document authorization list
        if document.authorized_roles and user.role not in document.authorized_roles:
            self._log_access_denial(user, document, "Role not in authorized list")
            return False
        
        # Check 3: Department-based access (if document is department-specific)
        if document.department and document.department != user.department:
            self._log_access_denial(user, document, "Department mismatch")
            return False
        
        # Access granted
        self._log_access_success(user, document)
        return True
    
    def build_vector_search_filter(self, user: User) -> Dict:
        """
        Build a filter for vector database search based on user permissions.
        
        This filter is applied at query time to ensure the vector database
        only returns documents the user is authorized to access.
        
        Args:
            user: User making the search request
            
        Returns:
            Dictionary representing search filters (format depends on vector DB)
        
        Example return value for Azure AI Search:
            {
                "filter": "classification in ('public', 'internal') and department eq 'underwriting'"
            }
        """
        authorized_classifications = self.get_authorized_classifications(user)
        classification_filter = [c.value for c in authorized_classifications]
        
        # Build filter object (Azure AI Search format)
        filter_conditions = [
            f"classification in ({', '.join(repr(c) for c in classification_filter)})"
        ]
        
        # Add department filter if user has department-specific access
        if user.department:
            filter_conditions.append(f"(department eq '{user.department}' or department eq null)")
        
        return {
            "filter": " and ".join(filter_conditions)
        }
    
    def _log_access_success(self, user: User, document: Document):
        """Log successful access for audit trail"""
        log_entry = {
            "timestamp": "2024-01-15T10:30:00Z",  # Use actual timestamp in production
            "event": "ACCESS_GRANTED",
            "user_id": user.user_id,
            "user_role": user.role.value,
            "document_id": document.document_id,
            "document_classification": document.classification.value
        }
        self.access_log.append(log_entry)
        logger.info(f"Access granted: {user.name} → {document.title}")
    
    def _log_access_denial(self, user: User, document: Document, reason: str):
        """Log access denial for security monitoring"""
        log_entry = {
            "timestamp": "2024-01-15T10:30:00Z",  # Use actual timestamp in production
            "event": "ACCESS_DENIED",
            "user_id": user.user_id,
            "user_role": user.role.value,
            "document_id": document.document_id,
            "document_classification": document.classification.value,
            "reason": reason
        }
        self.access_log.append(log_entry)
        logger.warning(f"Access denied: {user.name} → {document.title} | Reason: {reason}")


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

def example_usage():
    """Demonstrate RBAC gateway in action"""
    
    # Initialize RBAC gateway
    rbac = RBACGateway()
    
    # Define users
    junior_underwriter = User(
        user_id="u001",
        name="Alice Johnson",
        role=UserRole.JUNIOR_UNDERWRITER,
        department="underwriting"
    )
    
    senior_underwriter = User(
        user_id="u002",
        name="Bob Smith",
        role=UserRole.SENIOR_UNDERWRITER,
        department="underwriting"
    )
    
    manager = User(
        user_id="u003",
        name="Carol Williams",
        role=UserRole.MANAGER,
        department="underwriting"
    )
    
    # Define documents
    public_policy = Document(
        document_id="d001",
        title="Public Flood Insurance Guidelines",
        classification=DocumentClassification.PUBLIC,
        authorized_roles=[UserRole.JUNIOR_UNDERWRITER, UserRole.SENIOR_UNDERWRITER, UserRole.MANAGER]
    )
    
    confidential_exceptions = Document(
        document_id="d002",
        title="Exception Approval Guidelines",
        classification=DocumentClassification.CONFIDENTIAL,
        authorized_roles=[UserRole.SENIOR_UNDERWRITER, UserRole.MANAGER]
    )
    
    restricted_risk_assessment = Document(
        document_id="d003",
        title="Internal Risk Assessment Model",
        classification=DocumentClassification.RESTRICTED,
        authorized_roles=[UserRole.MANAGER]
    )
    
    # Test access control
    print("\n=== RBAC Gateway Example ===\n")
    
    # Scenario 1: Junior underwriter accessing public document (ALLOWED)
    print("Scenario 1: Junior underwriter → Public document")
    if rbac.is_authorized(junior_underwriter, public_policy):
        print("✓ Access granted\n")
    else:
        print("✗ Access denied\n")
    
    # Scenario 2: Junior underwriter accessing confidential document (DENIED)
    print("Scenario 2: Junior underwriter → Confidential document")
    if rbac.is_authorized(junior_underwriter, confidential_exceptions):
        print("✓ Access granted\n")
    else:
        print("✗ Access denied (expected behavior)\n")
    
    # Scenario 3: Senior underwriter accessing confidential document (ALLOWED)
    print("Scenario 3: Senior underwriter → Confidential document")
    if rbac.is_authorized(senior_underwriter, confidential_exceptions):
        print("✓ Access granted\n")
    else:
        print("✗ Access denied\n")
    
    # Scenario 4: Manager accessing restricted document (ALLOWED)
    print("Scenario 4: Manager → Restricted document")
    if rbac.is_authorized(manager, restricted_risk_assessment):
        print("✓ Access granted\n")
    else:
        print("✗ Access denied\n")
    
    # Show vector search filter for senior underwriter
    print("Vector search filter for senior underwriter:")
    search_filter = rbac.build_vector_search_filter(senior_underwriter)
    print(f"  {search_filter['filter']}\n")
    
    # Show audit log
    print("=== Audit Log ===")
    for log_entry in rbac.access_log:
        print(f"  {log_entry['event']}: {log_entry['user_id']} → {log_entry['document_id']}")


if __name__ == "__main__":
    example_usage()


# ============================================================================
# INTEGRATION WITH VECTOR DATABASE (PSEUDOCODE)
# ============================================================================

"""
Example integration with Azure AI Search:

from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

def rag_query_with_rbac(user: User, query: str) -> List[Dict]:
    '''Query RAG system with RBAC enforcement'''
    
    # Initialize RBAC gateway
    rbac = RBACGateway()
    
    # Build role-based filter
    search_filter = rbac.build_vector_search_filter(user)
    
    # Initialize Azure AI Search client
    search_client = SearchClient(
        endpoint="https://your-search-service.search.windows.net",
        index_name="underwriting-knowledge-base",
        credential=AzureKeyCredential("your-api-key")
    )
    
    # Execute vector search with RBAC filter
    results = search_client.search(
        search_text=query,
        filter=search_filter['filter'],  # CRITICAL: RBAC filter applied here
        select=["document_id", "title", "content", "classification"],
        top=5
    )
    
    # Return only documents user is authorized to see
    return list(results)

# Usage
results = rag_query_with_rbac(
    user=junior_underwriter,
    query="What are the flood insurance guidelines?"
)
# Results will ONLY include documents junior_underwriter is authorized to access
"""
