from typing import List
from pydantic import BaseModel, Field
import dspy


class SecurityFinding(BaseModel):
    title: str = Field(..., description="Concise title of the vulnerability")
    severity: str = Field(..., description="Critical, High, Medium, or Low")
    description: str = Field(..., description="Detailed description of the issue")
    impact: str = Field(..., description="Potential impact and exploitability")
    location: str = Field(..., description="Specific code location (file and line)")
    remediation: str = Field(..., description="Actionable steps to fix the issue")


class SecurityReport(BaseModel):
    executive_summary: str = Field(..., description="High-level risk assessment")
    findings: List[SecurityFinding] = Field(
        default_factory=list, description="List of security vulnerabilities found"
    )
    risk_matrix: str = Field(..., description="Summary of findings by severity")
    action_required: bool = Field(
        ..., description="True if actionable findings present, False otherwise"
    )


class SecuritySentinel(dspy.Signature):
    """
    You are an elite Application Security Specialist with deep expertise in identifying and mitigating security vulnerabilities.

    ## Core Security Scanning Protocol
    1. Input Validation Analysis (sanitization, types, limits).
    2. SQL Injection Risk Assessment (parameterization, concatenation).
    3. XSS Vulnerability Detection (escaping, CSP).
    4. Authentication & Authorization Audit (endpoints, sessions, RBAC).
    5. Sensitive Data Exposure (secrets, logs, encryption).
    6. OWASP Top 10 Compliance.
    """

    code_diff: str = dspy.InputField(desc="The code changes to review")
    security_report: SecurityReport = dspy.OutputField(
        desc="Structured security audit report"
    )
